"""Project configuration: the two dials (rigor tier, containment level) and rule overrides."""
from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "papertrail.toml"

TIERS = ["sketch", "logged", "reproducible", "ledgered", "sealed"]
CONTAINMENT = {0: "open", 1: "standard", 2: "private", 3: "restricted", 4: "air-gapped"}

# rule -> (dial, minimum level at which it is on by default)
RULES = {
    # rigor tier
    "log_runs": ("tier", "logged"),
    "commit_before_compute": ("tier", "reproducible"),
    "capture_env": ("tier", "reproducible"),
    "hash_outputs": ("tier", "ledgered"),
    "verify_before_share": ("tier", "ledgered"),
    "labbook_on_time": ("tier", "reproducible"),
    "anchor_head": ("tier", "sealed"),
    # containment level
    "data_out_of_git": ("containment", 1),
    "private_repo": ("containment", 2),
    "list_ai_inputs": ("containment", 3),
    "offline_only": ("containment", 4),
}

# Time windows, in hours, by rigor tier. Each can be set under [windows].
WINDOWS = {
    # a lab book entry is closed within this many hours of the last run it reports
    "labbook_hours": {"sketch": 168, "logged": 72, "reproducible": 48, "ledgered": 36, "sealed": 24},
    # at most this many hours between new entries and the next anchor (only when anchor_head is on)
    "anchor_hours": {"sketch": 0, "logged": 0, "reproducible": 0, "ledgered": 168, "sealed": 24},
}

WINDOW_TEXT = {
    "labbook_hours": "lab book entries are closed within {h} hours of their last run",
    "anchor_hours": "new entries are anchored within {h} hours",
}

RULE_TEXT = {
    "log_runs": "every computation goes through `papertrail run`",
    "commit_before_compute": "code is committed before it computes",
    "capture_env": "the environment is recorded with each run",
    "hash_outputs": "outputs are hashed and chained",
    "verify_before_share": "`papertrail verify` passes before results are shared",
    "labbook_on_time": "lab book entries are closed within the window (see [windows])",
    "anchor_head": "the chain head is anchored with a trusted timestamp",
    "data_out_of_git": "input data stays out of git; only hashes and manifests are committed",
    "private_repo": "the repository is private; only hashes go public",
    "list_ai_inputs": "AI tools see only listed inputs",
    "offline_only": "work happens on an offline machine; transfers are logged",
}

DEFAULT_TOML = """\
# Paper Trail configuration. See docs/PROTOCOL.md.

[project]
name = "{name}"

[levels]
# Rigor tier: sketch | logged | reproducible | ledgered | sealed
tier = "{tier}"
# Containment: 0 open | 1 standard | 2 private | 3 restricted | 4 air-gapped
containment = {containment}

[paths]
# Files whose changes matter to results (glob patterns, relative to the project root).
# Inside git, files git ignores are never treated as code.
code = ["**/*.py", "**/*.jl", "**/*.sage", "**/*.sh", "**/*.R", "**/*.ipynb",
        "**/*.c", "**/*.cpp", "**/*.h", "**/*.rs", "**/*.m", "**/*.gp", "**/*.mpl"]
# Input data hashed into every run.
inputs = []
ledger = "labbook/ledger.jsonl"
labbook = "labbook"

[rules]
# Switch any single rule on or off, overriding the dials. For example:
# data_out_of_git = false

[windows]
# Hours, overriding the tier's defaults (0 turns a window off). For example:
# labbook_hours = 36   # a day and a half, so work logged after midnight still counts
# anchor_hours = 24
"""


@dataclass
class Config:
    root: Path
    name: str
    tier: str
    containment: int
    code: list[str]
    inputs: list[str]
    ledger: Path
    labbook: Path
    overrides: dict[str, bool] = field(default_factory=dict)
    window_overrides: dict[str, int] = field(default_factory=dict)
    raw: bytes = b""

    def window(self, name: str) -> int:
        return self.window_overrides.get(name, WINDOWS[name][self.tier])

    def windows(self) -> dict[str, int]:
        return {w: self.window(w) for w in WINDOWS}

    def rule(self, name: str) -> bool:
        if name in self.overrides:
            return bool(self.overrides[name])
        dial, minimum = RULES[name]
        if dial == "tier":
            return TIERS.index(self.tier) >= TIERS.index(minimum)
        return self.containment >= minimum

    def rules(self) -> dict[str, bool]:
        return {r: self.rule(r) for r in RULES}

    def settings(self) -> dict:
        """What goes into every ledger entry: the dials, the rules in force, the config hash."""
        return {
            "tier": self.tier,
            "containment": self.containment,
            "rules": sorted(r for r, on in self.rules().items() if on),
            "windows": self.windows(),
            "config_sha256": hashlib.sha256(self.raw).hexdigest(),
        }


class ConfigError(Exception):
    pass


def find_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / CONFIG_NAME).exists():
            return d
    raise ConfigError(f"no {CONFIG_NAME} here or above; run `papertrail init` first")


def load(root: Path | None = None) -> Config:
    root = root or find_root()
    raw = (root / CONFIG_NAME).read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{CONFIG_NAME}: {e}") from e
    def table(key):
        t = data.get(key, {})
        if not isinstance(t, dict):
            raise ConfigError(f"[{key}] must be a table")
        return t

    levels, paths, rules, windows = table("levels"), table("paths"), table("rules"), table("windows")
    unknown_w = set(windows) - set(WINDOWS)
    if unknown_w:
        raise ConfigError(f"unknown window(s) in [windows]: {', '.join(sorted(unknown_w))}")
    for k, v in windows.items():
        if type(v) is not int or v < 0:
            raise ConfigError(f"[windows] {k} must be a whole number of hours, not {v!r}")
    tier = levels.get("tier", "logged")
    if tier not in TIERS:
        raise ConfigError(f"tier must be one of {', '.join(TIERS)}, not {tier!r}")
    containment = levels.get("containment", 1)
    if type(containment) is not int or containment not in CONTAINMENT:
        raise ConfigError(f"containment must be a whole number 0 to 4, not {containment!r}")
    unknown = set(rules) - set(RULES)
    if unknown:
        raise ConfigError(f"unknown rule(s) in [rules]: {', '.join(sorted(unknown))}")
    for k, v in rules.items():
        if not isinstance(v, bool):
            raise ConfigError(f"[rules] {k} must be true or false (no quotes), not {v!r}")

    def globs(key):
        v = paths.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ConfigError(f'[paths] {key} must be a list of strings, e.g. {key} = ["{v}"]' if isinstance(v, str)
                              else f"[paths] {key} must be a list of strings")
        return v

    def relpath(key, default):
        v = paths.get(key, default)
        if not isinstance(v, str) or Path(v).is_absolute() or ".." in Path(v).parts:
            raise ConfigError(f"[paths] {key} must be a path inside the project, not {v!r}")
        return root / v

    name = table("project").get("name", root.name)
    return Config(
        root=root,
        name=str(name),
        tier=tier,
        containment=containment,
        code=globs("code"),
        inputs=globs("inputs"),
        ledger=relpath("ledger", "labbook/ledger.jsonl"),
        labbook=relpath("labbook", "labbook"),
        overrides=dict(rules),
        window_overrides=dict(windows),
        raw=raw,
    )
