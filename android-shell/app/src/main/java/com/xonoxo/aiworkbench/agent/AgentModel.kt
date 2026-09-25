package com.xonoxo.aiworkbench.agent

import java.nio.charset.StandardCharsets

enum class CapabilityOrigin {
    EXPLICIT,
    LEARNED,
    COMPOSITE
}

sealed interface AgentValue {
    fun payloadBytes(): Int

    data class Text(val value: String) : AgentValue {
        override fun payloadBytes(): Int = value.toByteArray(StandardCharsets.UTF_8).size
    }

    data class Scalar(val value: Double) : AgentValue {
        override fun payloadBytes(): Int = 8
    }

    data class Flag(val value: Boolean) : AgentValue {
        override fun payloadBytes(): Int = 1
    }

    data class Symbols(val values: List<Int>) : AgentValue {
        override fun payloadBytes(): Int = values.size * 4
    }

    data class Scalars(val values: List<Double>) : AgentValue {
        override fun payloadBytes(): Int = values.size * 8
    }

    data class Reference(val id: String) : AgentValue {
        override fun payloadBytes(): Int = id.toByteArray(StandardCharsets.UTF_8).size
    }
}

data class CapabilityContract(
    val id: String,
    val contractVersion: Int = 1,
    val origin: CapabilityOrigin,
    val applicabilityDescription: String = "",
    val acceptedInputTypes: Set<String> = emptySet(),
    val publicOutputTypes: Set<String> = emptySet(),
    val declaredStateReads: Set<String> = emptySet(),
    val declaredStateWrites: Set<String> = emptySet(),
    val estimatedCost: Double = 1.0,
    val reliability: Double = 1.0,
    val provenance: List<String> = emptyList(),
    val implementationRef: String,
    val revalidationRequired: Boolean = false,
)

data class InteractionMotifContract(
    val id: String,
    val contractVersion: Int = 1,
    val participantRoles: List<String> = emptyList(),
    val contextDescription: String = "",
    val estimatedCost: Double = 1.0,
    val reliability: Double = 1.0,
    val provenance: List<String> = emptyList(),
    val revalidationRequired: Boolean = false,
)

data class PacketEmission(
    val destination: String? = null,
    val channel: String? = null,
    val publicType: String,
    val payload: List<AgentValue> = emptyList(),
    val ttl: Int = 1,
) {
    fun payloadBytes(): Int = payload.sumOf { it.payloadBytes() }
}

data class PublicPacket(
    val packetId: String,
    val source: String,
    val destination: String? = null,
    val channel: String? = null,
    val publicType: String,
    val payload: List<AgentValue> = emptyList(),
    val ttl: Int = 1,
    val provenanceParent: String? = null,
) {
    fun payloadBytes(): Int = payload.sumOf { it.payloadBytes() }
}

data class AgentBudget(
    val maxSteps: Int = 64,
    val maxActiveStateEntries: Int = 64,
    val maxPackets: Int = 64,
    val maxPacketBytes: Int = 1_024,
    val maxCommunicationBytes: Int = 8_192,
)

data class RemainingBudget(
    val steps: Int,
    val packetSlots: Int,
    val communicationBytes: Int,
)

data class AgentState(
    val episodeId: String,
    val step: Int,
    val activeState: Map<String, AgentValue>,
    val unresolvedDependencies: Set<String>,
    val packets: List<PublicPacket>,
    val activeCapabilities: Set<String>,
    val activeMotifs: Set<String>,
    val remainingBudget: RemainingBudget,
)

data class CapabilityProposal(
    val capabilityId: String,
    val confidence: Double,
    val estimatedCost: Double,
    val priority: Double = 1.0,
    val requiredStateKeys: Set<String> = emptySet(),
    val resolvesDependencies: Set<String> = emptySet(),
)

data class MotifProposal(
    val motifId: String,
    val orderedCapabilityIds: List<String>,
    val confidence: Double,
    val estimatedCost: Double,
    val priority: Double = 1.0,
    val requiredStateKeys: Set<String> = emptySet(),
    val resolvesDependencies: Set<String> = emptySet(),
)

data class CapabilityExecutionContext(
    val episodeId: String,
    val step: Int,
    val readableState: Map<String, AgentValue>,
    val unresolvedDependencies: Set<String>,
    val recentPackets: List<PublicPacket>,
)

data class CapabilityResult(
    val stateWrites: Map<String, AgentValue> = emptyMap(),
    val emissions: List<PacketEmission> = emptyList(),
    val resolvedDependencies: Set<String> = emptySet(),
    val openedDependencies: Set<String> = emptySet(),
    val action: PacketEmission? = null,
)

interface Capability {
    val contract: CapabilityContract

    fun propose(state: AgentState): CapabilityProposal?

    fun execute(context: CapabilityExecutionContext): CapabilityResult
}

interface InteractionMotif {
    val contract: InteractionMotifContract

    fun propose(state: AgentState): MotifProposal?
}

enum class TraceEventType {
    EPISODE_START,
    CAPABILITY_PROPOSAL,
    MOTIF_PROPOSAL,
    SELECTION,
    MOTIF_START,
    MOTIF_END,
    CAPABILITY_START,
    CAPABILITY_END,
    STATE_WRITE,
    PACKET_EMITTED,
    ACTION,
    FAILURE,
    TERMINATION,
}

data class TraceEvent(
    val episodeId: String,
    val eventId: String,
    val parentEventIds: List<String> = emptyList(),
    val step: Int,
    val type: TraceEventType,
    val objectId: String? = null,
    val timestampNanos: Long,
    val durationNanos: Long? = null,
    val details: Map<String, String> = emptyMap(),
)

enum class EpisodeTermination {
    ACTION_PRODUCED,
    NO_RUNNABLE_WORK,
    STEP_BUDGET_EXHAUSTED,
    ACTIVE_STATE_BUDGET_EXCEEDED,
    COMMUNICATION_BUDGET_EXCEEDED,
    INVALID_CAPABILITY_OUTPUT,
    INVALID_MOTIF,
    EXECUTION_FAILURE,
}

data class EpisodeResult(
    val episodeId: String,
    val finalState: AgentState,
    val action: PublicPacket?,
    val termination: EpisodeTermination,
    val trace: List<TraceEvent>,
)
