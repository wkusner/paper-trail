# The Paper Trail protocol

Every number a project reports must trace back, by hash, to the exact code, inputs and environment that made it, and anyone must be able to check that trail and, where the work allows, rerun it to the same bytes. The trace lives in the ledger, `labbook/ledger.jsonl`; the reasoning lives in the lab book, `labbook/`.

## The five rules
1. **Only through the trail.** Computations that produce results run through `papertrail run`. No hand-made result tables.
2. **Commit before you compute.** `papertrail run` refuses uncommitted code (at the `reproducible` tier and above); every run names its commit.
3. **Append, never edit.** The ledger and the lab book only grow. A correction is a new entry that says what it supersedes.
4. **One question, one lab book entry.** Written the same day: question, inputs, commands, results with their checks, caveats, what it supersedes.
5. **Verify before you share.** `papertrail verify` passes before results go anywhere.

## Two dials
A project sets both in `papertrail.toml`. Each dial switches rules on by default; any rule can be switched on or off under `[rules]`, and every ledger entry records the settings in force when it was written.

**Rigor tier: how much is recorded.**
| Tier | Adds | Rules switched on |
|---|---|---|
| sketch | a lab book entry per question; nothing enforced | |
| logged | runs go through `papertrail run`, with times | `log_runs` |
| reproducible | commit before compute; environment recorded; `verify --deep` reruns | `commit_before_compute`, `capture_env` |
| ledgered | outputs hashed and chained; verify before sharing | `hash_outputs`, `verify_before_share` |
| sealed | the chain head is anchored with a trusted timestamp | `anchor_head` |

**Containment: what can leave, and who or what can see the inputs.** Modelled loosely on biosafety levels.
| Level | Name | In practice | Rule switched on |
|---|---|---|---|
| 0 | open | everything may be public; data in git allowed | |
| 1 | standard | data stays out of git; only hashes and manifests are committed | `data_out_of_git` |
| 2 | private | private repository; only hashes go public; sharing needs the owner's say-so | `private_repo` |
| 3 | restricted | named people only; AI tools see only listed inputs; exports reviewed and logged | `list_ai_inputs` |
| 4 | air-gapped | an offline machine; anything moved in or out is hashed on both sides | `offline_only` |

`papertrail` enforces `commit_before_compute` and warns on `data_out_of_git` and missing outputs; the containment rules above 1 are commitments for people and for Claude, shown by `papertrail check`.

## The chain
Each entry holds the SHA-256 of the entry before it (`prev`) and of the entries it builds on (`parents`), and its own hash over all of that. Changing or deleting anything in the past breaks every hash after it, and `verify` reports it.

| Kind | Records |
|---|---|
| `genesis` | the project's name and purpose |
| `run` | command, working directory, commit, uncommitted code (if allowed), hashes of code, inputs and outputs, exit code, times, environment |
| `run` (reconstructed) | work done before the trail existed: what it was rebuilt from and its claimed date; never rerun by `verify` |
| `note` | a decision or observation; lab book entries opened |
| `correction` | what it supersedes and why |
| `anchor` | the chain head being timestamped |
| `seal` | the hash of a private file, never its contents |

A run that reads a file another run wrote, byte for byte, is linked to it as a parent automatically.

## Times
Entry times and git dates are self-reported. For dates others can trust, `papertrail anchor` writes the current head hash to `labbook/anchors/` and stamps it with OpenTimestamps if `ots` is installed. Since each entry includes the one before it, one stamp dates everything before it. Run `ots upgrade` on the proof after a few hours and commit it. The head hash can also go into a public sealed ledger, so a private project still has public, dated evidence.

## Sealing
`papertrail seal FILE` records only the file's SHA-256 (and an optional public label) and stamps it. Opening it later means revealing the file; anyone can hash it and compare. A note already sealed with Under Seal is recorded with `papertrail seal --hash <sha256> --proof <file.ots>`.

## Verify
`papertrail verify` checks that every entry matches its hash, links to the one before it, and names only earlier parents; that each output file still matches the run that last wrote it; and that anchor and seal files exist. `papertrail verify --deep` also reruns each latest-writing run made at the current commit with unchanged inputs, and fails if its outputs differ by a single byte. Runs at other commits are listed, not rerun.

## Step by step
1. `papertrail init --tier ledgered --containment 1 --purpose "..."`; edit `papertrail.toml` (code globs, input globs); commit it with `labbook/`.
2. Per question: `papertrail entry "short title"`.
3. Commit the code; `papertrail run --out ... --question "short title" -- <command>`.
4. Write up the entry; `papertrail verify`.
5. Commit the ledger, the results and the lab book entry together.
6. At milestones (or daily at the `sealed` tier): `papertrail anchor`, stamp, commit the proof.

## Never
- Edit or delete a line of the ledger; append instead. `verify` will catch it.
- Report a number with no ledger entry behind it.
- Present a reconstructed entry as if recorded at the time.
- Commit data that the containment level keeps out of git.
