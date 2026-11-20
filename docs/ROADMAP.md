# Roadmap

Planned, not built. Each item names what it would add to the ledger.

## AI work ledger: models, tokens, tallies
A place to record which model did which work, and at what cost, alongside the runs it produced.
- **Entry kind `ai`:** model and version, the tool or surface used, a session link, tokens in and out (when the surface reports them), wall time, the task in one line, and the entries it produced (as children).
- **`papertrail ai`** to record one by hand; a hook can record it automatically where the surface exposes usage.
- **`papertrail tally`**: totals by model, by question, by week; tokens per accepted result; how many outputs were later corrected.
- **Model suggestions, from evidence:** once the tally holds enough runs, `papertrail tally --suggest` says which model has done which kind of task well and cheaply in this project, rather than guessing.
- Token counts are self-reported by whatever surface gives them; the record says where each number came from.

## Clean-room builds
For rebuilding a computation from a text alone.
- **Locked inputs:** an allowlist of what the builder may see (for example, only the frozen text of a paper), with every file, prompt and message hashed.
- **Pre-registered builds:** the task, tools, budget, stopping rules and intervention policy fixed (and sealed) before the run.
- **Each turn as an entry:** inputs and outputs hashed per turn; `verify` checks that everything traces back to the allowlist or to a logged intervention.
- **A gated channel:** messages to the builder limited to a vocabulary set by level (silent, go/no-go, yes/no, pointers into the text, corrections, free text), refused above it, with the total information that crossed reported in bits. Messages only at scheduled checkpoints.
- Stated in every record: an allowlist controls what was supplied, not what a model or person already knew.

## Hooks shipped with the plugin
- Session start: run `papertrail check` automatically in any Paper Trail project.
- Before a tool call: refuse raw runs of computing code that bypass `papertrail run`, at the `reproducible` tier and above.

## Smaller
- Windows support (replace `fcntl` locking).
- An optional Python helper for recording seeds inside a run.
- `papertrail export` for a citable bundle of the ledger and lab book (Zenodo-ready).
