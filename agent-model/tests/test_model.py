import torch

from agent_ecology.model import EcologyConfig, SparseRecurrentEcology


def tiny_model() -> SparseRecurrentEcology:
    torch.manual_seed(3)
    return SparseRecurrentEcology(
        EcologyConfig(
            event_dim=7,
            output_dim=2,
            num_cells=8,
            active_cells=2,
            state_dim=24,
            workspace_slots=3,
            signature_dim=12,
            message_dim=10,
            max_thought_steps=3,
            min_thought_steps=1,
            routing_noise_std=0.0,
        )
    )


def test_only_top_k_private_states_change():
    model = tiny_model().eval()
    state = model.initial_state(4)
    event = torch.randn(4, 7)

    (
        _output,
        _workspace,
        new_states,
        selected,
        _weights,
        _scores,
        _halt,
    ) = model.thought_step(
        event,
        state.workspace,
        state.cell_states,
        add_training_noise=False,
    )

    changed = (new_states - state.cell_states).abs().sum(dim=-1) > 1e-7

    for batch_index in range(event.shape[0]):
        changed_ids = set(
            torch.nonzero(changed[batch_index], as_tuple=False)
            .flatten()
            .tolist()
        )
        selected_ids = set(selected[batch_index].tolist())
        assert changed_ids.issubset(selected_ids)
        assert len(selected_ids) == model.config.active_cells


def test_state_persists_between_external_events():
    model = tiny_model().eval()
    events = torch.randn(2, 2, 7)

    outputs, state, traces = model(
        events,
        force_steps=2,
        add_training_noise=False,
        return_trace=True,
    )

    assert outputs.shape == (2, 2, 2)
    assert state.workspace.shape == (2, 3, 24)
    assert state.cell_states.shape == (2, 8, 24)
    assert len(traces) == 2
    assert not torch.allclose(
        state.cell_states,
        torch.zeros_like(state.cell_states),
    )


def test_router_selects_exact_sparse_budget():
    model = tiny_model().eval()
    event = torch.randn(5, 7)
    state = model.initial_state(5)

    result = model.thought_step(
        event,
        state.workspace,
        state.cell_states,
        add_training_noise=False,
    )

    selected = result[3]
    weights = result[4]

    assert selected.shape == (5, 2)
    assert weights.shape == (5, 2)
    assert torch.allclose(
        weights.sum(dim=-1),
        torch.ones(5),
        atol=1e-6,
    )


def test_gradients_reach_private_cell_weights():
    model = tiny_model().train()
    event = torch.randn(3, 7)
    state = model.initial_state(3)

    output, *_ = model.thought_step(
        event,
        state.workspace,
        state.cell_states,
        add_training_noise=False,
    )
    loss = output.square().mean()
    loss.backward()

    assert model.w_ih.grad is not None
    assert model.w_msg.grad is not None
    assert float(model.w_ih.grad.abs().sum()) > 0.0
    assert float(model.w_msg.grad.abs().sum()) > 0.0


def test_parameter_count_is_nontrivial_but_small():
    model = tiny_model()
    count = model.parameter_count()
    assert count > 10_000
    assert count < 5_000_000


def test_sparse_and_dense_reference_are_semantically_equivalent():
    model = tiny_model().eval()
    event = torch.randn(4, 7)
    state = model.initial_state(4)

    sparse = model.thought_step(
        event,
        state.workspace,
        state.cell_states,
        add_training_noise=False,
    )
    dense = model.thought_step_dense_reference(
        event,
        state.workspace,
        state.cell_states,
    )

    for sparse_value, dense_value in zip(sparse, dense):
        if sparse_value.dtype in (torch.int32, torch.int64):
            assert torch.equal(sparse_value, dense_value)
        else:
            assert torch.allclose(
                sparse_value,
                dense_value,
                atol=2e-5,
                rtol=2e-5,
            )
