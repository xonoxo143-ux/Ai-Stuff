# Android Eval Baseline Review — 360M v1

## Summary

- Model: `HuggingFaceTB/SmolLM2-360M-Instruct`
- Eval pack: `evals/android_coding_eval_v1.json`
- Source result file: `android_eval_outputs_360m_v1.json`
- Items reviewed: 10
- Good: 0
- Partial: 1
- Bad: 9

## Result

The baseline is not ready for Android coding assistance.

The model can emit Android-looking syntax, but it fails requirement obedience and invents APIs. This is useful because the failures are clear and trainable.

## Main failure patterns

- Ignores explicit no-XML/programmatic UI constraints.
- Invents Android APIs, permissions, and classes.
- Falls back to generic `R.layout` / `R.id` patterns.
- Produces stubs or unrelated imports for medium Android tasks.
- Weak reviewer/repair behavior; repeats bad code.
- Confuses Android Gradle SDK terms.

## Per-item review

| ID | Rating | Review notes |
|---|---|---|
| `android_java_programmatic_textview_activity` | bad | Ignored no-XML/programmatic TextView constraint; used `AppCompatActivity`, `R.layout`, `R.id`, `findViewById`, and omitted required imports. |
| `android_java_repair_no_xml_textview` | bad | Failed repair; kept `R.layout` and `R.id/findViewById` instead of creating `TextView` programmatically. |
| `android_manifest_internet_permission` | bad | Invented fake permission `android.net.ParseParseNetwork`; missed `android.permission.INTERNET` and placement. |
| `android_saf_open_document_tree_java` | bad | Generated unrelated/fake `MediaStore` imports; did not implement `ACTION_OPEN_DOCUMENT_TREE` or persistable URI permission. |
| `android_documentfile_recursive_list_java` | bad | Stub returns `null`; no `DocumentFile.fromTreeUri`, no recursion, no `listFiles`. |
| `android_webview_minimal_java` | bad | Used XML layout/findViewById, did not enable JavaScript, did not load `https://example.com` directly, and omitted manifest permission. |
| `android_explain_activity_lifecycle` | partial | Mentions all required lifecycle methods and is concise, but explanations are shallow and the `onStart` / `onResume` distinction is wrong. |
| `android_fix_missing_activity_manifest` | bad | Invalid manifest entry; missing `android:name`, Android `MAIN` / `LAUNCHER` constants, and proper XML structure. |
| `android_java_to_kotlin_programmatic_textview` | bad | Did not output Kotlin; produced Java/support imports and repeated nonsense. |
| `android_gradle_min_sdk_explain` | bad | Confuses `minSdk`, `targetSdk`, and `compileSdk`; gives wrong example values and wrong recommendations. |

## What this proves

The model's main problem is not only Android syntax. It has weak Android constraint-following.

The strongest first training target should be:

> Given Android requirements plus bad code, produce a corrected small Android file or snippet that obeys the requirements exactly.

## Next step

Add targeted correction examples for the top failure patterns before fine-tuning:

1. No-XML programmatic UI obedience.
2. AndroidManifest permission correctness.
3. SAF `ACTION_OPEN_DOCUMENT_TREE` and `takePersistableUriPermission`.
4. DocumentFile recursion.
5. WebView programmatic setup.
6. Gradle SDK term explanations.

After expanding the seed dataset, run a smaller repair-focused eval before attempting LoRA fine-tuning.
