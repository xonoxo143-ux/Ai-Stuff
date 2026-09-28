from pathlib import Path

from agent_runtime.baselines import (
    EchoComposer,
    RememberCapability,
)
from agent_runtime.memory import MemoryConfig
from agent_runtime.runtime import AgentRuntime
from agent_runtime.sqlite_memory import (
    SQLiteAgentMemory,
)


def test_sqlite_memory_survives_runtime_restart(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "agent-memory.sqlite3"
    )
    memory = SQLiteAgentMemory(path)
    runtime = AgentRuntime(
        composer=EchoComposer(),
        contributors=[
            RememberCapability()
        ],
        memory=memory,
    )
    runtime.turn(
        "remember favorite = mango"
    )
    assert runtime.turn_id == 1
    memory.close()

    reopened = SQLiteAgentMemory(path)
    assert (
        reopened.semantic["favorite"]
        == "mango"
    )
    assert reopened.last_turn_id() == 1

    runtime2 = AgentRuntime(
        composer=EchoComposer(),
        memory=reopened,
    )
    assert runtime2.turn_id == 1
    runtime2.turn("hello again")
    assert runtime2.turn_id == 2
    assert reopened.last_turn_id() == 2
    assert len(reopened.episodes) == 4
    reopened.close()


def test_sqlite_active_state_is_bounded_and_ordered(
    tmp_path: Path,
):
    memory = SQLiteAgentMemory(
        tmp_path / "bounded.sqlite3",
        MemoryConfig(
            max_active_items=2,
            max_recent_episodes=4,
        ),
    )
    memory.update_active(
        {"a": 1, "b": 2}
    )
    memory.update_active(
        {"a": 3}
    )
    memory.update_active(
        {"c": 4}
    )
    assert list(memory.active) == [
        "a",
        "c",
    ]
    assert memory.active == {
        "a": 3,
        "c": 4,
    }
    memory.close()


def test_sqlite_recent_episode_window_and_capability_stats(
    tmp_path: Path,
):
    memory = SQLiteAgentMemory(
        tmp_path / "window.sqlite3",
        MemoryConfig(
            max_recent_episodes=2
        ),
    )
    for turn in range(1, 4):
        memory.append_episode(
            {
                "turn": turn,
                "role": "user",
                "text": str(turn),
            }
        )

    assert [
        event["turn"]
        for event
        in memory.recent_episodes()
    ] == [2, 3]

    memory.record_capability(
        "x",
        success=True,
        cost=0.25,
    )
    memory.record_capability(
        "x",
        success=False,
        cost=0.75,
    )
    assert (
        memory.capability_stats["x"]
        == {
            "calls": 2.0,
            "successes": 1.0,
            "total_cost": 1.0,
        }
    )
    memory.close()
