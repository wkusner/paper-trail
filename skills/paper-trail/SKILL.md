---
name: paper-trail
description: Use when working in a project that has a papertrail.toml, or when asked to start a lab protocol, log runs, keep a lab book, verify results, anchor or seal work with Paper Trail.
---

# Paper Trail

Every number a project reports must trace back, by hash, to the exact code, inputs and environment that made it, and anyone must be able to check that trail. The tool is `papertrail` (install: `pip install git+https://github.com/<owner>/paper-trail`). The readable protocol is `docs/PROTOCOL.md` in the Paper Trail repository.

## At the start and end of every session
1. Run `papertrail check`. Show the person the five rules and the rules in force, in a few lines.
2. Say plainly if anything is off: uncommitted code, a broken chain, uncommitted ledger entries, entries since the last anchor when the tier is `sealed`.
At the end, run `papertrail check` again, and `papertrail verify` if results were produced.

## The five rules
1. **Only through the trail.** Computations that produce results run through `papertrail run`. Never type up a result table by hand.
2. **Commit before you compute.** Commit the code first. Use `--allow-dirty` only for trying things out, say so, and do not report its results.
3. **Append, never edit.** Never edit or delete lines of the ledger or past lab book entries. Corrections are `papertrail correct --supersedes <hash> -m "..."`, plus one pointer line in the old lab book entry.
4. **One question, one lab book entry.** `papertrail entry "short title"`, pass the same title to `--question` on its runs, fill every section, and close it with `papertrail entry --close <file>` within the window `papertrail check` shows.
5. **Verify before you share.** `papertrail verify` (and `--deep` when it matters) passes before results leave the project. Shared numbers carry their entry hash and commit.

## Read the config before acting
`papertrail.toml` sets two dials; follow what they say, and the rule overrides under `[rules]`.
- **tier** (how much is recorded): sketch, logged, reproducible, ledgered, sealed.
- **containment** (what may leave): 0 open, 1 standard, 2 private, 3 restricted, 4 air-gapped.
At containment 2 or above, do not put anything from the project in a public place, and ask before sharing anything outside the repository. At 3, read and send to AI tools only the inputs the config lists. At 4, do nothing that needs the network.

## Commands
| Task | Command |
|---|---|
| Start a project | `papertrail init --tier ledgered --containment 1 --purpose "..."` |
| Run something | `papertrail run --out results/a.csv results/b.csv --question "short title" -- python fit.py` (the command always goes after `--`) |
| Extra inputs | `--in path ...`, besides the inputs listed in the config; declare every input that is not committed, or `verify --deep` cannot rerun the work |
| Link to earlier work | `--parent <hash prefix>` (runs whose outputs are this run's inputs are linked automatically) |
| Close a lab book entry | `papertrail entry --close labbook/2026-11-20-short-title.md` |
| Note a decision | `papertrail note -m "..."` |
| Correct a finding | `papertrail correct --supersedes <hash> -m "..."` |
| Record earlier work | `papertrail reconstruct -m "..." --built-from "..." --claimed-date 2025-06` |
| Timestamp the chain | `papertrail anchor` |
| Seal a private note | `papertrail seal path/to/note` or `papertrail seal --hash <sha256> --proof note.ots` |
| Check | `papertrail verify`, `papertrail verify --deep`, `papertrail check` |

## Sealing and anchoring
To seal a private note, `papertrail seal path/to/note`; the ledger keeps only its hash. If the note was already hashed and stamped by another tool or skill, record it with `papertrail seal --hash <its sha256> --proof <its .ots>`. To date the whole chain, `papertrail anchor`, then stamp the anchor file (`ots stamp`, if `papertrail` could not) and commit the proof.

## Things that trip people up
- `--in`, `--out` and `seal FILE` paths are relative to the current directory; paths in `papertrail.toml` are relative to the project root.
- Files git ignores are never treated as code. If a run imports an ignored file, say so and suggest un-ignoring it.
- `verify --deep` reports how many runs it actually reran. If it reran none, say so; do not call the work reproduced.
- When sealing, keep the private file out of git, and add a random line to short notes so the hash cannot be guessed.

## Reconstructed work
Work done before the trail existed is recorded with `papertrail reconstruct`, never with `run`. Say in the lab book what it was rebuilt from. Never present a reconstructed entry as if it had been recorded at the time.

## Lab book entries
Close each entry within its window; if it will be late, close it anyway and say why in a note. Never backdate.

Sections, in order: Question; Inputs; Method and commands; Results; Findings (numbered, one sentence plus its number); Caveats; Data problems found; Supersedes. Plain, short sentences. Say what is exploratory.

## Say so when the protocol breaks
If a step broke a rule (a hand-edited table, a dirty run reported, a missing entry), say so plainly, record a note, and fix it with a new entry. Do not hide it or tidy it away.
