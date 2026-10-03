import torch

from delta_hybrid.model_v1 import DeltaHybridV1
from delta_hybrid.persistent_state import StatefulDeltaHybridV1, state_size_bytes


def run(runner, x, segment=64):
    state = None
    sizes = []
    for start in range(0, x.shape[1], segment):
        out, state = runner.forward_segment(x[:, start:start + segment], state)
        assert torch.isfinite(out).all()
        sizes.append(state_size_bytes(state))
    return state, sizes


def test_bounded_attention_history_plateaus():
    torch.manual_seed(1)
    model = DeltaHybridV1().eval()
    runner = StatefulDeltaHybridV1(model, max_attention_history=64)
    x = torch.randint(0, 256, (2, 512))
    state, sizes = run(runner, x)
    assert state.attention.hidden.shape[1] == 64
    assert all(size == sizes[0] for size in sizes)
def test_zero_history_keeps_only_recurrent_continuation():
    torch.manual_seed(2)
    model = DeltaHybridV1().eval()
    runner = StatefulDeltaHybridV1(model, max_attention_history=0)
    x = torch.randint(0, 256, (2, 256))
    state, _ = run(runner, x)
    assert state.attention.hidden.shape[1] == 0
    assert state.attention.valid.shape[1] == 0
    assert len(state.delta_states) == 3


def test_unlimited_mode_still_grows_history():
    torch.manual_seed(3)
    model = DeltaHybridV1().eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, 256))
    state, sizes = run(runner, x)
    assert state.attention.hidden.shape[1] == 256
    assert sizes[-1] > sizes[0]
