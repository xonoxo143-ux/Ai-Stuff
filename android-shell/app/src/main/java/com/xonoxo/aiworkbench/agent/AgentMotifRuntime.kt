package com.xonoxo.aiworkbench.agent

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import kotlin.math.max

data class MotifTimingStats(
    val count: Int,
    val totalMs: Double,
    val meanMs: Double,
    val medianMs: Double,
    val p90Ms: Double,
    val p95Ms: Double,
)

data class MotifHardwareResult(
    val teacher: MotifTimingStats,
    val compiled: MotifTimingStats,
    val teacherOverCompiledMedianRatio: Double,
    val teacherOverCompiledMeanRatio: Double,
    val maxOutputAbsDelta: Double,
    val trials: List<Map<String, Any>>,
)

/**
 * Real-device microbenchmark for a compiled interaction motif.
 *
 * Both ONNX graphs consume the exact same boundary vector. The teacher graph
 * executes the original two source cells; the compiled graph executes the
 * distilled composite. This isolates whether compilation saves actual device
 * runtime at the promoted boundary.
 */
class AgentMotifRuntime : Closeable {
    private val environment = OrtEnvironment.getEnvironment()

    private var teacherSession: OrtSession? = null
    private var compiledSession: OrtSession? = null

    @Synchronized
    fun load(
        teacherPath: String,
        compiledPath: String,
        threads: Int = 4,
    ) {
        close()
        teacherSession = createSession(teacherPath, threads)
        compiledSession = createSession(compiledPath, threads)
        validate(requireNotNull(teacherSession), "teacher")
        validate(requireNotNull(compiledSession), "compiled")
    }

    @Synchronized
    fun isLoaded(): Boolean =
        teacherSession != null && compiledSession != null

    @Synchronized
    fun benchmark(
        samples: FloatArray,
        inputDim: Int,
        sampleCount: Int,
        warmupPasses: Int = 2,
        trials: Int = 12,
    ): MotifHardwareResult {
        val teacher = checkNotNull(teacherSession) {
            "Motif teacher session is not loaded"
        }
        val compiled = checkNotNull(compiledSession) {
            "Motif compiled session is not loaded"
        }
        require(samples.size == inputDim * sampleCount) {
            "Motif sample buffer has the wrong size"
        }

        fun runPass(
            session: OrtSession,
            captureOutputs: Boolean,
        ): Pair<MutableList<Double>, List<FloatArray>> {
            val latencies = mutableListOf<Double>()
            val outputs = if (captureOutputs) mutableListOf<FloatArray>() else null

            for (sampleIndex in 0 until sampleCount) {
                val start = sampleIndex * inputDim
                val row = samples.copyOfRange(start, start + inputDim)
                val started = System.nanoTime()

                val output = runOne(session, row, inputDim)
                val elapsedMs = (System.nanoTime() - started) / 1_000_000.0
                latencies += elapsedMs

                if (outputs != null) outputs += output
            }

            return latencies to (outputs ?: emptyList())
        }

        // Warm both execution paths before measured trials.
        repeat(warmupPasses) {
            runPass(teacher, false)
            runPass(compiled, false)
        }

        val teacherLatencies = mutableListOf<Double>()
        val compiledLatencies = mutableListOf<Double>()
        val trialRows = mutableListOf<Map<String, Any>>()
        var maxDelta = 0.0

        repeat(trials) { trial ->
            val teacherFirst = trial % 2 == 0
            val first = if (teacherFirst) teacher else compiled
            val second = if (teacherFirst) compiled else teacher

            val firstResult = runPass(first, captureOutputs = true)
            val secondResult = runPass(second, captureOutputs = true)

            val teacherResult =
                if (teacherFirst) firstResult else secondResult
            val compiledResult =
                if (teacherFirst) secondResult else firstResult

            teacherLatencies += teacherResult.first
            compiledLatencies += compiledResult.first

            for (index in 0 until sampleCount) {
                val teacherOutput = teacherResult.second[index]
                val compiledOutput = compiledResult.second[index]
                val width = minOf(teacherOutput.size, compiledOutput.size)
                for (j in 0 until width) {
                    maxDelta = max(
                        maxDelta,
                        kotlin.math.abs(
                            teacherOutput[j].toDouble() -
                                compiledOutput[j].toDouble()
                        )
                    )
                }
            }

            trialRows += mapOf(
                "trial" to trial,
                "order" to if (teacherFirst)
                    listOf("teacher", "compiled")
                else
                    listOf("compiled", "teacher"),
                "teacher_total_ms" to teacherResult.first.sum(),
                "compiled_total_ms" to compiledResult.first.sum(),
            )
        }

        val teacherStats = stats(teacherLatencies)
        val compiledStats = stats(compiledLatencies)

        return MotifHardwareResult(
            teacher = teacherStats,
            compiled = compiledStats,
            teacherOverCompiledMedianRatio = (
                teacherStats.medianMs / compiledStats.medianMs
            ),
            teacherOverCompiledMeanRatio = (
                teacherStats.meanMs / compiledStats.meanMs
            ),
            maxOutputAbsDelta = maxDelta,
            trials = trialRows,
        )
    }

    private fun createSession(
        path: String,
        threads: Int,
    ): OrtSession {
        val options = OrtSession.SessionOptions()
        return try {
            options.setOptimizationLevel(
                OrtSession.SessionOptions.OptLevel.ALL_OPT
            )
            options.setIntraOpNumThreads(threads.coerceAtLeast(1))
            options.setInterOpNumThreads(1)
            environment.createSession(path, options)
        } finally {
            options.close()
        }
    }

    private fun validate(
        session: OrtSession,
        label: String,
    ) {
        require(session.inputNames.contains("boundary")) {
            "$label motif model is missing boundary input"
        }
        require(session.outputNames.contains("replacement")) {
            "$label motif model is missing replacement output"
        }
    }

    private fun runOne(
        session: OrtSession,
        input: FloatArray,
        inputDim: Int,
    ): FloatArray {
        OnnxTensor.createTensor(
            environment,
            directFloatBuffer(input),
            longArrayOf(1, inputDim.toLong()),
        ).use { tensor ->
            session.run(mapOf("boundary" to tensor)).use { result ->
                val value = result.get("replacement").orElseThrow {
                    IllegalStateException(
                        "Motif model missing replacement output"
                    )
                }
                val outputTensor = value as? OnnxTensor
                    ?: throw IllegalStateException(
                        "Motif replacement is not a tensor"
                    )
                val buffer = outputTensor.floatBuffer
                    ?: throw IllegalStateException(
                        "Motif replacement is not float"
                    )
                val output = FloatArray(buffer.remaining())
                buffer.get(output)
                return output
            }
        }
    }

    private fun directFloatBuffer(values: FloatArray): FloatBuffer {
        val buffer = ByteBuffer.allocateDirect(values.size * 4)
            .order(ByteOrder.nativeOrder())
            .asFloatBuffer()
        buffer.put(values)
        buffer.rewind()
        return buffer
    }

    private fun stats(values: List<Double>): MotifTimingStats {
        require(values.isNotEmpty())
        val sorted = values.sorted()

        fun percentile(fraction: Double): Double {
            val index = (
                ((sorted.size - 1) * fraction).toInt()
            ).coerceIn(0, sorted.lastIndex)
            return sorted[index]
        }

        val median = if (sorted.size % 2 == 1) {
            sorted[sorted.size / 2]
        } else {
            (
                sorted[sorted.size / 2 - 1] +
                    sorted[sorted.size / 2]
            ) / 2.0
        }

        val total = values.sum()
        return MotifTimingStats(
            count = values.size,
            totalMs = total,
            meanMs = total / values.size,
            medianMs = median,
            p90Ms = percentile(0.90),
            p95Ms = percentile(0.95),
        )
    }

    @Synchronized
    override fun close() {
        teacherSession?.close()
        compiledSession?.close()
        teacherSession = null
        compiledSession = null
    }
}
