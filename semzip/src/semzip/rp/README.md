# RP Kernel 0.1

This package is a deliberately small experiment in separating **roleplaying cognition**
from **language generation**.

The kernel is not intended to produce impressive prose yet. It tests whether persistent
world state, separate character knowledge, memory, goals, and response planning can stay
coherent without asking a language model to reconstruct them from conversation text on
every turn.

## Loop

```text
user text
   -> narrow interpreter
   -> event-sourced world
   -> character perception / belief update
   -> response plan
   -> cheap construction-based realizer
   -> text
```

The `ResponsePlan` is the key boundary. Future neural or hybrid realizers should consume
plans rather than being asked to rediscover world state, intentions, secrets, and goals
while writing.

## v0.1 invariants

- Failed/impossible actions are recorded but do not mutate projected world state.
- Ownership and possession are distinct.
- A character learns events only if it can perceive them.
- Private knowledge is stored in that character's mind, not inferred from omniscient text.
- Event memory is distinct from conversational/speech memory.
- Secrets can influence planning without being exposed to the realizer as response content.
- Unknown facts produce uncertainty rather than invention.
- The permanent event ledger survives long delays; current state is a cheap projection.

## Demo character

`RPSession.yvette_demo()` creates a study containing Yvette, the user, a dagger and a key.
Yvette knows the key is connected to a private basement secret, is suspicious/sarcastic,
and has a persistent left-hand injury. The tiny input grammar currently supports a few
adversarial interactions such as taking an object, asking where an object is, asking who
has it, probing the basement, and making a false "you told me" memory claim.

The grammar is intentionally narrow. Unsupported language should fail rather than be
silently misinterpreted.
