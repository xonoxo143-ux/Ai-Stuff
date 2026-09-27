import torch

from agent_ecology.capacity_world import CapacityWorldConfig
from agent_ecology.interference_world import BlockedFamilyWorld
from agent_ecology.model import EcologyConfig, SparseRecurrentEcology
from agent_ecology.v1_causal_isolation import (
    _build_cell_sets,
    causal_cell_scores,
)


def _tiny_model(world):
    return SparseRecurrentEcology(
        EcologyConfig(
            event_dim=world.config.event_dim,
            output_dim=1,
            num_cells=8,
            active_cells=2,
            state_dim=12,
            workspace_slots=2,
            signature_dim=8,
            message_dim=8,
            max_thought_steps=1,
            min_thought_steps=1,
            routing_noise_std=0.0,
            dense_training_compute=True,
        )
    ).eval()


def test_causal_scores_are_deterministic_and_per_cell():
    torch.manual_seed(3)
    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=4,
            sequence_length=2,
            seed=4,
        )
    )
    model = _tiny_model(world)

    first = causal_cell_scores(
        model,
        world,
        [0, 1],
        eval_examples=2,
        thought_steps=1,
    )
    second = causal_cell_scores(
        model,
        world,
        [0, 1],
        eval_examples=2,
        thought_steps=1,
    )

    assert len(first) == model.config.num_cells
    assert first == second


def test_causal_cell_sets_are_matched_and_random_excludes_top():
    scores = [0.8, 0.7, 0.6, 0.5, 0.1, 0.0, -0.1, -0.2]
    usage = [0.0, 0.0, 0.1, 0.1, 0.2, 0.25, 0.2, 0.15]

    sets = _build_cell_sets(
        causal_scores=scores,
        usage=usage,
        random_seed=99,
        width=2,
    )

    assert sets["freeze_causal_top4"] == [0, 1]
    assert sets["freeze_causal_bottom4"] == [7, 6]
    assert sets["freeze_usage_top4"] == [5, 4]
    assert len(sets["freeze_random4"]) == 2
    assert set(sets["freeze_random4"]).isdisjoint({0, 1})
    assert sets["freeze_all_private"] == list(range(8))
