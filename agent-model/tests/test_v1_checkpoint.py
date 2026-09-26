import pytest

from agent_ecology.lifetime_world import LifetimeWorldConfig
from agent_ecology.v1_checkpoint import (
    V1Checkpoint,
    load_checkpoint,
    save_checkpoint,
)


def test_checkpoint_round_trip(tmp_path):
    config = LifetimeWorldConfig(
        total_experiences=1_000,
        seed=41,
    )
    checkpoint = V1Checkpoint.for_world(
        config,
        next_experience=377,
    )

    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, checkpoint)
    loaded = load_checkpoint(path)

    assert loaded == checkpoint
    loaded.validate_world(config)


def test_checkpoint_rejects_different_world():
    config = LifetimeWorldConfig(
        total_experiences=1_000,
        seed=41,
    )
    checkpoint = V1Checkpoint.for_world(
        config,
        next_experience=377,
    )

    with pytest.raises(ValueError):
        checkpoint.validate_world(
            LifetimeWorldConfig(
                total_experiences=1_000,
                seed=42,
            )
        )
