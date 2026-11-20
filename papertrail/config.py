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
    "anchor_head": ("tier", "sealed"),
    # containment level
    "data_out_of_git": ("containment", 1),
    "private_repo": ("containment", 2),
    "list_ai_inputs": ("containment", 3),
    "offline_only": ("containment", 4),
}

RULE_TEXT = {
    "log_runs": "every computation goes through `papertrail run`",
    "commit_before_compute": "code is committed before it computes",
    "capture_env": "the environment is recorded with each run",
    "hash_outputs": "outputs are hashed and chained",
    "verify_before_share": "`papertrail verify` passes before results are shared",
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
code = ["**/*.py", "**/*.jl", "**/*.sage", "**/*.sh"]
# Input data hashed into every run.
inputs = []
ledger = "labbook/ledger.jsonl"
labbook = "labbook"

[rules]
# Switch any single rule on or off, overriding the dials. For example:
# data_out_of_git = false
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
    raw: bytes = b""

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
    levels = data.get("levels", {})
    tier = levels.get("tier", "logged")
    if tier not in TIERS:
        raise ConfigError(f"tier must be one of {', '.join(TIERS)}, not {tier!r}")
    containment = levels.get("containment", 1)
    if containment not in CONTAINMENT:
        raise ConfigError(f"containment must be 0 to 4, not {containment!r}")
    rules = data.get("rules", {})
    unknown = set(rules) - set(RULES)
    if unknown:
        raise ConfigError(f"unknown rule(s) in [rules]: {', '.join(sorted(unknown))}")
    paths = data.get("paths", {})
    return Config(
        root=root,
        name=data.get("project", {}).get("name", root.name),
        tier=tier,
        containment=containment,
        code=list(paths.get("code", [])),
        inputs=list(paths.get("inputs", [])),
        ledger=root / paths.get("ledger", "labbook/ledger.jsonl"),
        labbook=root / paths.get("labbook", "labbook"),
        overrides={k: bool(v) for k, v in rules.items()},
        raw=raw,
    )
