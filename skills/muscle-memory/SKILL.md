---
name: muscle-memory
description: Use during any ongoing work with someone, to notice repeated friction (a step Claude keeps reasoning out, or something the person keeps asking for) and propose the right reflex: a hook, a tool, a preference or a template.
---

# Muscle Memory

Some work should be thought through every time; some should become reflex. When Claude and the person it works with hit the same friction again and again (a step Claude reasons out by hand, or something the person keeps asking for), it should become a reflex, and the reflex should live in the right place.

## Where a reflex lives
From most hard-wired to least:
1. **Hook or command** (Claude Code): runs with no model in the loop. A session-start hook (e.g. `papertrail check` every session), a pre-tool hook that enforces a rule (block raw runs in a Paper Trail project), a prompt hook that attaches context (the ssh host list when a server is mentioned), or a slash command whose output comes straight from a script (`/hosts`). Use for anything that must happen every time, or must never be skipped.
2. **Tool**: a script or command Claude calls; the answer is exact, testable and the same every time. Use for lookups, counts, hashes, date math, format conversions, rule checks.
3. **Preference**: how Claude presents things, applied to every answer from the start. Use for habits like putting anything to paste in its own code block, offering real decisions as clickable choices, or ending a working session with a suggested next prompt.
4. **Template**: reusable text, such as a recurring prompt, an entry skeleton or a message.

In claude.ai chat there are no hooks; the nearest equivalents are preferences and skills.

## What to notice
Two kinds of signal. The person repeating a request ("I need the ssh name", "give me a copyable block", "give me choices", "what's the next prompt?") is friction on their side: usually a preference, a template or a command. Claude repeating a computation is friction on the model's side: usually a tool or a hook.

A step is a tool candidate when most of these hold:
- **Exact:** there is one right answer (a hash, a count, a sum, a date difference, a format conversion, whether a rule was followed).
- **Repeated:** it has come up before in this work, or plainly will (each session, each run, each file).
- **Checkable:** a wrong answer would matter and could be caught by a test.
- **Rule-shaped:** it follows a written rule ("within 36 hours", "commit before compute", "no file over 5 MB").

It stays a model call when it needs judgment, taste, language or a decision only the person can make: drafting, reviewing an argument, choosing between designs.

Signs in the moment: Claude is about to recount, recompute or re-verify something by reading it; Claude is applying a written rule by hand; the same three commands are being typed again; an answer would change if asked twice; the person asks for the same thing a third time.

## Is it worth building?
Weigh it the way the old chart does (time saved times how often, across the life of the work, against the cost to build), with three additions for a person working with a model:
- **Each model call costs** tokens, waiting, and a small chance of a different answer. For checks that guard results, that chance alone justifies a tool or a hook.
- **Building costs more than it looks.** Code needs debugging, rethinking and upkeep. Prefer the smallest reflex that works: a preference before a tool, a twenty-line script before a framework.
- **The third time is the trigger.** Once is a task, twice is a coincidence; the third time, propose the reflex.

Rough guide: a step that comes up every session and takes more than a minute of reasoning, or any step that guards a result, is worth a small tool or hook. A step that comes up once a term usually is not; a checklist line is enough.

## What to say
One or two lines, at a natural pause, not in the middle of the work:

> This should be a tool: checking that every lab book entry was closed within 36 hours of its run. We've done it by hand three times, and a miss changes the record. A 30-line check in `papertrail verify` would do it. Add it to the list, or build it now?

> This should be a preference: you've asked for a copyable block three times. Save "anything to paste goes in its own code block" as a standing preference?

Then carry on with the task as asked. Never stop the work to build anything unasked, and save a preference only when the person says yes.

## Keep a list
Candidates go in `TOOLS.md` at the root of the project (or in the project's notes if there is no repository), one line each: the friction, how often it comes up, what a miss costs, where the reflex should live (hook, tool, preference, template), and a sketch. The person decides what gets built. When one is built, the line says where it lives.

## When Paper Trail is in use
A rule in the protocol that Claude checks by reasoning is a candidate for `papertrail` itself, or for a hook. Note it in `TOOLS.md` with the rule's name, so the protocol and the tool stay one thing.
