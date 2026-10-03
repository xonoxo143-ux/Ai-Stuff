import torch

from delta_hybrid.model_v1 import (
    CONTROL_PARAMETERS,
    DeltaHybridV1,
    parameter_count,
)


def test_parameter_budget_is_precommitted():
    model = DeltaHybridV1()
    fraction = abs(parameter_count(model) - CONTROL_PARAMETERS) / CONTROL_PARAMETERS
    assert fraction <= 0.02


def test_forward_shape_and_causality():
    torch.manual_seed(1)
    model = DeltaHybridV1().eval()
    x = torch.randint(0, 256, (2, 33))
    y = model(x)
    assert y.shape == (2, 33, 256)
    changed = x.clone()
    changed[:, 20:] = torch.randint(0, 256, (2, 13))
    y2 = model(changed)
    assert torch.allclose(y[:, :20], y2[:, :20], atol=1e-6, rtol=1e-6)
def test_reference_and_chunked_model_logits_match():
    torch.manual_seed(7)
    model = DeltaHybridV1().eval()
    x = torch.randint(0, 256, (2, 33))
    with torch.no_grad():
        chunked = model(x)
        model.set_execution("reference")
        reference = model(x)
    assert torch.allclose(
        chunked,
        reference,
        atol=1e-5,
        rtol=1e-5,
    )


def test_condition_zero_is_default():
    torch.manual_seed(2)
    model = DeltaHybridV1().eval()
    x = torch.randint(0, 256, (2, 17))
    zeros = torch.zeros(2, 16)
    assert torch.allclose(
        model(x),
        model(x, zeros),
        atol=0.0,
        rtol=0.0,
    )
