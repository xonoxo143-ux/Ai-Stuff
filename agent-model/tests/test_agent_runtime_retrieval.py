from pathlib import Path

from agent_runtime.contracts import (
    CapabilityContext,
)
from agent_runtime.memory import AgentMemory
from agent_runtime.retrieval import (
    SemanticRetrievalCapability,
)
from agent_runtime.sqlite_memory import (
    SQLiteAgentMemory,
)


def context(text: str) -> CapabilityContext:
    return CapabilityContext(
        turn_id=1,
        user_text=text,
        active_state={},
        recent_episodes=(),
        semantic_memory={},
    )


def test_in_memory_semantic_search_is_selective():
    memory = AgentMemory()
    memory.semantic.update(
        {
            "favorite_fruit": "mango",
            "phone_model":
                "Samsung Galaxy Fold 4",
            "unrelated": "blue bicycle",
        }
    )
    rows = memory.search_semantic(
        "what is my favorite fruit?",
        limit=2,
    )
    assert rows[0]["key"] == (
        "favorite_fruit"
    )
    assert rows[0]["value"] == "mango"
    assert all(
        row["key"] != "unrelated"
        for row in rows
    )


def test_sqlite_fts_semantic_search_survives_restart(
    tmp_path: Path,
):
    path = tmp_path / "memory.sqlite3"
    memory = SQLiteAgentMemory(path)
    memory.update_semantic(
        {
            "favorite_fruit": "mango",
            "github_branch":
                (
                    "experiment agent v1 "
                    "developmental ecology"
                ),
            "phone_model":
                "Samsung Galaxy Fold 4",
        }
    )
    assert (
        memory.search_semantic(
            "which github branch are we using?"
        )[0]["key"]
        == "github_branch"
    )
    memory.close()

    reopened = SQLiteAgentMemory(path)
    result = reopened.search_semantic(
        "what is my favorite fruit?"
    )
    assert result[0]["key"] == (
        "favorite_fruit"
    )
    assert result[0]["value"] == "mango"
    reopened.close()


def test_retrieval_capability_stays_asleep_when_irrelevant():
    memory = AgentMemory()
    memory.semantic["favorite_fruit"] = (
        "mango"
    )
    capability = (
        SemanticRetrievalCapability(
            memory,
            min_score=0.25,
        )
    )
    assert (
        capability.offer(
            context(
                "explain matrix multiplication"
            )
        )
        is None
    )


def test_retrieval_capability_emits_bounded_fact():
    memory = AgentMemory()
    memory.semantic.update(
        {
            "favorite_fruit": "mango",
            "phone_model":
                "Samsung Galaxy Fold 4",
        }
    )
    capability = (
        SemanticRetrievalCapability(
            memory,
            limit=1,
        )
    )
    ctx = context(
        "what is my favorite fruit?"
    )
    offer = capability.offer(ctx)
    assert offer is not None
    result = capability.run(ctx)
    assert len(result.messages) == 1
    assert (
        result.messages[0].content
        == "favorite_fruit=mango"
    )
    assert (
        result.messages[0].metadata[
            "memory_key"
        ]
        == "favorite_fruit"
    )
