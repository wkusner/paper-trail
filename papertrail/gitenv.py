"""Git state, file hashing and environment capture."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
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


def commit(root: Path) -> str | None:
    return git(root, "rev-parse", "HEAD")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expand(root: Path, patterns: list[str], exclude: list[Path] = ()) -> list[Path]:
    skip = {p.resolve() for p in exclude}
    found = set()
    for pat in patterns:
        for p in root.glob(pat):
            if p.is_file() and ".git" not in p.relative_to(root).parts and p.resolve() not in skip:
                found.add(p)
    return sorted(found)


def hashes(root: Path, files: list[Path]) -> dict[str, str]:
    return {str(p.relative_to(root)): sha256_file(p) for p in files}


def dirty_code(root: Path, code_files: list[Path]) -> list[str]:
    """Code files that are modified, staged or untracked relative to HEAD."""
    if not code_files:
        return []
    rel = [str(p.relative_to(root)) for p in code_files]
    # raw: porcelain lines start with a status column that may be a space
    out = git(root, "status", "--porcelain", "--untracked-files=all", "--", *rel, raw=True)
    if out is None:
        return ["(not a git repository)"]
    return sorted(line[3:] for line in out.splitlines() if line.strip())


def tracked(root: Path, files: list[Path]) -> list[str]:
    if not files:
        return []
    rel = [str(p.relative_to(root)) for p in files]
    out = git(root, "ls-files", "--", *rel)
    return sorted(out.splitlines()) if out else []


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
