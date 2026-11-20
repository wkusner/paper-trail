# Paper Trail

**Every number traces back to what made it.**

Paper Trail is a lab protocol and a small tool that enforces it. Wrap any command, in any language, with `papertrail run`, and it records the commit, the code, the inputs, the outputs and the environment in an append-only, hash-chained ledger. A lab book is kept alongside it, one entry per question. `papertrail verify` checks the whole chain and can rerun the work to the same bytes.

Each project chooses how strict to be with two dials: a **rigor tier** (sketch, logged, reproducible, ledgered, sealed) and a **containment level** (open, standard, private, restricted, air-gapped). Trusted dates come from anchoring the chain head with OpenTimestamps; private results can be sealed by hash, in the manner of [Under Seal].

It comes with a Claude skill, so Claude follows the protocol, checks it at the start and end of each session, and says plainly when a step broke it.

## Install
```
pip install git+https://github.com/<owner>/paper-trail
```
Python 3.11 or later; no other dependencies. For trusted timestamps, also install the OpenTimestamps client (`pip install opentimestamps-client`).

**As a Claude Code plugin:** `/plugin marketplace add <owner>/paper-trail`, then `/plugin install paper-trail@paper-trail`.
**As a Claude skill on its own:** upload the `skills/paper-trail` folder as a skill.

## Quick start
```
cd my-project                       # a git repository
papertrail init --tier ledgered --containment 1 --purpose "small sphere packings"
# edit papertrail.toml: which files are code, which are inputs
git add papertrail.toml labbook && git commit -m "Start the trail"

papertrail entry "Refine n=13"
papertrail run --out results/n13.csv --question "Refine n=13" -- python refine.py 13
papertrail verify --deep
git add labbook results && git commit -m "Refine n=13"
papertrail anchor
```

## Commands
| Command | Does |
|---|---|
| `init` | writes `papertrail.toml`, the lab book index and the genesis entry |
| `run [--out G] [--in G] [--parent H] [--allow-dirty] -- cmd` | runs a command and records it |
| `entry "title"` | opens a lab book entry for one question |
| `note -m "..."` | records a decision or observation |
| `correct --supersedes H -m "..."` | records a correction |
| `reconstruct -m "..." --built-from "..."` | records earlier work, labelled as reconstructed |
| `anchor` | timestamps the chain head |
| `seal FILE` or `seal --hash H [--proof P]` | records a private file's hash, not its contents |
| `verify [--deep]` | checks the chain and outputs; `--deep` reruns |
| `check` | shows the five rules, the rules in force and the project's state |

The protocol in full: [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Status
Version 0.1. The clean-room features (locked inputs, pre-registered builds, a gated channel with an information budget) are planned next.

## Origins
Generalized from a protocol first written for a topological data analysis project at Lawrence University, and part of the Lawrence generative lab.

[Under Seal]: https://lu-generative-lab.github.io/
