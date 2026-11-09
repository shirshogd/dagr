# README patterns (research notes)

Sources read (2026-11):
- https://github.com/NousResearch/hermes-agent : centered banner, tagline, shields row (docs, chat, MIT), one-line `curl | bash` install, 7-row HTML feature table, short quickstart, no demo or diagram.
- https://github.com/openclaw/openclaw : centered banner, 5 badges, one-line install per OS, about 3-step quickstart, "how it fits together" bullet list, no diagram.
- https://github.com/browser-use/browser-use : demo video directly under the hero, a paste-this-prompt install for agents, a "which one do I need" picture.
- https://github.com/Aider-AI/aider : centered title plus one-line subtitle, screencast right under the hero, 2-command install, icon feature list.
- https://github.com/crewAIInc/crewAI : badge row, link row, numbered 3-step quickstart, "Why" bullets.
- https://github.com/matiassingers/awesome-readme : GIF near the top, short description, copy-paste setup, selective badges, license and contributing.
- https://www.makeareadme.com/ : name, description, install, usage with expected output, status, license; move long material to linked docs.
- https://github.com/hackergrrl/art-of-readme : the raw page returned 404 when fetched, so these points come from its well-known advice, not from a fresh read: say what it is fast, cut the time to first success, link out for depth.

## Patterns applied
1. Centered hero: name plus one sentence, nothing else above the fold.
2. One badge row of facts only (license, Python, dependencies, supported agents).
3. The install is a single copy-paste block near the top (the paste-a-prompt form from browser-use).
4. Demo directly under the install: a GIF slot plus a link to the playable explainer.
5. A numbered list for "what happens next", so the whole flow fits in six lines.
6. A before/after folder tree, the most direct proof of what changes.
7. One mermaid diagram for how it works (GitHub renders it natively).
8. A CLI table instead of a feature grid, since the CLI is the product surface.
9. Define each term on first use; a boxed "What is X?" for the one outside idea (ICM), with credit.
10. Safety and control gets its own section, because the tool edits user files.
11. An honest Status section: what is new, what is untested.
12. Depth moves to docs/ pages; the README stays under about 250 lines.
13. Short paragraphs, tables over prose, no emoji walls, no hype words.
14. FAQ, contributing, and license links at the bottom.
