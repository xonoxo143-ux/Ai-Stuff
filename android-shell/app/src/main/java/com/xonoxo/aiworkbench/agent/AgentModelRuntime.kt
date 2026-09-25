package com.xonoxo.aiworkbench.agent

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.json.JSONObject
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

enum class AgentExecutionBackend {
    SPARSE,
    DENSE_REFERENCE,
}

data class AgentModelInfo(
    val modelId: String,
    val eventDim: Int,
    val outputDim: Int,
    val numCells: Int,
    val activeCells: Int,
    val stateDim: Int,
    val workspaceSlots: Int,
    val thoughtSteps: Int,
    val denseReferenceAvailable: Boolean,
)

data class AgentThoughtResult(
    val output: FloatArray,
    val selectedCells: IntArray,
    val routeWeights: FloatArray,
    val routerScores: FloatArray,
    val haltProbability: Float,
    val latencyNanos: Long,
)

private data class RuntimeState(
    var workspace: FloatArray,
    var cellStates: FloatArray,
)

/**
 * Android host for the learned ecology's one-step ONNX graphs.
 *
 * The sparse graph is the deployed path. An optional dense-reference graph uses
 * the exact same weights and top-k commit semantics while evaluating every cell
 * candidate. Keeping both lets the phone measure whether sparse execution
 * actually saves real hardware time rather than only theoretical FLOPs.
 */
class AgentModelRuntime : Closeable {
    private val environment = OrtEnvironment.getEnvironment()

    private var sparseSession: OrtSession? = null
    private var denseSession: OrtSession? = null
    private var info: AgentModelInfo? = null
    private var initialWorkspace = FloatArray(0)

    private var sparseState = RuntimeState(FloatArray(0), FloatArray(0))
    private var denseState = RuntimeState(FloatArray(0), FloatArray(0))

    @Synchronized
    fun load(
        sparseModelPath: String,
        manifestText: String,
        denseModelPath: String? = null,
        threads: Int = 4,
    ): AgentModelInfo {
        closeSessions()

        val manifest = JSONObject(manifestText)
        val schema = manifest.getInt("schema")
        require(schema == 1 || schema == 2) {
            "Unsupported Agent model manifest schema: $schema"
        }
        val config = manifest.getJSONObject("config")
        val denseDeclared = schema >= 2 && manifest.has("dense_reference")

        require(!denseDeclared || !denseModelPath.isNullOrBlank()) {
            "Manifest declares a dense reference model but no path was supplied"
        }

        val loadedInfo = AgentModelInfo(
            modelId = manifest.getString("model_id"),
            eventDim = config.getInt("event_dim"),
            outputDim = config.getInt("output_dim"),
            numCells = config.getInt("num_cells"),
            activeCells = config.getInt("active_cells"),
            stateDim = config.getInt("state_dim"),
            workspaceSlots = config.getInt("workspace_slots"),
            thoughtSteps = config.getInt("max_thought_steps"),
            denseReferenceAvailable = denseDeclared,
        )

        val initial = manifest.getJSONArray("initial_workspace")
        require(initial.length() == loadedInfo.workspaceSlots) {
            "Manifest workspace slot count does not match config"
        }

        val flattened = FloatArray(
            loadedInfo.workspaceSlots * loadedInfo.stateDim
        )
        var cursor = 0
        for (slotIndex in 0 until initial.length()) {
            val slot = initial.getJSONArray(slotIndex)
            require(slot.length() == loadedInfo.stateDim) {
                "Manifest workspace width does not match config"
            }
            for (dimension in 0 until slot.length()) {
                flattened[cursor++] = slot.getDouble(dimension).toFloat()
            }
        }

        sparseSession = createSession(sparseModelPath, threads)
        validateSession(requireNotNull(sparseSession), "sparse")

        if (denseDeclared) {
            denseSession = createSession(requireNotNull(denseModelPath), threads)
            validateSession(requireNotNull(denseSession), "dense reference")
        }

        info = loadedInfo
        initialWorkspace = flattened
        reset()
        return loadedInfo
    }

    @Synchronized
    fun reset(backend: AgentExecutionBackend? = null) {
        val loadedInfo = info ?: return

        fun freshState(): RuntimeState = RuntimeState(
            workspace = initialWorkspace.copyOf(),
            cellStates = FloatArray(
                loadedInfo.numCells * loadedInfo.stateDim
            ),
        )

        when (backend) {
            AgentExecutionBackend.SPARSE -> sparseState = freshState()
            AgentExecutionBackend.DENSE_REFERENCE -> denseState = freshState()
            null -> {
                sparseState = freshState()
                denseState = freshState()
            }
        }
    }

    @Synchronized
    fun isLoaded(): Boolean = sparseSession != null

    @Synchronized
    fun denseReferenceAvailable(): Boolean = denseSession != null

    @Synchronized
    fun modelInfo(): AgentModelInfo? = info

    @Synchronized
    fun thoughtStep(
        event: FloatArray,
        backend: AgentExecutionBackend = AgentExecutionBackend.SPARSE,
    ): AgentThoughtResult {
        val loadedInfo = checkNotNull(info) {
            "Agent model metadata is not loaded"
        }
        require(event.size == loadedInfo.eventDim) {
            "Expected event dimension ${loadedInfo.eventDim}, got ${event.size}"
        }

        val loadedSession = when (backend) {
            AgentExecutionBackend.SPARSE -> checkNotNull(sparseSession) {
                "Sparse Agent model is not loaded"
            }
            AgentExecutionBackend.DENSE_REFERENCE -> checkNotNull(denseSession) {
                "Dense reference Agent model is not loaded"
            }
        }

        val state = when (backend) {
            AgentExecutionBackend.SPARSE -> sparseState
            AgentExecutionBackend.DENSE_REFERENCE -> denseState
        }

        val started = System.nanoTime()

        OnnxTensor.createTensor(
            environment,
            directFloatBuffer(event),
            longArrayOf(1, loadedInfo.eventDim.toLong()),
        ).use { eventTensor ->
            OnnxTensor.createTensor(
                environment,
                directFloatBuffer(state.workspace),
                longArrayOf(
                    1,
                    loadedInfo.workspaceSlots.toLong(),
                    loadedInfo.stateDim.toLong(),
                ),
            ).use { workspaceTensor ->
                OnnxTensor.createTensor(
                    environment,
                    directFloatBuffer(state.cellStates),
                    longArrayOf(
                        1,
                        loadedInfo.numCells.toLong(),
                        loadedInfo.stateDim.toLong(),
                    ),
                ).use { cellTensor ->
                    val inputs = mapOf(
                        "event" to eventTensor,
                        "workspace" to workspaceTensor,
                        "cell_states" to cellTensor,
                    )

                    loadedSession.run(inputs).use { result ->
                        val output = floatOutput(result, "output")
                        state.workspace = floatOutput(result, "new_workspace")
                        state.cellStates = floatOutput(result, "new_cell_states")
                        val selectedLongs = longOutput(
                            result, "selected_cells"
                        )
                        val selected = IntArray(selectedLongs.size) {
                            selectedLongs[it].toInt()
                        }
                        val routeWeights = floatOutput(
                            result, "route_weights"
                        )
                        val routerScores = floatOutput(
                            result, "router_scores"
                        )
                        val halt = floatOutput(
                            result, "halt_probability"
                        ).single()

                        return AgentThoughtResult(
                            output = output,
                            selectedCells = selected,
                            routeWeights = routeWeights,
                            routerScores = routerScores,
                            haltProbability = halt,
                            latencyNanos = System.nanoTime() - started,
                        )
                    }
                }
            }
        }
    }

    private fun createSession(
        modelPath: String,
        threads: Int,
    ): OrtSession {
        val options = OrtSession.SessionOptions()
        return try {
            options.setOptimizationLevel(
                OrtSession.SessionOptions.OptLevel.ALL_OPT
            )
            options.setIntraOpNumThreads(threads.coerceAtLeast(1))
            options.setInterOpNumThreads(1)
            environment.createSession(modelPath, options)
        } finally {
            options.close()
        }
    }

    private fun validateSession(
        session: OrtSession,
        label: String,
    ) {
        val requiredInputs = setOf("event", "workspace", "cell_states")
        require(session.inputNames.containsAll(requiredInputs)) {
            "$label Agent model is missing required inputs"
        }
        val requiredOutputs = setOf(
            "output",
            "new_workspace",
            "new_cell_states",
            "selected_cells",
            "route_weights",
            "router_scores",
            "halt_probability",
        )
        require(session.outputNames.containsAll(requiredOutputs)) {
            "$label Agent model is missing required outputs"
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

    private fun floatOutput(
        result: OrtSession.Result,
        name: String,
    ): FloatArray {
        val value = result.get(name).orElseThrow {
            IllegalStateException("Missing ONNX output: $name")
        }
        val tensor = value as? OnnxTensor
            ?: throw IllegalStateException("$name is not a tensor")
        val buffer = tensor.floatBuffer
            ?: throw IllegalStateException("$name is not float")
        val output = FloatArray(buffer.remaining())
        buffer.get(output)
        return output
    }

    private fun longOutput(
        result: OrtSession.Result,
        name: String,
    ): LongArray {
        val value = result.get(name).orElseThrow {
            IllegalStateException("Missing ONNX output: $name")
        }
        val tensor = value as? OnnxTensor
            ?: throw IllegalStateException("$name is not a tensor")
        val buffer = tensor.longBuffer
            ?: throw IllegalStateException("$name is not int64")
        val output = LongArray(buffer.remaining())
        buffer.get(output)
        return output
    }

    @Synchronized
    override fun close() {
        closeSessions()
        info = null
        initialWorkspace = FloatArray(0)
        sparseState = RuntimeState(FloatArray(0), FloatArray(0))
        denseState = RuntimeState(FloatArray(0), FloatArray(0))
    }

    private fun closeSessions() {
        sparseSession?.close()
        denseSession?.close()
        sparseSession = null
        denseSession = null
    }
}
