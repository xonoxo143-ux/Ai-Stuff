from agent_runtime.baselines import (
    ArithmeticCapability,
    EchoComposer,
    RememberCapability,
)
from agent_runtime.contracts import (
    CapabilityOffer,
    CapabilityResult,
    CapabilityRole,
)
from agent_runtime.memory import AgentMemory, MemoryConfig
from agent_runtime.runtime import AgentRuntime, RuntimeConfig


def make_runtime(**config):
    return AgentRuntime(
        composer=EchoComposer(),
        contributors=[
            ArithmeticCapability(),
            RememberCapability(),
        ],
        memory=AgentMemory(
            MemoryConfig(
                max_active_items=8,
                max_recent_episodes=8,
            )
        ),
        config=RuntimeConfig(**config),
    )


def test_plain_turn_uses_only_composer():
    runtime = make_runtime()
    response, trace = runtime.turn("hello")
    assert response == "hello"
    selected = [
        e.capability
        for e in trace.executions
        if e.selected
    ]
    assert selected == ["echo-composer"]
    assert runtime.memory.active["last_user_text"] == "hello"
    assert len(runtime.memory.episodes) == 2


def test_arithmetic_is_recruited_and_composed():
    runtime = make_runtime()
    response, trace = runtime.turn("2 + 3 * 4")
    assert "arithmetic=14" in response
    selected = [
        e.capability
        for e in trace.executions
        if e.selected
    ]
    assert "arithmetic" in selected
    assert "remember" not in selected


def test_semantic_memory_is_separate_from_active_and_episode_memory():
    runtime = make_runtime()
    runtime.turn("remember favorite = mango")
    assert runtime.memory.semantic["favorite"] == "mango"
    assert (
        runtime.memory.active["last_user_text"]
        == "remember favorite = mango"
    )
    assert runtime.memory.episodes[-2]["role"] == "user"
    assert (
        runtime.memory.capability_stats["remember"]["calls"]
        == 1.0
    )


def test_budget_can_block_a_relevant_capability():
    runtime = make_runtime(contributor_budget=0.01)
    response, trace = runtime.turn("6 * 7")
    assert response == "6 * 7"
    arithmetic = next(
        e
        for e in trace.executions
        if e.capability == "arithmetic"
    )
    assert arithmetic.offered_relevance == 1.0
    assert arithmetic.selected is False


def test_turn_trace_is_json_shape_and_deterministic_selection():
    runtime = make_runtime(max_contributors=1)
    _response, trace = runtime.turn("8 / 2")
    payload = trace.to_dict()
    assert payload["turn_id"] == 1
    assert payload["offers"][0]["capability"] == "arithmetic"
    assert any(
        row["capability"] == "echo-composer"
        for row in payload["executions"]
    )


def test_state_persists_across_turns_without_parametric_learning():
    runtime = make_runtime()
    runtime.turn("first")
    runtime.turn("second")
    assert runtime.turn_id == 2
    assert runtime.memory.active["last_user_text"] == "second"
    assert [
        e["text"]
        for e in runtime.memory.episodes
        if e["role"] == "user"
    ] == ["first", "second"]


class BrokenCapability:
    name = "broken"
    role = CapabilityRole.CONTRIBUTOR
    contract_version = "0.1"

    def offer(self, context):
        return CapabilityOffer(
            self.name,
            relevance=2.0,
            estimated_cost=0.0,
        )

    def run(self, context):
        raise RuntimeError("boom")


def test_contributor_failure_is_traced_not_fatal():
    runtime = AgentRuntime(
        composer=EchoComposer(),
        contributors=[BrokenCapability()],
    )
    response, trace = runtime.turn("hello")
    assert response == "hello"
    broken = next(
        e
        for e in trace.executions
        if e.capability == "broken"
    )
    assert broken.selected is True
    assert broken.success is False
    assert "boom" in broken.error
    assert (
        runtime.memory.capability_stats["broken"]["successes"]
        == 0.0
    )


def test_active_state_is_bounded():
    memory = AgentMemory(
        MemoryConfig(
            max_active_items=2,
            max_recent_episodes=8,
        )
    )
    memory.update_active({"a": 1, "b": 2, "c": 3})
    assert list(memory.active) == ["b", "c"]
