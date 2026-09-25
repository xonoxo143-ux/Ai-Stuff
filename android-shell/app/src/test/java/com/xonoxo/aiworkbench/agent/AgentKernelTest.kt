package com.xonoxo.aiworkbench.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentKernelTest {
    @Test
    fun `order-sensitive motif preserves causal order`() {
        val a = object : Capability {
            override val contract = CapabilityContract(
                id = "A",
                origin = CapabilityOrigin.EXPLICIT,
                declaredStateReads = setOf("order"),
                declaredStateWrites = setOf("order"),
                implementationRef = "test:A",
            )

            override fun propose(state: AgentState): CapabilityProposal? = null

            override fun execute(context: CapabilityExecutionContext): CapabilityResult {
                val current = (context.readableState["order"] as? AgentValue.Text)?.value.orEmpty()
                return CapabilityResult(
                    stateWrites = mapOf("order" to AgentValue.Text(current + "A")),
                )
            }
        }

        val b = object : Capability {
            override val contract = CapabilityContract(
                id = "B",
                origin = CapabilityOrigin.EXPLICIT,
                declaredStateReads = setOf("order"),
                declaredStateWrites = setOf("order", "done"),
                publicOutputTypes = setOf("result"),
                implementationRef = "test:B",
            )

            override fun propose(state: AgentState): CapabilityProposal? = null

            override fun execute(context: CapabilityExecutionContext): CapabilityResult {
                val current = (context.readableState["order"] as? AgentValue.Text)?.value.orEmpty()
                val next = current + "B"
                return CapabilityResult(
                    stateWrites = mapOf(
                        "order" to AgentValue.Text(next),
                        "done" to AgentValue.Flag(true),
                    ),
                    action = PacketEmission(
                        destination = "external",
                        publicType = "result",
                        payload = listOf(AgentValue.Text(next)),
                    ),
                )
            }
        }

        val motif = object : InteractionMotif {
            override val contract = InteractionMotifContract(
                id = "AB",
                participantRoles = listOf("first", "second"),
            )

            override fun propose(state: AgentState): MotifProposal? {
                if (state.activeState.containsKey("done")) return null
                return MotifProposal(
                    motifId = "AB",
                    orderedCapabilityIds = listOf("A", "B"),
                    confidence = 1.0,
                    estimatedCost = 2.0,
                )
            }
        }

        val result = AgentKernel(listOf(a, b), listOf(motif)).runEpisode(
            episodeId = "order-test",
            initialState = mapOf("order" to AgentValue.Text("")),
        )

        assertEquals(EpisodeTermination.ACTION_PRODUCED, result.termination)
        assertEquals("AB", (result.finalState.activeState["order"] as AgentValue.Text).value)
        assertEquals("AB", ((result.action!!.payload.single()) as AgentValue.Text).value)
        assertTrue(result.trace.any { it.type == TraceEventType.MOTIF_START && it.objectId == "AB" })
        assertEquals(
            listOf("A", "B"),
            result.trace
                .filter { it.type == TraceEventType.CAPABILITY_START }
                .mapNotNull { it.objectId },
        )
    }

    @Test
    fun `coalition can produce value that isolated members cannot`() {
        val seed = object : Capability {
            override val contract = CapabilityContract(
                id = "seed",
                origin = CapabilityOrigin.EXPLICIT,
                declaredStateWrites = setOf("shared"),
                implementationRef = "test:seed",
            )

            override fun propose(state: AgentState): CapabilityProposal? = null

            override fun execute(context: CapabilityExecutionContext) = CapabilityResult(
                stateWrites = mapOf("shared" to AgentValue.Scalar(2.0)),
            )
        }

        val combine = object : Capability {
            override val contract = CapabilityContract(
                id = "combine",
                origin = CapabilityOrigin.EXPLICIT,
                declaredStateReads = setOf("shared"),
                publicOutputTypes = setOf("result"),
                implementationRef = "test:combine",
            )

            override fun propose(state: AgentState): CapabilityProposal? = null

            override fun execute(context: CapabilityExecutionContext): CapabilityResult {
                val shared = context.readableState["shared"] as? AgentValue.Scalar
                    ?: return CapabilityResult()
                return CapabilityResult(
                    action = PacketEmission(
                        destination = "external",
                        publicType = "result",
                        payload = listOf(AgentValue.Scalar(shared.value * 3.0)),
                    ),
                )
            }
        }

        val coalition = object : InteractionMotif {
            override val contract = InteractionMotifContract(id = "seed+combine")

            override fun propose(state: AgentState) = MotifProposal(
                motifId = contract.id,
                orderedCapabilityIds = listOf("seed", "combine"),
                confidence = 1.0,
                estimatedCost = 2.0,
            )
        }

        val result = AgentKernel(listOf(seed, combine), listOf(coalition)).runEpisode(
            episodeId = "coalition-test",
        )

        assertEquals(EpisodeTermination.ACTION_PRODUCED, result.termination)
        assertEquals(6.0, (result.action!!.payload.single() as AgentValue.Scalar).value, 0.0)
    }

    @Test
    fun `bounded communication rejects oversized public output`() {
        val noisy = object : Capability {
            override val contract = CapabilityContract(
                id = "noisy",
                origin = CapabilityOrigin.EXPLICIT,
                publicOutputTypes = setOf("blob"),
                implementationRef = "test:noisy",
            )

            override fun propose(state: AgentState) = CapabilityProposal(
                capabilityId = contract.id,
                confidence = 1.0,
                estimatedCost = 1.0,
            )

            override fun execute(context: CapabilityExecutionContext) = CapabilityResult(
                emissions = listOf(
                    PacketEmission(
                        publicType = "blob",
                        payload = listOf(AgentValue.Text("too-large")),
                    )
                )
            )
        }

        val result = AgentKernel(listOf(noisy)).runEpisode(
            episodeId = "budget-test",
            budget = AgentBudget(maxPacketBytes = 4),
        )

        assertEquals(EpisodeTermination.COMMUNICATION_BUDGET_EXCEEDED, result.termination)
        assertTrue(result.finalState.packets.isEmpty())
    }

    @Test
    fun `capability cannot write undeclared active state`() {
        val invalid = object : Capability {
            override val contract = CapabilityContract(
                id = "invalid",
                origin = CapabilityOrigin.LEARNED,
                implementationRef = "test:learned",
            )

            override fun propose(state: AgentState) = CapabilityProposal(
                capabilityId = contract.id,
                confidence = 1.0,
                estimatedCost = 1.0,
            )

            override fun execute(context: CapabilityExecutionContext) = CapabilityResult(
                stateWrites = mapOf("hidden-leak" to AgentValue.Flag(true)),
            )
        }

        val result = AgentKernel(listOf(invalid)).runEpisode(episodeId = "contract-test")

        assertEquals(EpisodeTermination.INVALID_CAPABILITY_OUTPUT, result.termination)
        assertTrue("hidden-leak" !in result.finalState.activeState)
        assertTrue(result.trace.any { it.type == TraceEventType.FAILURE && it.objectId == "invalid" })
    }

    @Test
    fun `provenance links motif selection to capability execution`() {
        val leaf = object : Capability {
            override val contract = CapabilityContract(
                id = "leaf",
                origin = CapabilityOrigin.COMPOSITE,
                publicOutputTypes = setOf("result"),
                implementationRef = "test:composite",
            )

            override fun propose(state: AgentState): CapabilityProposal? = null

            override fun execute(context: CapabilityExecutionContext) = CapabilityResult(
                action = PacketEmission(
                    destination = "external",
                    publicType = "result",
                    payload = listOf(AgentValue.Flag(true)),
                )
            )
        }

        val motif = object : InteractionMotif {
            override val contract = InteractionMotifContract(id = "motif")

            override fun propose(state: AgentState) = MotifProposal(
                motifId = contract.id,
                orderedCapabilityIds = listOf("leaf"),
                confidence = 1.0,
                estimatedCost = 1.0,
            )
        }

        val result = AgentKernel(listOf(leaf), listOf(motif)).runEpisode(episodeId = "trace-test")

        val motifStart = result.trace.single { it.type == TraceEventType.MOTIF_START }
        val capabilityStart = result.trace.single { it.type == TraceEventType.CAPABILITY_START }
        val packet = result.action

        assertTrue(motifStart.eventId in capabilityStart.parentEventIds)
        assertNotNull(packet)
        assertEquals(capabilityStart.eventId, packet!!.provenanceParent)
    }
}
