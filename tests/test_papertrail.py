import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PY = sys.executable
ROOT = Path(__file__).resolve().parents[1]


def pt(cwd, *args, check=True):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    r = subprocess.run([PY, "-m", "papertrail", *args], cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise AssertionError(f"papertrail {args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def ledger(proj):
    return [json.loads(l) for l in (proj / "labbook/ledger.jsonl").read_text().splitlines()]


@pytest.fixture
def proj(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    sh(tmp_path, "git", "config", "user.email", "t@example.org")
    sh(tmp_path, "git", "config", "user.name", "T")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/in.txt").write_text("3\n4\n")
    (tmp_path / "sq.py").write_text(
        "import sys\nxs=[int(l) for l in open('data/in.txt')]\nopen('out.txt','w').write(str(sum(x*x for x in xs))+'\\n')\n"
    )
    pt(tmp_path, "init", "--tier", "ledgered", "--containment", "1", "--purpose", "test")
    cfg = (tmp_path / "papertrail.toml").read_text().replace("inputs = []", 'inputs = ["data/*.txt"]')
    (tmp_path / "papertrail.toml").write_text(cfg)
    sh(tmp_path, "git", "add", "sq.py", "papertrail.toml", "labbook")
    sh(tmp_path, "git", "commit", "-qm", "start")
    return tmp_path


def test_init_writes_genesis_and_refuses_twice(proj):
    es = ledger(proj)
    assert es[0]["kind"] == "genesis" and es[0]["prev"] is None
    assert es[0]["settings"]["tier"] == "ledgered"
    assert pt(proj, "init", check=False).returncode == 2


def test_run_records_commit_inputs_outputs_env(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    assert (proj / "out.txt").read_text() == "25\n"
    run = ledger(proj)[-1]
    b = run["body"]
    assert run["kind"] == "run" and run["prev"] == ledger(proj)[0]["hash"]
    assert b["exit_code"] == 0 and b["commit"] and b["dirty"] == []
    assert set(b["inputs"]) == {"data/in.txt"} and set(b["outputs"]) == {"out.txt"}
    assert "sq.py" in b["code"] and "python" in b["env"]


def test_commit_before_compute_refuses_dirty_code(proj):
    (proj / "sq.py").write_text((proj / "sq.py").read_text() + "# edit\n")
    r = pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py", check=False)
    assert r.returncode == 2 and "uncommitted code" in r.stderr
    assert len(ledger(proj)) == 1
    pt(proj, "run", "--allow-dirty", "--out", "out.txt", "--", PY, "sq.py")
    b = ledger(proj)[-1]["body"]
    assert b["allow_dirty"] and b["dirty"] == ["sq.py"]


def test_new_untracked_code_counts_as_dirty(proj):
    (proj / "helper.py").write_text("x = 1\n")
    r = pt(proj, "run", "--", PY, "sq.py", check=False)
    assert r.returncode == 2 and "helper.py" in r.stderr


def test_rule_override_in_config_switches_dial_default(proj):
    cfg = (proj / "papertrail.toml").read_text() + "commit_before_compute = false\n"
    (proj / "papertrail.toml").write_text(cfg)
    (proj / "sq.py").write_text((proj / "sq.py").read_text() + "# edit\n")
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    e = ledger(proj)[-1]
    assert "commit_before_compute" not in e["settings"]["rules"]
    assert e["body"]["dirty"] == ["sq.py"]


def test_sketch_tier_does_not_enforce_commit(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    pt(tmp_path, "init", "--tier", "sketch", "--containment", "0")
    (tmp_path / "a.py").write_text("print(1)\n")
    pt(tmp_path, "run", "--", PY, "a.py")
    assert ledger(tmp_path)[-1]["body"]["dirty"] == ["a.py"]


def test_failed_run_is_recorded_and_exit_code_passed_through(proj):
    (proj / "bad.py").write_text("raise SystemExit(3)\n")
    sh(proj, "git", "add", "bad.py")
    sh(proj, "git", "commit", "-qm", "bad")
    r = pt(proj, "run", "--", PY, "bad.py", check=False)
    assert r.returncode == 3 and ledger(proj)[-1]["body"]["exit_code"] == 3


def test_verify_catches_an_edited_entry(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    p = proj / "labbook/ledger.jsonl"
    lines = p.read_text().splitlines()
    e = json.loads(lines[1])
    e["body"]["exit_code"] = 1
    lines[1] = json.dumps(e)
    p.write_text("\n".join(lines) + "\n")
    r = pt(proj, "verify", check=False)
    assert r.returncode == 1 and "do not match its hash" in r.stdout


def test_verify_catches_a_deleted_entry(proj):
    pt(proj, "note", "-m", "one")
    pt(proj, "note", "-m", "two")
    p = proj / "labbook/ledger.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[0], lines[2]]) + "\n")
    r = pt(proj, "verify", check=False)
    assert r.returncode == 1 and "does not link" in r.stdout


def test_verify_catches_a_changed_output(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    assert pt(proj, "verify").returncode == 0
    (proj / "out.txt").write_text("26\n")
    r = pt(proj, "verify", check=False)
    assert r.returncode == 1 and "out.txt: changed" in r.stdout


def test_deep_verify_reruns_and_reproduces(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    r = pt(proj, "verify", "--deep")
    assert "reproduced 1 outputs" in r.stdout


def test_deep_verify_catches_nondeterminism(proj):
    (proj / "rand.py").write_text("import random\nopen('r.txt','w').write(str(random.random()))\n")
    sh(proj, "git", "add", "rand.py")
    sh(proj, "git", "commit", "-qm", "rand")
    pt(proj, "run", "--out", "r.txt", "--", PY, "rand.py")
    r = pt(proj, "verify", "--deep", check=False)
    assert r.returncode == 1 and "did not reproduce" in r.stdout


def test_parents_link_automatically_through_matching_files(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    first = ledger(proj)[-1]["hash"]
    (proj / "dbl.py").write_text("open('out2.txt','w').write(str(2*int(open('out.txt').read())))\n")
    sh(proj, "git", "add", "dbl.py")
    sh(proj, "git", "commit", "-qm", "dbl")
    pt(proj, "run", "--in", "out.txt", "--out", "out2.txt", "--", PY, "dbl.py")
    assert first in ledger(proj)[-1]["parents"]


def test_correction_and_reconstruction_are_labelled(proj):
    pt(proj, "note", "-m", "found 25")
    old = ledger(proj)[-1]["hash"]
    pt(proj, "correct", "--supersedes", old[:8], "-m", "it was 24")
    c = ledger(proj)[-1]
    assert c["kind"] == "correction" and c["parents"] == [old]
    pt(proj, "reconstruct", "-m", "2019 search", "--built-from", "old log files", "--claimed-date", "2019-05")
    r = ledger(proj)[-1]
    assert r["body"]["reconstructed"] is True and r["body"]["claimed_date"] == "2019-05"
    assert pt(proj, "verify").returncode == 0


def test_seal_records_hash_not_contents(proj, tmp_path_factory):
    secret = tmp_path_factory.mktemp("private") / "idea.md"
    secret.write_text("a private idea\n")
    pt(proj, "seal", str(secret))
    e = ledger(proj)[-1]
    raw = (proj / "labbook/ledger.jsonl").read_text()
    assert e["kind"] == "seal" and len(e["body"]["sha256"]) == 64
    assert "private idea" not in raw and "idea.md" not in raw


def test_anchor_writes_head_file(proj):
    head = ledger(proj)[-1]["hash"]
    pt(proj, "anchor")
    a = ledger(proj)[-1]
    assert a["body"]["head"] == head and (proj / a["body"]["file"]).read_text().strip() == head
    assert pt(proj, "verify").returncode == 0


def test_entry_opens_one_file_per_question(proj):
    r = pt(proj, "entry", "Sum of squares")
    path = proj / r.stdout.strip()
    assert path.exists() and "## Supersedes" in path.read_text()
    assert path.name in (proj / "labbook/README.md").read_text()
    assert pt(proj, "entry", "Sum of squares", check=False).returncode == 2


def test_check_shows_rules_and_state(proj):
    r = pt(proj, "check")
    assert "Commit before you compute." in r.stdout and "chain intact" in r.stdout
    assert "[x] input data stays out of git" in r.stdout


def test_bad_config_is_reported_plainly(proj):
    (proj / "papertrail.toml").write_text('[levels]\ntier = "strict"\n')
    r = pt(proj, "check", check=False)
    assert r.returncode == 2 and "tier must be one of" in r.stderr


def test_unknown_rule_is_rejected(proj):
    (proj / "papertrail.toml").write_text((proj / "papertrail.toml").read_text() + "comit_before_compute = false\n")
    r = pt(proj, "check", check=False)
    assert r.returncode == 2 and "unknown rule" in r.stderr


def test_runs_from_a_subdirectory(proj):
    (proj / "sub").mkdir()
    (proj / "sub/w.py").write_text("open('w.txt','w').write('x')\n")
    sh(proj, "git", "add", "sub/w.py")
    sh(proj, "git", "commit", "-qm", "sub")
    pt(proj / "sub", "run", "--out", "sub/w.txt", "--", PY, "w.py")
    b = ledger(proj)[-1]["body"]
    assert b["cwd"] == "sub" and "sub/w.txt" in b["outputs"]
    assert "reproduced" in pt(proj, "verify", "--deep").stdout
