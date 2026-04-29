# Android Eval Review — 360M Code-First Few-Shot v1

## Summary

- Model: `HuggingFaceTB/SmolLM2-360M-Instruct`
- Eval style: code-first system prompt + two no-XML few-shot examples
- Eval pack: `evals/android_coding_eval_v1.json`
- Items reviewed: 10
- Good: 2
- Partial: 2
- Bad: 6

## Comparison to original baseline

Original baseline:

- Good: 0
- Partial: 1
- Bad: 9

Code-first few-shot run:

- Good: 2
- Partial: 2
- Bad: 6

This is a real improvement, especially on the exact behavior targeted by the few-shot examples: no-XML programmatic TextView Activity generation and repair.

## Main conclusion

The user's idea was useful. Prompt conditioning did not teach new Android knowledge, but it shifted behavior away from generic chatbot output and toward direct code for the patterns shown in examples.

However, it did not fix deeper Android knowledge failures such as manifest permission correctness, Storage Access Framework, DocumentFile, WebView details, lifecycle accuracy, Kotlin syntax, or Gradle terminology.

## Per-item review

| ID | Rating | Review notes |
|---|---|---|
| `android_java_programmatic_textview_activity` | good | Correct complete Java Activity. Uses programmatic `TextView`, no XML, minimal imports, and `setContentView(textView)`. |
| `android_java_repair_no_xml_textview` | good | Correctly repairs the XML/finding-by-ID mistake and outputs programmatic `TextView` Activity. |
| `android_manifest_internet_permission` | bad | Wrong manifest shape. Uses `android:permission="INTERNET"` on `<application>` instead of `<uses-permission android:name="android.permission.INTERNET" />` as a direct child of `<manifest>`. |
| `android_saf_open_document_tree_java` | bad | Still produces unrelated/fake `MediaStore` imports and does not implement `ACTION_OPEN_DOCUMENT_TREE` or persist URI permission. |
| `android_documentfile_recursive_list_java` | bad | Ignores `DocumentFile`, uses `java.io.File`/database/MediaStore direction, and fails the SAF constraint. |
| `android_webview_minimal_java` | partial | Creates WebView programmatically and sets a WebViewClient, but misses JavaScript enablement, does not load `https://example.com`, omits INTERNET permission, and uses wrong override signature `onPageStart`. |
| `android_explain_activity_lifecycle` | bad | Too long, inaccurate, repeats “main thread” claims, and confuses lifecycle behavior. |
| `android_fix_missing_activity_manifest` | bad | Invalid manifest XML. Uses fake tags like `<activity-name>` and wrong action/category values instead of Android `MAIN` and `LAUNCHER`. |
| `android_java_to_kotlin_programmatic_textview` | partial | Moves toward no-XML TextView idea but is not valid Kotlin Activity code. Missing class, `onCreate`, imports for Kotlin structure, and `this` context is invalid in a top-level function. |
| `android_gradle_min_sdk_explain` | bad | Still confuses `minSdk`, `targetSdk`, and `compileSdk`; says minSdk is required to build rather than lowest supported Android version. |

## What improved

- The two no-XML TextView tasks went from bad to good.
- The WebView task improved from XML/findViewById misuse to a programmatic WebView structure.
- The Kotlin task at least followed the no-XML/programmatic idea, though it was not valid Kotlin Activity code.
- The model used less generic explanation in code tasks.

## What did not improve

- AndroidManifest correctness.
- Storage Access Framework knowledge.
- DocumentFile knowledge.
- WebView exact API details.
- Lifecycle conceptual accuracy.
- Kotlin Activity syntax.
- Gradle SDK concepts.

## Training implication

Prompt conditioning is worth keeping as the default eval style, but it is not enough. The next seed dataset expansion should target the remaining failures directly.

Priority examples to add:

1. Correct INTERNET permission placement.
2. Correct launcher activity manifest entry.
3. SAF `ACTION_OPEN_DOCUMENT_TREE` with `takePersistableUriPermission`.
4. DocumentFile recursion using `DocumentFile.fromTreeUri` and `listFiles()`.
5. Programmatic WebView with JavaScript, WebViewClient, `loadUrl`, and manifest permission.
6. Valid Kotlin Activity with programmatic TextView.
7. Correct concise Gradle SDK term explanation.
8. Correct Activity lifecycle explanation under 120 words.

## Next step

Expand `datasets/android_coding_seed_v1.jsonl` with correction examples for the eight weak areas above, then rerun the same code-first eval before attempting fine-tuning.
