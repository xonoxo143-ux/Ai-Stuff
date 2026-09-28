# Agent language real-text result 01

**Date:** 2026-09-28  
**Workflow run:** `36436244279`  
**Status:** PROMISING RESULT / AWAITING MULTI-SEED REPLICATION

## Setup

Random initialization.

No pretrained weights or tokenizer.

Training corpus:

- first 4,000 streamed TinyStories training examples;
- first 400 validation examples;
- raw UTF-8 bytes;
- about 3.40 MB train and 0.33 MB validation after collection.

Training:

```text
800 updates
batch 8
256-byte windows
seed 101
```

## Result

```text
model          params     valid bits/byte   time      steps/s
GRU            800,640        1.659         133.1 s     6.01
Transformer    927,872        2.610          82.8 s     9.67
```

## Generated samples

GRU:

```text
Once upon a time there was a little girl named Lily. She was so happy and said the bird was so happy. The bird was so happy and said the
```

Transformer:

```text
Once upon a time the was she starked the bit the bug the the bight the the bit the bit the the bo the the the stomet the the sthe sther
```

## Interpretation

At the same update budget, the GRU has already crossed into recognizable English while the Transformer has not.

The GRU result is still far from a conversational language organ:

- repetition is severe;
- semantic depth is minimal;
- no dialogue objective has been trained;
- no perception/cognition loop is connected yet.

But this is the first real-language evidence that a sub-million-parameter, raw-byte, random-init language organ can acquire usable English surface structure cheaply enough for this project.

## Next gate

Repeat exactly across three seeds before:

- increasing update budget;
- increasing model size;
- choosing a production architecture;
- connecting the learned checkpoint to the Agent runtime.
