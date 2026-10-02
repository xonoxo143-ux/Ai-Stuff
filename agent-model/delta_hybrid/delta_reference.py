"""Readable Gated-Delta recurrence used as the V1 correctness oracle.

State orientation is [batch, value_dim, key_dim].  The update is the
ICLR-2025 Gated Delta rule, expanded as:

    S_t = alpha*S_{t-1}
          + beta*(v_t - alpha*S_{t-1}*k_t) outer k_t

with L2-normalized q/k.  This file intentionally favors clarity over speed.
"""
from dataclasses import dataclass

import torch
import torch.nn.functional as F


@dataclass
class DeltaState:
    memory: torch.Tensor


def zero_state(batch, d_value, d_key, *, device=None, dtype=None):
    return DeltaState(
        torch.zeros(batch, d_value, d_key, device=device, dtype=dtype)
    )
def step(q, k, v, beta, decay, state):
    """Consume one position and return its readout plus the updated state."""
    q = F.normalize(q, dim=-1)
    k = F.normalize(k, dim=-1)
    beta = beta.reshape(-1, 1)
    decay = decay.reshape(-1, 1, 1)

    prior = decay * state.memory
    predicted_value = torch.bmm(prior, k.unsqueeze(-1)).squeeze(-1)
    error = v - predicted_value
    memory = (
        prior
        + beta.unsqueeze(-1)
        * error.unsqueeze(-1)
        * k.unsqueeze(1)
    )
    output = torch.bmm(memory, q.unsqueeze(-1)).squeeze(-1)
    return output, DeltaState(memory)


def scan(q, k, v, beta, decay, state=None, reset=None):
    """Reference sequence scan.  The time loop is deliberate."""
    batch, steps, d_key = q.shape
    d_value = v.shape[-1]
    if state is None:
        state = zero_state(
            batch, d_value, d_key, device=q.device, dtype=q.dtype
        )

    outputs = []
    for t in range(steps):
        if reset is not None:
            keep = (~reset[:, t].bool()).to(q.dtype).view(batch, 1, 1)
            state = DeltaState(state.memory * keep)

        output, state = step(
            q[:, t],
            k[:, t],
            v[:, t],
            beta[:, t],
            decay[:, t],
            state,
        )
        outputs.append(output)

    return torch.stack(outputs, dim=1), state


def serialize_state(state):
    """Return an owned tensor snapshot suitable for checkpointing."""
    return state.memory.detach().clone()


def deserialize_state(tensor):
    """Restore a state without aliasing the serialized tensor."""
    return DeltaState(tensor.clone())
