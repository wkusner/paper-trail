"""papertrail: a protocol wrapper that leaves a verifiable trail behind every result."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from . import __version__
from . import config as C
from . import gitenv as G
from . import ledger as L

FIVE_RULES = [
    ("Only through the trail.", "Computations that produce results run through `papertrail run`. No hand-made result tables."),
    ("Commit before you compute.", "Every run names the commit it ran at; uncommitted code is refused or recorded."),
    ("Append, never edit.", "The ledger and lab book only grow. A correction is a new entry naming what it supersedes."),
    ("One question, one lab book entry.", "Written the same day: question, inputs, commands, results, caveats, what it supersedes."),
    ("Verify before you share.", "`papertrail verify` passes before results go anywhere."),
]

ENTRY_TEMPLATE = """\
# {title}

{today} · ledger entries: (first 12 hex digits of each)

## Question
(One or two sentences.)

## Inputs
(Inputs by name and hash; the commit; the ledger entries used.)

## Method and commands
(Exactly what was run, so it can be rerun.)

## Results
(Numbers with units and their checks; one table where a table fits.)

## Findings
1.

## Caveats
(What is exploratory, what is not independent, what is missing.)

## Data problems found

## Supersedes
(Earlier findings this corrects, and how. The earlier entry gets one line pointing here; nothing else in it changes.)
"""


def die(msg: str, code: int = 2):
    print(f"papertrail: {msg}", file=sys.stderr)
    sys.exit(code)


def warn(msg: str):
    print(f"papertrail: warning: {msg}", file=sys.stderr)


def code_files(cfg: C.Config) -> list[Path]:
    return G.expand(cfg.root, cfg.code, exclude=[cfg.ledger])


def resolve_parents(entries, prefixes):
    try:
        return [L.resolve(entries, p)["hash"] for p in prefixes or []]
    except L.LedgerError as e:
        die(str(e))


def producers(entries: list[dict], files: dict[str, str]) -> list[str]:
    """Earlier runs whose recorded outputs match these inputs byte for byte."""
    wanted = set(files.items())
    out = []
    for e in entries:
        if e["kind"] == "run" and wanted & set(e["body"].get("outputs", {}).items()):
            out.append(e["hash"])
    return out


# --- commands ---------------------------------------------------------------

def cmd_init(a):
    root = Path.cwd().resolve()
    cfg_path = root / C.CONFIG_NAME
    if not cfg_path.exists():
        if a.tier not in C.TIERS:
            die(f"tier must be one of {', '.join(C.TIERS)}")
        if a.containment not in C.CONTAINMENT:
            die("containment must be 0 to 4")
        name = a.name or root.name
        cfg_path.write_text(C.DEFAULT_TOML.format(name=name.replace('"', "'"), tier=a.tier, containment=a.containment))
    try:
        cfg = C.load(root)
    except C.ConfigError as e:
        die(str(e))
    if L.read(cfg.ledger):
        die(f"{cfg.ledger.relative_to(root)} already exists; this project is already started")
    cfg.labbook.mkdir(parents=True, exist_ok=True)
    index = cfg.labbook / "README.md"
    if not index.exists():
        index.write_text(f"# Lab book: {cfg.name}\n\nOne entry per question, newest last.\n\n")
    e = L.append(cfg.ledger, "genesis", {"name": cfg.name, "purpose": a.purpose or "", "papertrail": __version__}, cfg.settings())
    print(f"started {cfg.name}: tier {cfg.tier}, containment {cfg.containment} ({C.CONTAINMENT[cfg.containment]})")
    print(f"genesis {e['hash'][:12]}; commit {C.CONFIG_NAME} and {cfg.labbook.relative_to(root)}/ next")


def cmd_run(a):
    cfg = C.load()
    if not a.command:
        die("give a command after --, e.g. papertrail run --out results.csv -- python fit.py")
    entries = L.read(cfg.ledger)
    if not entries:
        die("no ledger yet; run `papertrail init`")
    code = code_files(cfg)
    dirty = G.dirty_code(cfg.root, code)
    if dirty and cfg.rule("commit_before_compute") and not a.allow_dirty:
        die("uncommitted code; commit first (or pass --allow-dirty, which is recorded):\n  " + "\n  ".join(dirty))
    inputs = G.expand(cfg.root, cfg.inputs + (a.inputs or []))
    in_hashes = G.hashes(cfg.root, inputs)
    in_git = G.tracked(cfg.root, inputs)
    if in_git and cfg.rule("data_out_of_git"):
        warn("input data is tracked in git, against data_out_of_git: " + ", ".join(in_git))
    if cfg.rule("hash_outputs") and not a.outputs:
        warn("this tier hashes outputs; name them with --out")
    commit = G.commit(cfg.root)
    started = L.now()
    t0 = time.monotonic()
    try:
        rc = subprocess.run(a.command, cwd=Path.cwd()).returncode
    except FileNotFoundError:
        die(f"command not found: {a.command[0]}")
    seconds = round(time.monotonic() - t0, 3)
    outs = G.expand(cfg.root, a.outputs or [])
    if a.outputs and not outs:
        warn("no files matched --out")
    body = {
        "command": a.command,
        "cwd": str(Path.cwd().resolve().relative_to(cfg.root)),
        "question": a.question or "",
        "commit": commit,
        "dirty": dirty,
        "allow_dirty": bool(a.allow_dirty),
        "code": G.hashes(cfg.root, code),
        "inputs": in_hashes,
        "outputs": G.hashes(cfg.root, outs),
        "exit_code": rc,
        "started": started,
        "seconds": seconds,
    }
    if cfg.rule("capture_env"):
        body["env"] = G.environment(cfg.root)
    parents = resolve_parents(entries, a.parent) + producers(entries, in_hashes)
    e = L.append(cfg.ledger, "run", body, cfg.settings(), parents)
    status = "ok" if rc == 0 else f"exit {rc}"
    print(f"papertrail: run {e['hash'][:12]} recorded ({status}, {len(body['outputs'])} outputs, {seconds}s)", file=sys.stderr)
    sys.exit(rc)


def cmd_note(a):
    cfg = C.load()
    entries = L.read(cfg.ledger)
    e = L.append(cfg.ledger, "note", {"text": a.message}, cfg.settings(), resolve_parents(entries, a.parent))
    print(f"note {e['hash'][:12]}")


def cmd_correct(a):
    cfg = C.load()
    entries = L.read(cfg.ledger)
    old = resolve_parents(entries, [a.supersedes])[0]
    e = L.append(cfg.ledger, "correction", {"supersedes": old, "text": a.message}, cfg.settings(), [old])
    print(f"correction {e['hash'][:12]} supersedes {old[:12]}")
    print("add one line to the old lab book entry pointing to the new one; change nothing else in it")


def cmd_reconstruct(a):
    cfg = C.load()
    entries = L.read(cfg.ledger)
    outs = G.expand(cfg.root, a.outputs or [])
    ins = G.expand(cfg.root, a.inputs or [])
    body = {
        "reconstructed": True,
        "command": a.command,
        "claimed_date": a.claimed_date or "",
        "built_from": a.built_from,
        "text": a.message,
        "commit": a.commit or "",
        "inputs": G.hashes(cfg.root, ins),
        "outputs": G.hashes(cfg.root, outs),
    }
    e = L.append(cfg.ledger, "run", body, cfg.settings(), resolve_parents(entries, a.parent))
    print(f"reconstructed run {e['hash'][:12]} (recorded today; claimed date {a.claimed_date or 'not given'})")


def cmd_entry(a):
    cfg = C.load()
    slug = re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-") or "entry"
    today = date.today().isoformat()
    path = cfg.labbook / f"{today}-{slug}.md"
    if path.exists():
        die(f"{path.relative_to(cfg.root)} already exists; one question, one entry")
    cfg.labbook.mkdir(parents=True, exist_ok=True)
    path.write_text(ENTRY_TEMPLATE.format(title=a.title, today=today))
    with (cfg.labbook / "README.md").open("a") as f:
        f.write(f"- {today}: [{a.title}]({path.name})\n")
    L.append(cfg.ledger, "note", {"text": f"opened lab book entry {path.name}", "labbook_entry": path.name}, cfg.settings())
    print(path.relative_to(cfg.root))


def _stamp(path: Path) -> bool:
    if shutil.which("ots") is None:
        return False
    r = subprocess.run(["ots", "stamp", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        warn("ots stamp failed: " + r.stderr.strip())
        return False
    return True


def cmd_anchor(a):
    cfg = C.load()
    entries = L.read(cfg.ledger)
    head = entries[-1]["hash"]
    d = cfg.labbook / "anchors"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{entries[-1]['seq']:05d}-{head[:12]}.txt"
    f.write_text(head + "\n")
    stamped = _stamp(f)
    e = L.append(cfg.ledger, "anchor", {"head": head, "file": str(f.relative_to(cfg.root)), "ots": stamped}, cfg.settings(), [head])
    print(f"anchor {e['hash'][:12]} for head {head[:12]}")
    if stamped:
        print(f"stamped {f.name}.ots; run `ots upgrade` on it in a few hours, then commit it")
    else:
        print(f"no OpenTimestamps client found; stamp {f.relative_to(cfg.root)} with `ots stamp` (or with Under Seal), then commit the .ots file")


def cmd_seal(a):
    cfg = C.load()
    if bool(a.file) == bool(a.hash):
        die("give a file or --hash, not both")
    digest = G.sha256_file(Path(a.file)) if a.file else a.hash.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        die("--hash must be a 64-digit SHA-256")
    d = cfg.labbook / "seals"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{digest}.txt"
    f.write_text(digest + "\n")
    body = {"sha256": digest, "label": a.label or "", "file": str(f.relative_to(cfg.root))}
    if a.proof:
        body["proof_sha256"] = G.sha256_file(Path(a.proof))
        body["ots"] = True
    else:
        body["ots"] = _stamp(f)
    e = L.append(cfg.ledger, "seal", body, cfg.settings())
    print(f"seal {e['hash'][:12]} for {digest[:12]}; the sealed file's contents are not recorded")
    if not body["ots"]:
        print(f"no timestamp proof yet; stamp {f.relative_to(cfg.root)} with `ots stamp` or Under Seal")


def verify(cfg: C.Config, deep: bool) -> tuple[list[str], list[str]]:
    problems, notes = [], []
    try:
        entries = L.read(cfg.ledger)
    except L.LedgerError as e:
        return [str(e)], notes
    if not entries:
        return ["the ledger is empty"], notes
    problems += L.check_chain(entries)
    latest: dict[str, tuple[str, dict]] = {}
    for e in entries:
        if e["kind"] == "run" and not e["body"].get("reconstructed"):
            for path, h in e["body"].get("outputs", {}).items():
                latest[path] = (h, e)
    for path, (h, e) in sorted(latest.items()):
        p = cfg.root / path
        if not p.exists():
            notes.append(f"{path}: missing (last written by run {e['hash'][:12]})")
        elif G.sha256_file(p) != h:
            problems.append(f"{path}: changed since run {e['hash'][:12]} recorded it")
    for e in entries:
        if e["kind"] in ("anchor", "seal"):
            f = cfg.root / e["body"]["file"]
            if not f.exists():
                problems.append(f"{e['body']['file']}: missing ({e['kind']} {e['hash'][:12]})")
    if deep:
        head = G.commit(cfg.root)
        writers = {e["hash"]: e for _, e in latest.values()}
        for e in sorted(writers.values(), key=lambda e: e["seq"]):
            b = e["body"]
            tag = f"run {e['hash'][:12]}"
            if b.get("exit_code") != 0:
                notes.append(f"{tag}: not rerun (it failed originally)")
                continue
            if b.get("commit") != head or b.get("dirty"):
                notes.append(f"{tag}: not rerun (made at {str(b.get('commit'))[:12]}{', dirty' if b.get('dirty') else ''}; HEAD is {str(head)[:12]})")
                continue
            if G.dirty_code(cfg.root, code_files(cfg)):
                notes.append(f"{tag}: not rerun (code has uncommitted changes)")
                continue
            if G.hashes(cfg.root, G.expand(cfg.root, list(b["inputs"]))) != b["inputs"]:
                notes.append(f"{tag}: not rerun (its inputs have changed)")
                continue
            rc = subprocess.run(b["command"], cwd=cfg.root / b["cwd"], capture_output=True).returncode
            now_out = {p: G.sha256_file(cfg.root / p) for p in b["outputs"] if (cfg.root / p).exists()}
            if rc != 0 or now_out != b["outputs"]:
                problems.append(f"{tag}: rerun did not reproduce its outputs byte for byte")
            else:
                notes.append(f"{tag}: rerun reproduced {len(now_out)} outputs")
    return problems, notes


def cmd_verify(a):
    cfg = C.load()
    problems, notes = verify(cfg, a.deep)
    for n in notes:
        print("  note: " + n)
    for p in problems:
        print("  FAIL: " + p)
    if problems:
        print(f"verify failed: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"verify passed: {len(L.read(cfg.ledger))} entries{' (deep)' if a.deep else ''}")


def cmd_check(a):
    cfg = C.load()
    print(f"Paper Trail · {cfg.name} · tier {cfg.tier} · containment {cfg.containment} ({C.CONTAINMENT[cfg.containment]})\n")
    print("The five rules")
    for i, (head, text) in enumerate(FIVE_RULES, 1):
        print(f"  {i}. {head} {text}")
    print("\nRules in force")
    for r, on in cfg.rules().items():
        src = " (set in config)" if r in cfg.overrides else ""
        print(f"  [{'x' if on else ' '}] {C.RULE_TEXT[r]}{src}")
    entries = L.read(cfg.ledger)
    chain = L.check_chain(entries) if entries else ["the ledger is empty"]
    print("\nState")
    print(f"  commit: {(G.commit(cfg.root) or 'none')[:12]}")
    dirty = G.dirty_code(cfg.root, code_files(cfg))
    print(f"  uncommitted code: {', '.join(dirty) if dirty else 'none'}")
    print(f"  ledger: {len(entries)} entries; chain {'intact' if not chain else 'BROKEN'}")
    for p in chain:
        print(f"    {p}")
    led = G.git(cfg.root, "status", "--porcelain", "--", str(cfg.ledger.relative_to(cfg.root)))
    if led:
        print("  ledger has uncommitted entries: commit it with the results and lab book entry")
    if entries:
        last = entries[-1]
        print(f"  last entry: {last['kind']} {last['hash'][:12]} at {last['time']}")
        anchors = [e["seq"] for e in entries if e["kind"] == "anchor"]
        since = len(entries) - 1 - (anchors[-1] if anchors else -1)
        if cfg.rule("anchor_head") and since > 0:
            print(f"  {since} entries since the last anchor: run `papertrail anchor`")
    sys.exit(1 if chain else 0)


def main(argv=None):
    p = argparse.ArgumentParser(prog="papertrail", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="start a project: config, lab book, genesis entry")
    s.add_argument("--name")
    s.add_argument("--purpose")
    s.add_argument("--tier", default="logged")
    s.add_argument("--containment", type=int, default=1)
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("run", help="run a command and record it: papertrail run [options] -- command")
    s.add_argument("--out", dest="outputs", action="append", help="output file or glob (repeatable)")
    s.add_argument("--in", dest="inputs", action="append", help="extra input file or glob (repeatable)")
    s.add_argument("--parent", action="append", help="hash prefix of an entry this run builds on")
    s.add_argument("--question", help="lab book entry or short question this run serves")
    s.add_argument("--allow-dirty", action="store_true", help="run with uncommitted code; recorded")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("note", help="record a note")
    s.add_argument("-m", "--message", required=True)
    s.add_argument("--parent", action="append")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("correct", help="record a correction that supersedes an earlier entry")
    s.add_argument("--supersedes", required=True)
    s.add_argument("-m", "--message", required=True)
    s.set_defaults(fn=cmd_correct)

    s = sub.add_parser("reconstruct", help="record work done before the trail existed, labelled as reconstructed")
    s.add_argument("-m", "--message", required=True, help="what was done")
    s.add_argument("--built-from", required=True, help="what this record is reconstructed from (notes, emails, old logs)")
    s.add_argument("--command", default="", help="the command as best known")
    s.add_argument("--claimed-date", help="when the work was originally done, as best known")
    s.add_argument("--commit", help="the commit it was done at, if known")
    s.add_argument("--out", dest="outputs", action="append")
    s.add_argument("--in", dest="inputs", action="append")
    s.add_argument("--parent", action="append")
    s.set_defaults(fn=cmd_reconstruct)

    s = sub.add_parser("entry", help="open a lab book entry for one question")
    s.add_argument("title")
    s.set_defaults(fn=cmd_entry)

    s = sub.add_parser("anchor", help="timestamp the chain head")
    s.set_defaults(fn=cmd_anchor)

    s = sub.add_parser("seal", help="record a private file's hash without its contents")
    s.add_argument("file", nargs="?")
    s.add_argument("--hash", help="a SHA-256 already computed (e.g. by Under Seal)")
    s.add_argument("--proof", help="an existing .ots proof for it")
    s.add_argument("--label", help="a public label (optional; leave out to reveal nothing)")
    s.set_defaults(fn=cmd_seal)

    s = sub.add_parser("verify", help="check the chain and the recorded outputs")
    s.add_argument("--deep", action="store_true", help="also rerun commands and compare outputs byte for byte")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("check", help="show the rules, the dials and the project's state")
    s.set_defaults(fn=cmd_check)

    a = p.parse_args(argv)
    if a.cmd == "run" and a.command and a.command[0] == "--":
        a.command = a.command[1:]
    try:
        a.fn(a)
    except (C.ConfigError, L.LedgerError) as e:
        die(str(e))


if __name__ == "__main__":
    main()
