# Agent v1 chatbot anchor — SUPERSEDED

**Superseded:** 2026-09-29

This file described an earlier integration policy that allowed a strong pretrained language model to sit at the center of the chatbot.

That is **not the current project objective**.

The authoritative target is now in:

**`AGENT_CURRENT.md`**

Current hard rule:

> Build the conversational intelligence from scratch. A pretrained LLM may be used only as a control/reference system, never as the hidden intelligence or response engine being evaluated.

The current whole-agent priority is:

```text
close the homegrown conversational loop
→ expand language/semantic generality
→ add broad retrievable knowledge
→ test multi-turn/topic flexibility
→ use isolated cognition benchmarks diagnostically
→ add continual development
```

Do not use this historical file to override `AGENT_CURRENT.md`.
