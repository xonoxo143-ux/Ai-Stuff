# Guided Frontier Reasoning v0 — Result

**Date:** 2026-09-29
**Status:** immutable result

Three seeds, 140 unseen 4–7-step compositions per seed, 12,800 stored candidate modules.

```text
myopic learned rollout      18.10% mean solved
beam 6 guided frontier      42.14%
beam 18 guided frontier     53.10%
relative gain               2.93×
```

Mean active search work:

```text
myopic candidate checks      ~20.3
beam 6 expansions           ~273.9
beam 18 expansions          ~626.0
```

Independent budget sweep:

```text
budget  80    34.2% solved   ~58 mean expansions
budget 160    50.0% solved   ~104
budget 320    60.8% solved   ~175
budget 640    64.2% solved   ~292
budget1200    66.7% solved   ~481
```

Interpretation: retaining multiple execution states materially improves novel multi-step reasoning when a learned one-step proposal mechanism is already strong. Beam search itself is not promoted as final architecture.
