"""Chunk-parallel Gated-Delta forward path.

This is independent from the serial correctness oracle.  Inside each chunk it
uses the paper's WY/UT matrix form (batched matmuls + triangular solves);
recurrence remains only between chunks.
"""
import torch
import torch.nn.functional as F

from .delta_reference import DeltaState, scan, zero_state


def _safe_log_decay(decay):
    tiny = torch.finfo(decay.dtype).tiny
    return torch.log(decay.clamp_min(tiny))


def chunk_step_parallel(q, k, v, beta, decay, state=None):
    """Process one reset-free chunk with the WY/UT formulation."""
    batch, steps, d_key = q.shape
    d_value = v.shape[-1]
    if state is None:
        state = zero_state(
            batch, d_value, d_key, device=q.device, dtype=q.dtype
        )

    q = F.normalize(q, dim=-1)
    k = F.normalize(k, dim=-1)
    log_gamma = _safe_log_decay(decay).cumsum(dim=1)
    gamma = log_gamma.exp()

    gram = torch.matmul(k, k.transpose(-1, -2))
    eye = torch.eye(steps, device=q.device, dtype=q.dtype)
    eye = eye.expand(batch, steps, steps)
    beta_diag = torch.diag_embed(beta)

    # Ungated WY transform used for W.
    lower = torch.tril(beta.unsqueeze(-1) * gram, diagonal=-1)
    t_w = torch.linalg.solve_triangular(
        eye + lower, beta_diag, upper=False
    )
    w = torch.matmul(t_w, k)

    # Gated UT transform used for U_g.
    causal = torch.tril(
        torch.ones(steps, steps, device=q.device, dtype=q.dtype)
    )
    log_ratio = log_gamma.unsqueeze(-1) - log_gamma.unsqueeze(-2)
    gamma_ratio = log_ratio.exp() * causal
    gated_lower = torch.tril(
        beta.unsqueeze(-1) * gamma_ratio * gram, diagonal=-1
    )
    t_u = torch.linalg.solve_triangular(
        eye + gated_lower, beta_diag, upper=False
    )
    u_g = torch.matmul(t_u, v)

    left_w = gamma.unsqueeze(-1) * w
    left_q = gamma.unsqueeze(-1) * q
    right_k = (
        (log_gamma[:, -1:].unsqueeze(-1) - log_gamma.unsqueeze(-1)).exp()
        * k
    )

    state_t = state.memory.transpose(-1, -2)
    pseudo_values = u_g - torch.matmul(left_w, state_t)

    within = torch.matmul(q, k.transpose(-1, -2)) * gamma_ratio
    outputs = (
        torch.matmul(left_q, state_t)
        + torch.matmul(within, pseudo_values)
    )

    final_scale = log_gamma[:, -1].exp().view(batch, 1, 1)
    memory = (
        final_scale * state.memory
        + torch.matmul(pseudo_values.transpose(-1, -2), right_k)
    )
    return outputs, DeltaState(memory)
def chunk_parallel_scan(
    q, k, v, beta, decay, state=None, *, chunk_size=64, reset=None
):
    """Scan a sequence with parallel work inside each reset-free chunk.

    Reset-bearing chunks use the trusted serial oracle as a control-path
    fallback.  Ordinary training batches take only the parallel path.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")

    batch, steps, d_key = q.shape
    d_value = v.shape[-1]
    if state is None:
        state = zero_state(
            batch, d_value, d_key, device=q.device, dtype=q.dtype
        )

    outputs = []
    for start in range(0, steps, chunk_size):
        stop = min(steps, start + chunk_size)
        xs = (
            q[:, start:stop],
            k[:, start:stop],
            v[:, start:stop],
            beta[:, start:stop],
            decay[:, start:stop],
        )
        reset_chunk = None if reset is None else reset[:, start:stop]
        if reset_chunk is not None and bool(reset_chunk.any()):
            out, state = scan(
                *xs, state=state, reset=reset_chunk
            )
        else:
            out, state = chunk_step_parallel(*xs, state=state)
        outputs.append(out)

    if outputs:
        return torch.cat(outputs, dim=1), state
    empty = v.new_empty(batch, 0, d_value)
    return empty, state
