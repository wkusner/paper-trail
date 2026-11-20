# Paper Trail

**Every number traces back to what made it.**

Paper Trail is a lab protocol and a small tool that enforces it. Wrap any command, in any language, with `papertrail run`, and it records the commit, the code, the inputs, the outputs and the environment in an append-only, hash-chained ledger. A lab book is kept alongside it, one entry per question. `papertrail verify` checks the whole chain, and `verify --deep` reruns the work in a scratch checkout and checks it reproduces to the same bytes.

Each project chooses how strict to be with two dials, which set standard defaults for every rule and time window (any of them can then be tuned): a **rigor tier** (sketch, logged, reproducible, ledgered, sealed) and a **containment level** (open, standard, private, restricted, air-gapped). Trusted dates come from anchoring the chain head with OpenTimestamps; private results can be sealed by hash, like a sealed envelope deposited with a date.

It comes with two Claude skills:
- **paper-trail**: Claude follows the protocol, checks it at the start and end of each session, and says plainly when a step broke it.
- **muscle-memory**: Claude notices when a step it keeps doing by reasoning (counting, checking a rule, date math) should be a tool instead, and says so in a line, with the payoff.

## Tools before talk
A model call is the right way to draft, review or decide. It is the wrong way to count, hash, compare dates or check a written rule: it costs something every time, can answer differently when asked twice, and leaves no test behind. Paper Trail is the protocol made into a tool for exactly that reason, and the muscle-memory skill keeps finding the next candidates. Build the smallest tool that works, on the third time a step comes up, and keep a list of the rest.

## Install
```
pip install git+https://github.com/<owner>/paper-trail
```
Python 3.11 or later on macOS or Linux (not Windows yet); no other dependencies. For trusted timestamps, also install the OpenTimestamps client (`pip install opentimestamps-client`).

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
| `run [--out F...] [--in F...] [--parent H] [--allow-dirty] -- cmd` | runs a command and records it; paths are relative to where you are |
| `entry "title"`, `entry --close FILE` | opens a lab book entry for one question; closes it, recording its hash and the time |
| `note -m "..."` | records a decision or observation |
| `correct --supersedes H -m "..."` | records a correction |
| `reconstruct -m "..." --built-from "..."` | records earlier work, labelled as reconstructed |
| `anchor` | timestamps the chain head |
| `seal FILE` or `seal --hash H [--proof P]` | records a private file's hash, not its contents |
| `verify [--deep]` | checks the chain and outputs; `--deep` reruns |
| `check` | shows the five rules, the rules in force and the project's state |

The protocol in full: [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Status
Version 0.1. Planned next, in [docs/ROADMAP.md](docs/ROADMAP.md): an AI work ledger (models, tokens, tallies), clean-room builds, and hooks.

## Origins
Generalized from a protocol first written for a topological data analysis project at Lawrence University, and part of the Lawrence generative lab.

