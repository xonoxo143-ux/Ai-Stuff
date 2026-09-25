# First Agent v0 Phone Run

This procedure is intentionally small. Its purpose is to obtain the first real-hardware trace from the learned sparse recurrent ecology.

## Preconditions

Use an APK built by the `Train Agent Model v0` workflow whose artifact is named:

`Agent-v0-Phone-Package`

That APK contains both:

- the learned ONNX Agent model;
- its verified runtime manifest.

No separate model download is required for this first run.

## Run

1. Install/open AI Workbench.
2. Open the **Agent** tab.
3. Confirm the tab reports a learned Agent model is bundled/ready.
4. Tap **Run hardware self-test**.
5. Wait for the summary and trace.
6. Tap **Push Agent result to GitHub**.

The self-test runs a stateful program through the learned ecology and records, for every internal thought:

- predicted value;
- expected value;
- absolute error;
- recruited capability-cell IDs;
- routing weights;
- per-thought wall-clock latency.

The program deliberately includes operation compositions withheld from model training.

## Do not interpret the first result as a final quality score

The first phone result answers a narrower set of questions:

- Does the learned ecology execute correctly through Android ONNX Runtime?
- Does its private recurrent state survive across events?
- Which cells are recruited on a real sequence?
- What does one sparse thought step actually cost on the phone?
- Does phone numerical behavior remain consistent with the exported model?

After the result is uploaded, inspect it before changing the architecture.
