---
name: muscle-memory
description: Use while working with Wöden on any task, to notice when a step Claude keeps doing by reasoning (counting, checking, converting, comparing, date math, rule checks) should become a small tool, and to say so briefly with the payoff.
---

# Muscle Memory

Some work should be thought through every time; some should become reflex. When Claude and Wöden do the same exact, checkable step again and again by having Claude reason it out, that step belongs in a tool: a script, a command, a check. A tool gives the same answer every time, costs nothing per use, can be tested, and leaves a record. A model call does none of that reliably.

## What to notice
A step is a tool candidate when most of these hold:
- **Exact:** there is one right answer (a hash, a count, a sum, a date difference, a format conversion, whether a rule was followed).
- **Repeated:** it has come up before in this work, or plainly will (each session, each run, each file).
- **Checkable:** a wrong answer would matter and could be caught by a test.
- **Rule-shaped:** it follows a written rule ("same day", "commit before compute", "no file over 5 MB").

It stays a model call when it needs judgment, taste, language or a decision only Wöden can make: drafting, reviewing an argument, choosing between designs.

Signs in the moment: Claude is about to recount, recompute or re-verify something by reading it; Claude is applying a written rule by hand; the same three commands are being typed again; an answer would change if asked twice.

## Is it worth building?
Weigh it the way the old chart does (time saved times how often, across the life of the work, against the cost to build), with three additions for the two of us:
- **Each model call costs** tokens, waiting, and a small chance of a different answer. For checks that guard results, that chance alone justifies a tool.
- **Building costs more than it looks.** Code needs debugging, rethinking and upkeep. Prefer the smallest tool that works: a twenty-line script beats a framework.
- **The third time is the trigger.** Once is a task, twice is a coincidence; the third time, propose the tool.

Rough guide: a step that comes up every session and takes more than a minute of reasoning, or any step that guards a result, is worth a small tool. A step that comes up once a term usually is not; a checklist line is enough.

## What to say
One or two lines, at a natural pause, not in the middle of the work:

> This should be a tool: checking that every lab book entry was closed within 36 hours of its run. We've done it by hand three times, and a miss changes the record. A 30-line check in `papertrail verify` would do it. Add it to the list, or build it now?

Then carry on with the task as asked. Never stop the work to build the tool unasked.

## Keep a list
Candidates go in `TOOLS.md` at the root of the project (or in the project's notes if there is no repository), one line each: the step, how often it comes up, what a miss costs, and a sketch of the tool. Wöden decides what gets built. When one is built, the line says where it lives.

## When Paper Trail is in use
A rule in the protocol that Claude checks by reasoning is a candidate for `papertrail` itself. Note it in `TOOLS.md` with the rule's name, so the protocol and the tool stay one thing.
