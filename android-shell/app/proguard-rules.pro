# Kernel classes are referenced directly from Kotlin/JNI.
-keep class com.xonoxo.aiworkbench.NativeRuntime { *; }

# ONNX Runtime Java bindings are reached through JNI.
-keep class ai.onnxruntime.** { *; }
