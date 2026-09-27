import copy

import torch

from agent_ecology.capacity_world import CapacityWorldConfig
from agent_ecology.interference_world import BlockedFamilyWorld
from agent_ecology.model import EcologyConfig, SparseRecurrentEcology
from agent_ecology.v1_selective_isolation import (
    _PRIVATE_CELL_NAMES,
    _select_cell_sets,
    _train_family,
)


def test_cell_selection_is_matched_and_deterministic():
    usage = [
        0.30, 0.20, 0.15, 0.10,
        0.08, 0.06, 0.04, 0.03,
        0.02, 0.01, 0.005, 0.005,
        0.0, 0.0, 0.0, 0.0,
    ]
    first = _select_cell_sets(
        usage,
        random_seed=123,
        width=4,
    )
    second = _select_cell_sets(
        usage,
        random_seed=123,
        width=4,
    )

    assert first == second
    assert first["freeze_old_top4"] == [0, 1, 2, 3]
    assert first["freeze_old_bottom4"] == [12, 13, 14, 15]
    assert len(first["freeze_random4"]) == 4
    assert set(first["freeze_random4"]).isdisjoint({0, 1, 2, 3})


def test_masked_private_rows_remain_exactly_unchanged():
    torch.manual_seed(5)

    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=4,
            sequence_length=2,
            seed=6,
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
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=1e-3,
        weight_decay=1e-4,
    )
    state = model.initial_state(1)

    frozen = [0, 3]
    named_before = dict(model.named_parameters())
    before = {
        name: named_before[name].detach()[frozen].clone()
        for name in _PRIVATE_CELL_NAMES
    }

    _train_family(
        model,
        optimizer,
        state,
        world,
        0,
        train_examples=3,
        thought_steps=1,
        balance_weight=0.0,
        frozen_private_cells=frozen,
    )

    named_after = dict(model.named_parameters())
    for name in _PRIVATE_CELL_NAMES:
        assert torch.equal(
            before[name],
            named_after[name].detach()[frozen],
        )


def test_unfrozen_private_rows_can_change():
    torch.manual_seed(7)

    world = BlockedFamilyWorld(
        CapacityWorldConfig(
            num_families=4,
            sequence_length=2,
            seed=8,
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
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=1e-3,
        weight_decay=0.0,
    )
    state = model.initial_state(1)

    before = copy.deepcopy(model.w_ih.detach())

    _train_family(
        model,
        optimizer,
        state,
        world,
        0,
        train_examples=4,
        thought_steps=1,
        balance_weight=0.0,
        frozen_private_cells=[0],
    )

    delta = (model.w_ih.detach() - before).abs().reshape(8, -1).sum(dim=1)
    assert float(delta[0]) == 0.0
    assert float(delta[1:].max()) > 0.0
