package com.xonoxo.aiworkbench.agent

import java.util.UUID
import kotlin.math.max

private sealed interface Candidate {
    val id: String
    val confidence: Double
    val estimatedCost: Double
    val priority: Double

    data class CapabilityCandidate(
        val proposal: CapabilityProposal,
    ) : Candidate {
        override val id: String = proposal.capabilityId
        override val confidence: Double = proposal.confidence
        override val estimatedCost: Double = proposal.estimatedCost
        override val priority: Double = proposal.priority
    }

    data class MotifCandidate(
        val proposal: MotifProposal,
    ) : Candidate {
        override val id: String = proposal.motifId
        override val confidence: Double = proposal.confidence
        override val estimatedCost: Double = proposal.estimatedCost
        override val priority: Double = proposal.priority
    }
}

class AgentKernel(
    capabilities: Collection<Capability>,
    motifs: Collection<InteractionMotif> = emptyList(),
) {
    private val capabilitiesById = capabilities.associateBy { it.contract.id }
    private val motifsById = motifs.associateBy { it.contract.id }

    init {
        require(capabilitiesById.size == capabilities.size) { "Capability ids must be unique" }
        require(motifsById.size == motifs.size) { "Motif ids must be unique" }
    }

    fun runEpisode(
        episodeId: String = UUID.randomUUID().toString(),
        initialState: Map<String, AgentValue> = emptyMap(),
        unresolvedDependencies: Set<String> = emptySet(),
        initialPackets: List<PublicPacket> = emptyList(),
        budget: AgentBudget = AgentBudget(),
    ): EpisodeResult {
        require(initialState.size <= budget.maxActiveStateEntries) {
            "Initial active state exceeds budget"
        }
        require(initialPackets.size <= budget.maxPackets) {
            "Initial packet count exceeds budget"
        }
        require(initialPackets.all { it.payloadBytes() <= budget.maxPacketBytes }) {
            "Initial packet exceeds per-packet budget"
        }
        require(initialPackets.sumOf { it.payloadBytes() } <= budget.maxCommunicationBytes) {
            "Initial packets exceed communication budget"
        }

        val trace = mutableListOf<TraceEvent>()
        var eventCounter = 0L
        var packetCounter = 0L
        var step = 0
        var communicationBytes = initialPackets.sumOf { it.payloadBytes() }
        val state = initialState.toMutableMap()
        val unresolved = unresolvedDependencies.toMutableSet()
        val packets = initialPackets.toMutableList()
        val activeCapabilities = linkedSetOf<String>()
        val activeMotifs = linkedSetOf<String>()
        var action: PublicPacket? = null

        fun nextEventId(): String = "e${++eventCounter}"
        fun nextPacketId(): String = "p${++packetCounter}"

        fun appendTrace(
            type: TraceEventType,
            objectId: String? = null,
            parents: List<String> = emptyList(),
            durationNanos: Long? = null,
            details: Map<String, String> = emptyMap(),
        ): String {
            val id = nextEventId()
            trace += TraceEvent(
                episodeId = episodeId,
                eventId = id,
                parentEventIds = parents,
                step = step,
                type = type,
                objectId = objectId,
                timestampNanos = System.nanoTime(),
                durationNanos = durationNanos,
                details = details,
            )
            return id
        }

        fun snapshot(): AgentState = AgentState(
            episodeId = episodeId,
            step = step,
            activeState = state.toMap(),
            unresolvedDependencies = unresolved.toSet(),
            packets = packets.toList(),
            activeCapabilities = activeCapabilities.toSet(),
            activeMotifs = activeMotifs.toSet(),
            remainingBudget = RemainingBudget(
                steps = max(0, budget.maxSteps - step),
                packetSlots = max(0, budget.maxPackets - packets.size),
                communicationBytes = max(0, budget.maxCommunicationBytes - communicationBytes),
            ),
        )

        fun finish(reason: EpisodeTermination, details: Map<String, String> = emptyMap()): EpisodeResult {
            appendTrace(TraceEventType.TERMINATION, details = details + ("reason" to reason.name))
            return EpisodeResult(
                episodeId = episodeId,
                finalState = snapshot(),
                action = action,
                termination = reason,
                trace = trace.toList(),
            )
        }

        appendTrace(TraceEventType.EPISODE_START)

        fun candidateScore(candidate: Candidate): Double =
            candidate.priority * candidate.confidence / max(candidate.estimatedCost, 1e-9)

        fun proposalIsUsable(requiredStateKeys: Set<String>): Boolean =
            requiredStateKeys.all { state.containsKey(it) }

        fun executeCapability(capability: Capability, parentEventIds: List<String>): EpisodeTermination? {
            if (step >= budget.maxSteps) return EpisodeTermination.STEP_BUDGET_EXHAUSTED

            activeCapabilities += capability.contract.id
            val startId = appendTrace(
                TraceEventType.CAPABILITY_START,
                objectId = capability.contract.id,
                parents = parentEventIds,
                details = mapOf("contract_version" to capability.contract.contractVersion.toString()),
            )
            val started = System.nanoTime()

            val readableState = state.filterKeys { capability.contract.declaredStateReads.contains(it) }
            val visiblePackets = packets.filter {
                it.destination == null || it.destination == "*" || it.destination == capability.contract.id
            }

            val result = try {
                capability.execute(
                    CapabilityExecutionContext(
                        episodeId = episodeId,
                        step = step,
                        readableState = readableState,
                        unresolvedDependencies = unresolved.toSet(),
                        recentPackets = visiblePackets,
                    )
                )
            } catch (t: Throwable) {
                activeCapabilities -= capability.contract.id
                appendTrace(
                    TraceEventType.FAILURE,
                    objectId = capability.contract.id,
                    parents = listOf(startId),
                    details = mapOf("error" to (t.message ?: t.javaClass.simpleName)),
                )
                return EpisodeTermination.EXECUTION_FAILURE
            }

            val undeclaredWrites = result.stateWrites.keys - capability.contract.declaredStateWrites
            val allEmissions = result.emissions + listOfNotNull(result.action)
            val undeclaredOutputTypes = allEmissions
                .map { it.publicType }
                .filterNot { capability.contract.publicOutputTypes.contains(it) }
                .toSet()

            if (undeclaredWrites.isNotEmpty() || undeclaredOutputTypes.isNotEmpty()) {
                activeCapabilities -= capability.contract.id
                appendTrace(
                    TraceEventType.FAILURE,
                    objectId = capability.contract.id,
                    parents = listOf(startId),
                    details = buildMap {
                        if (undeclaredWrites.isNotEmpty()) {
                            put("undeclared_state_writes", undeclaredWrites.sorted().joinToString(","))
                        }
                        if (undeclaredOutputTypes.isNotEmpty()) {
                            put("undeclared_output_types", undeclaredOutputTypes.sorted().joinToString(","))
                        }
                    },
                )
                return EpisodeTermination.INVALID_CAPABILITY_OUTPUT
            }

            val projectedStateSize = (state.keys + result.stateWrites.keys).size
            if (projectedStateSize > budget.maxActiveStateEntries) {
                activeCapabilities -= capability.contract.id
                return EpisodeTermination.ACTIVE_STATE_BUDGET_EXCEEDED
            }

            val outgoingBytes = allEmissions.sumOf { it.payloadBytes() }
            val packetCount = allEmissions.size
            val violatesCommunicationBudget =
                allEmissions.any { it.payloadBytes() > budget.maxPacketBytes } ||
                    packets.size + packetCount > budget.maxPackets ||
                    communicationBytes + outgoingBytes > budget.maxCommunicationBytes

            if (violatesCommunicationBudget) {
                activeCapabilities -= capability.contract.id
                return EpisodeTermination.COMMUNICATION_BUDGET_EXCEEDED
            }

            step += 1

            for ((key, value) in result.stateWrites) {
                state[key] = value
                appendTrace(
                    TraceEventType.STATE_WRITE,
                    objectId = capability.contract.id,
                    parents = listOf(startId),
                    details = mapOf("key" to key),
                )
            }

            unresolved += result.openedDependencies
            unresolved -= result.resolvedDependencies

            fun materialize(emission: PacketEmission): PublicPacket {
                val packet = PublicPacket(
                    packetId = nextPacketId(),
                    source = capability.contract.id,
                    destination = emission.destination,
                    channel = emission.channel,
                    publicType = emission.publicType,
                    payload = emission.payload,
                    ttl = emission.ttl,
                    provenanceParent = startId,
                )
                packets += packet
                communicationBytes += packet.payloadBytes()
                appendTrace(
                    TraceEventType.PACKET_EMITTED,
                    objectId = capability.contract.id,
                    parents = listOf(startId),
                    details = mapOf(
                        "packet_id" to packet.packetId,
                        "public_type" to packet.publicType,
                        "payload_bytes" to packet.payloadBytes().toString(),
                    ),
                )
                return packet
            }

            result.emissions.forEach(::materialize)
            if (result.action != null) {
                action = materialize(result.action)
                appendTrace(
                    TraceEventType.ACTION,
                    objectId = capability.contract.id,
                    parents = listOf(startId),
                    details = mapOf("packet_id" to action!!.packetId),
                )
            }

            val duration = System.nanoTime() - started
            appendTrace(
                TraceEventType.CAPABILITY_END,
                objectId = capability.contract.id,
                parents = listOf(startId),
                durationNanos = duration,
            )
            activeCapabilities -= capability.contract.id
            return null
        }

        while (true) {
            if (step >= budget.maxSteps) {
                return finish(EpisodeTermination.STEP_BUDGET_EXHAUSTED)
            }

            val current = snapshot()
            val candidates = mutableListOf<Candidate>()

            for (capability in capabilitiesById.values) {
                val proposal = capability.propose(current) ?: continue
                if (proposal.capabilityId != capability.contract.id) continue
                if (!proposalIsUsable(proposal.requiredStateKeys)) continue
                appendTrace(
                    TraceEventType.CAPABILITY_PROPOSAL,
                    objectId = capability.contract.id,
                    details = mapOf(
                        "confidence" to proposal.confidence.toString(),
                        "estimated_cost" to proposal.estimatedCost.toString(),
                        "priority" to proposal.priority.toString(),
                    ),
                )
                candidates += Candidate.CapabilityCandidate(proposal)
            }

            for (motif in motifsById.values) {
                val proposal = motif.propose(current) ?: continue
                if (proposal.motifId != motif.contract.id) continue
                if (!proposalIsUsable(proposal.requiredStateKeys)) continue
                appendTrace(
                    TraceEventType.MOTIF_PROPOSAL,
                    objectId = motif.contract.id,
                    details = mapOf(
                        "confidence" to proposal.confidence.toString(),
                        "estimated_cost" to proposal.estimatedCost.toString(),
                        "priority" to proposal.priority.toString(),
                        "capabilities" to proposal.orderedCapabilityIds.joinToString(","),
                    ),
                )
                candidates += Candidate.MotifCandidate(proposal)
            }

            if (candidates.isEmpty()) {
                return finish(EpisodeTermination.NO_RUNNABLE_WORK)
            }

            val selected = candidates
                .sortedWith(
                    compareByDescending<Candidate> { candidateScore(it) }
                        .thenBy { it.id }
                )
                .first()

            val selectionId = appendTrace(
                TraceEventType.SELECTION,
                objectId = selected.id,
                details = mapOf(
                    "score" to candidateScore(selected).toString(),
                    "kind" to if (selected is Candidate.MotifCandidate) "motif" else "capability",
                ),
            )

            when (selected) {
                is Candidate.CapabilityCandidate -> {
                    val capability = capabilitiesById[selected.proposal.capabilityId]
                        ?: return finish(EpisodeTermination.INVALID_CAPABILITY_OUTPUT)
                    val failure = executeCapability(capability, listOf(selectionId))
                    if (failure != null) return finish(failure)
                    if (action != null) return finish(EpisodeTermination.ACTION_PRODUCED)
                }

                is Candidate.MotifCandidate -> {
                    val motif = motifsById[selected.proposal.motifId]
                        ?: return finish(EpisodeTermination.INVALID_MOTIF)
                    val orderedIds = selected.proposal.orderedCapabilityIds
                    if (orderedIds.isEmpty() || orderedIds.any { !capabilitiesById.containsKey(it) }) {
                        appendTrace(
                            TraceEventType.FAILURE,
                            objectId = motif.contract.id,
                            parents = listOf(selectionId),
                            details = mapOf("error" to "Motif references no capabilities or an unknown capability"),
                        )
                        return finish(EpisodeTermination.INVALID_MOTIF)
                    }

                    activeMotifs += motif.contract.id
                    val motifStart = appendTrace(
                        TraceEventType.MOTIF_START,
                        objectId = motif.contract.id,
                        parents = listOf(selectionId),
                        details = mapOf("capabilities" to orderedIds.joinToString(",")),
                    )

                    for (capabilityId in orderedIds) {
                        val capability = capabilitiesById.getValue(capabilityId)
                        val failure = executeCapability(capability, listOf(motifStart))
                        if (failure != null) {
                            activeMotifs -= motif.contract.id
                            return finish(failure)
                        }
                        if (action != null) break
                    }

                    appendTrace(
                        TraceEventType.MOTIF_END,
                        objectId = motif.contract.id,
                        parents = listOf(motifStart),
                    )
                    activeMotifs -= motif.contract.id
                    if (action != null) return finish(EpisodeTermination.ACTION_PRODUCED)
                }
            }
        }
    }
}
