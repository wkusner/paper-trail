"""The append-only, hash-chained ledger (JSON Lines)."""
from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

KINDS = {"genesis", "run", "note", "correction", "anchor", "seal"}


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(canonical(body)).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise LedgerError(f"line {n} is not valid JSON: {e}") from e
    return out


class LedgerError(Exception):
    pass


def resolve(entries: list[dict], prefix: str) -> dict:
    """Find one entry by a hash prefix (at least 6 hex digits)."""
    if len(prefix) < 6:
        raise LedgerError("give at least 6 hex digits of the entry hash")
    hits = [e for e in entries if e.get("hash", "").startswith(prefix)]
    if not hits:
        raise LedgerError(f"no entry starts with {prefix}")
    if len(hits) > 1:
        raise LedgerError(f"{prefix} matches {len(hits)} entries; give more digits")
    return hits[0]


def append(path: Path, kind: str, body: dict, settings: dict, parents: list[str] | None = None) -> dict:
    """Append one entry, chained to the last. Locks the file so two runs cannot interleave."""
    if kind not in KINDS:
        raise LedgerError(f"unknown entry kind {kind!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            lines = [l for l in f.read().splitlines() if l.strip()]
            prev = json.loads(lines[-1]) if lines else None
            entry = {
                "seq": (prev["seq"] + 1) if prev else 0,
                "kind": kind,
                "time": now(),
                "prev": prev["hash"] if prev else None,
                "parents": sorted(set(parents or [])),
                "settings": settings,
                "body": body,
            }
            entry["hash"] = entry_hash(entry)
            f.seek(0, 2)
            f.write(canonical(entry).decode("utf-8") + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return entry


def check_chain(entries: list[dict]) -> list[str]:
    """Problems with the chain itself: edited entries, broken links, unknown parents."""
    problems = []
    seen = set()
    prev = None
    for i, e in enumerate(entries):
        label = f"entry {e.get('seq', i)}"
        if e.get("seq") != i:
            problems.append(f"{label}: sequence number should be {i}")
        if e.get("hash") != entry_hash(e):
            problems.append(f"{label}: contents do not match its hash (edited after writing?)")
        if e.get("prev") != (prev["hash"] if prev else None):
            problems.append(f"{label}: does not link to the entry before it")
        for p in e.get("parents", []):
            if p not in seen:
                problems.append(f"{label}: parent {p[:12]} is not an earlier entry")
        if i == 0 and e.get("kind") != "genesis":
            problems.append("the first entry is not a genesis entry")
        seen.add(e.get("hash"))
        prev = e
    return problems
