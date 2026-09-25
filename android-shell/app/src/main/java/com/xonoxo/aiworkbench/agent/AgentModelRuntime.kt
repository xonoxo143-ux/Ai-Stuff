package com.xonoxo.aiworkbench.agent

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.json.JSONObject
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

data class AgentModelInfo(
    val modelId: String,
    val eventDim: Int,
    val outputDim: Int,
    val numCells: Int,
    val activeCells: Int,
    val stateDim: Int,
    val workspaceSlots: Int,
    val thoughtSteps: Int,
)

data class AgentThoughtResult(
    val output: FloatArray,
    val selectedCells: IntArray,
    val routeWeights: FloatArray,
    val routerScores: FloatArray,
    val haltProbability: Float,
    val latencyNanos: Long,
)

/**
 * Thin Android host for the learned ecology's ONNX thought-step model.
 *
 * The ONNX graph performs one internal cognitive transition. The Agent Kernel,
 * not this class, decides how many transitions to run and how they participate
 * in the wider capability/motif ecology.
 */
class AgentModelRuntime : Closeable {
    private val environment = OrtEnvironment.getEnvironment()

    private var session: OrtSession? = null
    private var info: AgentModelInfo? = null
    private var initialWorkspace = FloatArray(0)
    private var workspace = FloatArray(0)
    private var cellStates = FloatArray(0)

    @Synchronized
    fun load(
        modelPath: String,
        manifestText: String,
        threads: Int = 4,
    ): AgentModelInfo {
        closeSession()

        val manifest = JSONObject(manifestText)
        require(manifest.getInt("schema") == 1) {
            "Unsupported Agent model manifest schema"
        }
        val config = manifest.getJSONObject("config")

        val loadedInfo = AgentModelInfo(
            modelId = manifest.getString("model_id"),
            eventDim = config.getInt("event_dim"),
            outputDim = config.getInt("output_dim"),
            numCells = config.getInt("num_cells"),
            activeCells = config.getInt("active_cells"),
            stateDim = config.getInt("state_dim"),
            workspaceSlots = config.getInt("workspace_slots"),
            thoughtSteps = config.getInt("max_thought_steps"),
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

        val options = OrtSession.SessionOptions()
        try {
            options.setOptimizationLevel(
                OrtSession.SessionOptions.OptLevel.ALL_OPT
            )
            options.setIntraOpNumThreads(threads.coerceAtLeast(1))
            options.setInterOpNumThreads(1)
            session = environment.createSession(modelPath, options)
        } finally {
            options.close()
        }

        val loadedSession = requireNotNull(session)
        val requiredInputs = setOf("event", "workspace", "cell_states")
        require(loadedSession.inputNames.containsAll(requiredInputs)) {
            "Agent model is missing required inputs"
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
        require(loadedSession.outputNames.containsAll(requiredOutputs)) {
            "Agent model is missing required outputs"
        }

        info = loadedInfo
        initialWorkspace = flattened
        reset()
        return loadedInfo
    }

    @Synchronized
    fun reset() {
        val loadedInfo = info ?: return
        workspace = initialWorkspace.copyOf()
        cellStates = FloatArray(
            loadedInfo.numCells * loadedInfo.stateDim
        )
    }

    @Synchronized
    fun isLoaded(): Boolean = session != null

    @Synchronized
    fun modelInfo(): AgentModelInfo? = info

    @Synchronized
    fun thoughtStep(event: FloatArray): AgentThoughtResult {
        val loadedSession = checkNotNull(session) {
            "Agent model is not loaded"
        }
        val loadedInfo = checkNotNull(info) {
            "Agent model metadata is not loaded"
        }
        require(event.size == loadedInfo.eventDim) {
            "Expected event dimension ${loadedInfo.eventDim}, got ${event.size}"
        }

        val started = System.nanoTime()

        OnnxTensor.createTensor(
            environment,
            directFloatBuffer(event),
            longArrayOf(1, loadedInfo.eventDim.toLong()),
        ).use { eventTensor ->
            OnnxTensor.createTensor(
                environment,
                directFloatBuffer(workspace),
                longArrayOf(
                    1,
                    loadedInfo.workspaceSlots.toLong(),
                    loadedInfo.stateDim.toLong(),
                ),
            ).use { workspaceTensor ->
                OnnxTensor.createTensor(
                    environment,
                    directFloatBuffer(cellStates),
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
                        workspace = floatOutput(result, "new_workspace")
                        cellStates = floatOutput(result, "new_cell_states")
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
        closeSession()
        info = null
        initialWorkspace = FloatArray(0)
        workspace = FloatArray(0)
        cellStates = FloatArray(0)
    }

    private fun closeSession() {
        session?.close()
        session = null
    }
}
