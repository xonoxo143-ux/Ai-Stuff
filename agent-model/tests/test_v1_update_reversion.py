import copy

import torch

from agent_ecology.capacity_world import CapacityWorldConfig
from agent_ecology.interference_world import BlockedFamilyWorld
from agent_ecology.model import EcologyConfig, SparseRecurrentEcology
from agent_ecology.v1_update_reversion import (
    _private_snapshot,
    _set_private_rows,
    _rank,
)


def test_private_row_reversion_and_restore_are_exact():
    torch.manual_seed(1)
    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=4,
            sequence_length=2,
            seed=2,
        )
    )
    model = SparseRecurrentEcology(
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
    )

    before = _private_snapshot(model)
    with torch.no_grad():
        model.w_ih[3].add_(1.0)
        model.w_msg[3].sub_(2.0)
    after = _private_snapshot(model)

    _set_private_rows(model, [3], before)
    assert torch.equal(model.w_ih[3], before["w_ih"][3])
    assert torch.equal(model.w_msg[3], before["w_msg"][3])

    _set_private_rows(model, [3], after)
    assert torch.equal(model.w_ih[3], after["w_ih"][3])
    assert torch.equal(model.w_msg[3], after["w_msg"][3])


def test_rank_direction_is_stable():
    scores = [0.1, -0.2, 0.8, 0.3, 0.0]

    assert _rank(scores, 2, True) == [2, 3]
    assert _rank(scores, 2, False) == [1, 4]
