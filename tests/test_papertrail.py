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
    cfg = (proj / "papertrail.toml").read_text().replace("[rules]\n", "[rules]\ncommit_before_compute = false\n")
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
    assert "1 of 1 result-producing runs rerun and reproduced" in r.stdout


def test_deep_verify_catches_nondeterminism(proj):
    (proj / "rand.py").write_text("import random\nopen('r.txt','w').write(str(random.random()))\n")
    sh(proj, "git", "add", "rand.py")
    sh(proj, "git", "commit", "-qm", "rand")
    pt(proj, "run", "--out", "r.txt", "--", PY, "rand.py")
    before = (proj / "r.txt").read_text()
    r = pt(proj, "verify", "--deep", check=False)
    assert r.returncode == 1 and "did not reproduce" in r.stdout
    assert (proj / "r.txt").read_text() == before  # the original result is untouched
    assert pt(proj, "verify").returncode == 0


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
    (proj / "papertrail.toml").write_text((proj / "papertrail.toml").read_text().replace("[rules]\n", "[rules]\ncomit_before_compute = false\n"))
    r = pt(proj, "check", check=False)
    assert r.returncode == 2 and "unknown rule" in r.stderr


def test_runs_from_a_subdirectory(proj):
    (proj / "sub").mkdir()
    (proj / "sub/w.py").write_text("open('w.txt','w').write('x')\n")
    sh(proj, "git", "add", "sub/w.py")
    sh(proj, "git", "commit", "-qm", "sub")
    pt(proj / "sub", "run", "--out", "w.txt", "--", PY, "w.py")
    b = ledger(proj)[-1]["body"]
    assert b["cwd"] == "sub" and "sub/w.txt" in b["outputs"]
    assert "1 of 1" in pt(proj, "verify", "--deep").stdout


def test_several_outputs_after_shell_glob_expansion(proj):
    (proj / "two.py").write_text("open('a.csv','w').write('a'); open('b.csv','w').write('b')\n")
    sh(proj, "git", "add", "two.py")
    sh(proj, "git", "commit", "-qm", "two")
    pt(proj, "run", "--out", "a.csv", "b.csv", "--", PY, "two.py")
    assert set(ledger(proj)[-1]["body"]["outputs"]) == {"a.csv", "b.csv"}


def test_run_without_double_dash_is_refused(proj):
    r = pt(proj, "run", PY, "sq.py", check=False)
    assert r.returncode == 2 and "after --" in r.stderr and not (proj / "out.txt").exists()


def test_deep_still_reruns_after_results_are_committed(proj):
    pt(proj, "run", "--out", "out.txt", "--", PY, "sq.py")
    sh(proj, "git", "add", "-A")
    sh(proj, "git", "commit", "-qm", "results")
    assert "1 of 1" in pt(proj, "verify", "--deep").stdout


def test_truncation_after_an_anchor_is_caught(proj):
    pt(proj, "note", "-m", "a")
    pt(proj, "anchor")
    pt(proj, "note", "-m", "b")
    p = proj / "labbook/ledger.jsonl"
    p.write_text("\n".join(p.read_text().splitlines()[:2]) + "\n")
    r = pt(proj, "verify", check=False)
    assert r.returncode == 1 and "anchors/" in r.stdout


def test_tampered_anchor_file_is_caught(proj):
    pt(proj, "anchor")
    f = proj / ledger(proj)[-1]["body"]["file"]
    f.write_text("0" * 64 + "\n")
    assert pt(proj, "verify", check=False).returncode == 1


def test_deleted_code_file_is_dirty(proj):
    (proj / "helper.py").write_text("x=1\n")
    sh(proj, "git", "add", "helper.py")
    sh(proj, "git", "commit", "-qm", "helper")
    (proj / "helper.py").unlink()
    r = pt(proj, "run", "--", PY, "sq.py", check=False)
    assert r.returncode == 2 and "helper.py" in r.stderr


def test_no_commit_is_refused_at_reproducible(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    pt(tmp_path, "init", "--tier", "reproducible")
    (tmp_path / "a.txt").write_text("x")
    r = pt(tmp_path, "run", "--", PY, "-c", "print(1)", check=False)
    assert r.returncode == 2 and "no commit" in r.stderr


def test_out_outside_project_refused_before_running(proj):
    r = pt(proj, "run", "--out", "/tmp/x.txt", "--", PY, "sq.py", check=False)
    assert r.returncode == 2 and not (proj / "out.txt").exists()
    r = pt(proj, "run", "--out", "../x.txt", "--", PY, "sq.py", check=False)
    assert r.returncode == 2 and "outside the project" in r.stderr


def test_glob_characters_in_file_names_are_literal(proj):
    (proj / "data/s[1].csv").write_text("1\n")
    (proj / "data/s1.csv").write_text("other\n")
    pt(proj, "run", "--in", "data/s[1].csv", "--", PY, "sq.py")
    assert "data/s[1].csv" in ledger(proj)[-1]["body"]["inputs"]


def test_config_types_are_checked(proj):
    base = (proj / "papertrail.toml").read_text()
    (proj / "papertrail.toml").write_text(base.replace('inputs = ["data/*.txt"]', 'inputs = "data.csv"'))
    assert "list of strings" in pt(proj, "check", check=False).stderr
    (proj / "papertrail.toml").write_text(base.replace("[rules]\n", '[rules]\ncommit_before_compute = "false"\n'))
    assert "true or false" in pt(proj, "check", check=False).stderr
    (proj / "papertrail.toml").write_text(base.replace("containment = 1", "containment = 2.0"))
    assert "whole number" in pt(proj, "check", check=False).stderr


def test_garbage_ledger_line_is_reported_not_a_traceback(proj):
    with (proj / "labbook/ledger.jsonl").open("a") as f:
        f.write("[]\n")
    r = pt(proj, "verify", check=False)
    assert r.returncode in (1, 2) and "Traceback" not in r.stderr and "not a Paper Trail entry" in (r.stdout + r.stderr)


def test_seal_with_proof_keeps_a_copy(proj, tmp_path_factory):
    d = tmp_path_factory.mktemp("p")
    (d / "n.ots").write_bytes(b"proof")
    pt(proj, "seal", "--hash", "A" * 64, "--proof", str(d / "n.ots"))
    assert (proj / "labbook/seals" / ("a" * 64 + ".txt.ots")).read_bytes() == b"proof"
    assert pt(proj, "seal", "--hash", "b" * 64, "--proof", "missing.ots", check=False).returncode == 2


def _age(proj, hours):
    """Push every entry's time back by `hours` and rehash, to simulate the passage of time."""
    import hashlib
    from datetime import datetime, timedelta
    p = proj / "labbook/ledger.jsonl"
    out, prev = [], None
    for line in p.read_text().splitlines():
        e = json.loads(line)
        e["time"] = (datetime.fromisoformat(e["time"]) - timedelta(hours=hours)).isoformat(timespec="seconds")
        e["prev"] = prev
        body = {k: v for k, v in e.items() if k != "hash"}
        e["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        prev = e["hash"]
        out.append(json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    p.write_text("\n".join(out) + "\n")


def test_entry_closed_within_window_is_fine(proj):
    pt(proj, "entry", "Sum of squares")
    pt(proj, "run", "--question", "Sum of squares", "--out", "out.txt", "--", PY, "sq.py")
    r = pt(proj, "entry", "--close", next((proj / "labbook").glob("*sum-of-squares.md")).name)
    assert "closed" in r.stdout and "window" not in r.stdout
    assert "protocol:" not in pt(proj, "verify").stdout


def test_late_close_is_reported_with_the_window(proj):
    pt(proj, "entry", "Sum of squares")
    pt(proj, "run", "--question", "Sum of squares", "--out", "out.txt", "--", PY, "sq.py")
    _age(proj, 40)  # ledgered tier: 36 h window
    name = next((proj / "labbook").glob("*sum-of-squares.md")).name
    assert "window 36 h" in pt(proj, "entry", "--close", name).stdout
    assert "protocol:" in pt(proj, "verify").stdout


def test_window_is_tunable_in_config(proj):
    cfg = (proj / "papertrail.toml").read_text().replace("[windows]\n", "[windows]\nlabbook_hours = 72\n")
    (proj / "papertrail.toml").write_text(cfg)
    pt(proj, "entry", "Sum of squares")
    pt(proj, "run", "--question", "Sum of squares", "--out", "out.txt", "--", PY, "sq.py")
    _age(proj, 40)
    name = next((proj / "labbook").glob("*sum-of-squares.md")).name
    assert "window" not in pt(proj, "entry", "--close", name).stdout
    assert ledger(proj)[-1]["settings"]["windows"]["labbook_hours"] == 72
    assert "set in config" in pt(proj, "check").stdout


def test_editing_a_closed_entry_is_noticed(proj):
    pt(proj, "entry", "Sum of squares")
    path = next((proj / "labbook").glob("*sum-of-squares.md"))
    pt(proj, "entry", "--close", path.name)
    path.write_text(path.read_text() + "late addition\n")
    assert "changed since it was closed" in pt(proj, "verify").stdout


def test_bad_window_value_is_rejected(proj):
    cfg = (proj / "papertrail.toml").read_text().replace("[windows]\n", '[windows]\nlabbook_hours = "a day"\n')
    (proj / "papertrail.toml").write_text(cfg)
    assert "whole number of hours" in pt(proj, "check", check=False).stderr
