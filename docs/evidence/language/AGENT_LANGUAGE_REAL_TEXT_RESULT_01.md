# Agent language real-text result 01

**Date:** 2026-09-29  
**Workflow:** initial run \`36436244279\`; three-seed replication \`36437199998\`  
**Status:** REPLICATED RESULT

## Setup

Random initialization.

No pretrained weights or tokenizer.

Training corpus:

- first 4,000 streamed TinyStories training examples;
- first 400 validation examples;
- raw UTF-8 bytes;
- about 3.40 MB train and 0.33 MB validation.

Per run:

\`\`\`text
800 updates
batch 8
256-byte windows
\`\`\`

Seeds: 101, 202, 303.

## Replicated result

\`\`\`text
model          params     mean valid bits/byte   mean train time
GRU            800,640          1.640                187.8 s
Transformer    927,872          2.567                131.5 s
\`\`\`

Per-seed GRU validation bits/byte:

\`\`\`text
101   1.659
202   1.620
303   1.642
\`\`\`

Per-seed Transformer:

\`\`\`text
101   2.610
202   2.583
303   2.507
\`\`\`

All three GRU samples crossed into recognizable but repetitive English. Example starts included:

\`\`\`text
"Once upon a time there was a little girl named Lily..."
"Once upon a time, there was a big box..."
"Once upon a time, there was a little girl named Timmy..."
\`\`\`

The Transformer remained much more malformed at the same update budget.

## Interpretation

The synthetic GRU quality advantage survived real-text replication.

This is a meaningful language-surface result, not evidence that the model is already an intelligent conversational agent.

Current consequence:

- GRU is the production baseline;
- Transformer remains an efficiency/control candidate;
- do not scale either merely to polish surface language while the cognitive/transfer problem is more important.
