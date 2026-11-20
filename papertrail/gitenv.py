"""Git state, path resolution, file hashing and environment capture."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

LOCKFILES = [
    "uv.lock", "poetry.lock", "requirements.txt", "environment.yml", "Pipfile.lock",
    "Manifest.toml", "Project.toml", "package-lock.json", "renv.lock",
]


def git(root: Path, *args: str, raw: bool = False) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
        return r.stdout if raw else r.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def is_repo(root: Path) -> bool:
    return git(root, "rev-parse", "--is-inside-work-tree") == "true"


def commit(root: Path) -> str | None:
    return git(root, "rev-parse", "--verify", "-q", "HEAD")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def matches(path: str, patterns: list[str]) -> bool:
    """Glob match on a root-relative POSIX path; '**/' also matches at the top level."""
    for pat in patterns:
        if fnmatchcase(path, pat) or (pat.startswith("**/") and fnmatchcase(path, pat[3:])):
            return True
    return False


class PathError(Exception):
    pass


def to_root(root: Path, cwd: Path, pattern: str) -> str:
    """A path or glob given relative to cwd, rewritten relative to the project root."""
    if Path(pattern).is_absolute():
        raise PathError(f"{pattern}: give paths inside the project, relative to where you are")
    joined = os.path.normpath(os.path.join(os.path.relpath(cwd, root), pattern))
    if joined == ".." or joined.startswith("../"):
        raise PathError(f"{pattern}: outside the project")
    return Path(joined).as_posix()


def expand(root: Path, patterns: list[str], exclude: list[Path] = ()) -> list[Path]:
    """Root-relative patterns to existing files. A pattern naming an existing file is taken literally."""
    skip = {p.resolve() for p in exclude}
    found = set()
    for pat in patterns:
        literal = root / pat
        hits = [literal] if literal.is_file() else [p for p in root.glob(pat) if p.is_file()]
        for p in hits:
            if ".git" not in p.relative_to(root).parts and p.resolve() not in skip:
                found.add(p)
    return sorted(found)


def project_files(root: Path) -> list[str] | None:
    """Tracked files plus untracked files that git does not ignore (None outside git)."""
    out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", raw=True)
    if out is None:
        return None
    return sorted({p for p in out.split("\0") if p})


def code_files(root: Path, patterns: list[str], exclude: list[Path] = ()) -> list[Path]:
    """Code is any non-ignored file matching the code globs (inside git); plain globs outside git."""
    files = project_files(root)
    if files is None:
        return expand(root, patterns, exclude)
    skip = {p.resolve() for p in exclude}
    return [root / f for f in files if matches(f, patterns) and (root / f).is_file() and (root / f).resolve() not in skip]


def dirty_code(root: Path, patterns: list[str]) -> list[str]:
    """Code paths that differ from HEAD: modified, staged, untracked, deleted or renamed."""
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=all", raw=True)
    if out is None:
        return ["(not a git repository)"]
    dirty = set()
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        rec = parts[i]
        i += 1
        if len(rec) < 4:
            continue
        status, path = rec[:2], rec[3:]
        if "R" in status or "C" in status:
            old = parts[i]
            i += 1
            if matches(old, patterns):
                dirty.add(old)
        if matches(path, patterns):
            dirty.add(path)
    return sorted(dirty)


def tracked(root: Path, files: list[Path]) -> list[str]:
    if not files:
        return []
    rel = [str(p.relative_to(root)) for p in files]
    out = git(root, "ls-files", "--", *rel)
    return sorted(out.splitlines()) if out else []


def hashes(root: Path, files: list[Path]) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in files}


def environment(root: Path) -> dict:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "lockfiles": hashes(root, [root / n for n in LOCKFILES if (root / n).is_file()]),
    }
    for var in ("CONDA_DEFAULT_ENV", "VIRTUAL_ENV", "JULIA_PROJECT"):
        if os.environ.get(var):
            env[var] = os.environ[var]
    return env


def text(arg: str) -> str:
    """Make any argv string safe to store as UTF-8 JSON."""
    return os.fsencode(arg).decode("utf-8", "backslashreplace")
