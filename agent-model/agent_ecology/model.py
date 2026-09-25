from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
from torch import Tensor, nn
import torch.nn.functional as F


@dataclass(frozen=True)
class EcologyConfig:
    event_dim: int = 12
    output_dim: int = 1
    num_cells: int = 32
    active_cells: int = 4
    state_dim: int = 192
    workspace_slots: int = 6
    signature_dim: int = 64
    message_dim: int = 64
    max_thought_steps: int = 8
    min_thought_steps: int = 2
    halt_threshold: float = 0.90
    router_temperature: float = 1.0
    routing_noise_std: float = 0.10
    dense_training_compute: bool = True

    def validate(self) -> None:
        if self.event_dim <= 0 or self.output_dim <= 0:
            raise ValueError("event_dim and output_dim must be positive")
        if self.num_cells <= 0:
            raise ValueError("num_cells must be positive")
        if not 1 <= self.active_cells <= self.num_cells:
            raise ValueError("active_cells must be in [1, num_cells]")
        if self.state_dim <= 0 or self.workspace_slots <= 0:
            raise ValueError("state_dim and workspace_slots must be positive")
        if self.signature_dim <= 0 or self.message_dim <= 0:
            raise ValueError("signature_dim and message_dim must be positive")
        if self.max_thought_steps <= 0:
            raise ValueError("max_thought_steps must be positive")
        if not 1 <= self.min_thought_steps <= self.max_thought_steps:
            raise ValueError("min_thought_steps must be in [1, max_thought_steps]")


@dataclass
class EcologyState:
    workspace: Tensor
    cell_states: Tensor

    def detach(self) -> "EcologyState":
        return EcologyState(
            workspace=self.workspace.detach(),
            cell_states=self.cell_states.detach(),
        )


class SparseRecurrentEcology(nn.Module):
    """
    A sparse recurrent ecology.

    The model keeps N private recurrent cell states but only executes top-k cells
    during each internal thought step. Cells are selected by a cheap learned
    signature match against the current need vector. Selected cells read from a
    bounded workspace, update only their own private state, and emit bounded
    messages back to the workspace.

    No cell is privileged as a central semantic controller.
    """

    def __init__(self, config: EcologyConfig):
        super().__init__()
        config.validate()
        self.config = config

        c = config
        h = c.state_dim
        cell_input_dim = h * 2

        self.event_encoder = nn.Sequential(
            nn.Linear(c.event_dim, h),
            nn.Tanh(),
        )

        self.initial_workspace = nn.Parameter(
            torch.zeros(c.workspace_slots, h)
        )
        nn.init.normal_(self.initial_workspace, mean=0.0, std=0.02)

        # Cheap routing path.
        self.need_projection = nn.Linear(h * 2, c.signature_dim)
        self.cell_signatures = nn.Parameter(
            torch.randn(c.num_cells, c.signature_dim) * 0.02
        )

        # Cell-specific private recurrent parameters, stacked so only selected
        # weights need to participate in the sparse update.
        self.w_ih = nn.Parameter(
            torch.empty(c.num_cells, 3 * h, cell_input_dim)
        )
        self.w_hh = nn.Parameter(
            torch.empty(c.num_cells, 3 * h, h)
        )
        self.b_ih = nn.Parameter(torch.zeros(c.num_cells, 3 * h))
        self.b_hh = nn.Parameter(torch.zeros(c.num_cells, 3 * h))

        # Cell-specific public message emitters.
        self.w_msg = nn.Parameter(
            torch.empty(c.num_cells, c.message_dim, h)
        )
        self.b_msg = nn.Parameter(torch.zeros(c.num_cells, c.message_dim))

        # Shared interface projections. These are transport/interface mechanics,
        # not a domain-smart controller.
        self.signature_read_query = nn.Linear(c.signature_dim, h, bias=False)
        self.message_key = nn.Linear(c.message_dim, h, bias=False)
        self.message_value = nn.Linear(c.message_dim, h, bias=False)
        self.workspace_norm = nn.LayerNorm(h)

        self.output_head = nn.Linear(h, c.output_dim)
        self.halt_head = nn.Linear(h, 1)

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        h = self.config.state_dim
        for index in range(self.config.num_cells):
            nn.init.xavier_uniform_(self.w_ih[index])
            nn.init.orthogonal_(self.w_hh[index])
            nn.init.xavier_uniform_(self.w_msg[index])
        # Bias update gate slightly toward retaining state at initialization.
        with torch.no_grad():
            self.b_ih[:, h : 2 * h].fill_(1.0)

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def initial_state(
        self,
        batch_size: int,
        *,
        device: Optional[torch.device] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> EcologyState:
        if device is None:
            device = self.initial_workspace.device
        if dtype is None:
            dtype = self.initial_workspace.dtype

        workspace = self.initial_workspace.to(device=device, dtype=dtype)
        workspace = workspace.unsqueeze(0).expand(batch_size, -1, -1).clone()
        cell_states = torch.zeros(
            batch_size,
            self.config.num_cells,
            self.config.state_dim,
            device=device,
            dtype=dtype,
        )
        return EcologyState(workspace=workspace, cell_states=cell_states)

    def _route(
        self,
        event_embedding: Tensor,
        workspace: Tensor,
        *,
        add_training_noise: bool,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor]:
        c = self.config
        pooled = workspace.mean(dim=1)
        need = self.need_projection(torch.cat([event_embedding, pooled], dim=-1))
        need = F.normalize(need, dim=-1)
        signatures = F.normalize(self.cell_signatures, dim=-1)

        scores = torch.matmul(need, signatures.transpose(0, 1))
        scores = scores / max(c.router_temperature, 1e-6)

        if add_training_noise and self.training and c.routing_noise_std > 0.0:
            scores = scores + torch.randn_like(scores) * c.routing_noise_std

        top_scores, top_indices = torch.topk(
            scores,
            k=c.active_cells,
            dim=-1,
            largest=True,
            sorted=True,
        )
        route_weights = torch.softmax(top_scores, dim=-1)
        router_probs = torch.softmax(scores, dim=-1)
        return top_indices, route_weights, scores, router_probs

    @staticmethod
    def _gather_cell_tensor(parameter: Tensor, indices: Tensor) -> Tensor:
        # parameter: [N, ...], indices: [B, K] -> [B, K, ...]
        flat = indices.reshape(-1)
        gathered = parameter.index_select(0, flat)
        return gathered.reshape(*indices.shape, *parameter.shape[1:])

    def _selected_cell_update(
        self,
        event_embedding: Tensor,
        workspace: Tensor,
        cell_states: Tensor,
        selected: Tensor,
        route_weights: Tensor,
    ) -> Tuple[Tensor, Tensor]:
        c = self.config
        b, k = selected.shape
        h = c.state_dim

        selected_signatures = self._gather_cell_tensor(
            self.cell_signatures, selected
        )
        read_queries = self.signature_read_query(selected_signatures)

        read_logits = torch.einsum(
            "bkh,bsh->bks", read_queries, workspace
        ) / (h ** 0.5)
        read_weights = torch.softmax(read_logits, dim=-1)
        workspace_reads = torch.einsum(
            "bks,bsh->bkh", read_weights, workspace
        )

        selected_states = torch.gather(
            cell_states,
            dim=1,
            index=selected.unsqueeze(-1).expand(-1, -1, h),
        )

        event_repeated = event_embedding.unsqueeze(1).expand(-1, k, -1)
        cell_input = torch.cat([workspace_reads, event_repeated], dim=-1)

        w_ih = self._gather_cell_tensor(self.w_ih, selected)
        w_hh = self._gather_cell_tensor(self.w_hh, selected)
        b_ih = self._gather_cell_tensor(self.b_ih, selected)
        b_hh = self._gather_cell_tensor(self.b_hh, selected)

        input_gates = torch.einsum(
            "bkoi,bki->bko", w_ih, cell_input
        ) + b_ih
        hidden_gates = torch.einsum(
            "bkoh,bkh->bko", w_hh, selected_states
        ) + b_hh

        i_r, i_z, i_n = input_gates.chunk(3, dim=-1)
        h_r, h_z, h_n = hidden_gates.chunk(3, dim=-1)

        reset = torch.sigmoid(i_r + h_r)
        update = torch.sigmoid(i_z + h_z)
        candidate = torch.tanh(i_n + reset * h_n)
        new_selected_states = (1.0 - update) * candidate + update * selected_states

        # Sparse state mutation: only selected cell slots are overwritten.
        new_cell_states = cell_states.scatter(
            dim=1,
            index=selected.unsqueeze(-1).expand(-1, -1, h),
            src=new_selected_states,
        )

        w_msg = self._gather_cell_tensor(self.w_msg, selected)
        b_msg = self._gather_cell_tensor(self.b_msg, selected)
        messages = torch.einsum(
            "bkmh,bkh->bkm", w_msg, new_selected_states
        ) + b_msg
        messages = torch.tanh(messages)
        messages = messages * route_weights.unsqueeze(-1)

        return new_cell_states, messages

    def _dense_training_cell_update(
        self,
        event_embedding: Tensor,
        workspace: Tensor,
        cell_states: Tensor,
        selected: Tensor,
        route_weights: Tensor,
    ) -> Tuple[Tensor, Tensor]:
        """
        Expensive training path.

        It evaluates every private cell candidate so training can gather useful
        gradients without materializing a separate copy of selected weights for
        every batch item. Only top-k cells are committed to private state and
        only their public messages are exposed.

        This intentionally spends more compute during learning than deployment.
        Runtime/eval remains genuinely sparse.
        """
        c = self.config
        b = event_embedding.shape[0]
        n = c.num_cells
        h = c.state_dim
        k = c.active_cells

        signatures = self.cell_signatures
        read_queries = self.signature_read_query(signatures)
        read_logits = torch.einsum(
            "nh,bsh->bns", read_queries, workspace
        ) / (h ** 0.5)
        read_weights = torch.softmax(read_logits, dim=-1)
        workspace_reads = torch.einsum(
            "bns,bsh->bnh", read_weights, workspace
        )

        event_repeated = event_embedding.unsqueeze(1).expand(-1, n, -1)
        cell_input = torch.cat([workspace_reads, event_repeated], dim=-1)

        input_gates = torch.einsum(
            "noi,bni->bno", self.w_ih, cell_input
        ) + self.b_ih.unsqueeze(0)
        hidden_gates = torch.einsum(
            "noh,bnh->bno", self.w_hh, cell_states
        ) + self.b_hh.unsqueeze(0)

        i_r, i_z, i_n = input_gates.chunk(3, dim=-1)
        h_r, h_z, h_n = hidden_gates.chunk(3, dim=-1)

        reset = torch.sigmoid(i_r + h_r)
        update = torch.sigmoid(i_z + h_z)
        candidate = torch.tanh(i_n + reset * h_n)
        candidate_states = (
            (1.0 - update) * candidate + update * cell_states
        )

        selected_states = torch.gather(
            candidate_states,
            dim=1,
            index=selected.unsqueeze(-1).expand(-1, -1, h),
        )
        new_cell_states = cell_states.scatter(
            dim=1,
            index=selected.unsqueeze(-1).expand(-1, -1, h),
            src=selected_states,
        )

        all_messages = torch.einsum(
            "nmh,bnh->bnm", self.w_msg, candidate_states
        ) + self.b_msg.unsqueeze(0)
        all_messages = torch.tanh(all_messages)
        selected_messages = torch.gather(
            all_messages,
            dim=1,
            index=selected.unsqueeze(-1).expand(
                b, k, c.message_dim
            ),
        )
        selected_messages = (
            selected_messages * route_weights.unsqueeze(-1)
        )

        return new_cell_states, selected_messages

    def _workspace_write(
        self,
        workspace: Tensor,
        messages: Tensor,
    ) -> Tensor:
        h = self.config.state_dim

        keys = self.message_key(messages)
        values = self.message_value(messages)

        write_logits = torch.einsum(
            "bsh,bkh->bsk", workspace, keys
        ) / (h ** 0.5)
        write_weights = torch.softmax(write_logits, dim=-1)
        aggregate = torch.einsum(
            "bsk,bkh->bsh", write_weights, values
        )

        # A deliberately small mechanical communication update. The nonlinear
        # private computation lives in capability cells.
        return self.workspace_norm(workspace + aggregate)

    def thought_step(
        self,
        event: Tensor,
        workspace: Tensor,
        cell_states: Tensor,
        *,
        add_training_noise: bool = True,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        """
        Execute exactly one internal sparse thought step.

        Returns:
          output,
          new_workspace,
          new_cell_states,
          selected_cell_ids,
          route_weights,
          all_router_scores,
          halt_probability
        """
        event_embedding = self.event_encoder(event)

        selected, route_weights, scores, _router_probs = self._route(
            event_embedding,
            workspace,
            add_training_noise=add_training_noise,
        )

        if self.training and self.config.dense_training_compute:
            new_cell_states, messages = self._dense_training_cell_update(
                event_embedding,
                workspace,
                cell_states,
                selected,
                route_weights,
            )
        else:
            new_cell_states, messages = self._selected_cell_update(
                event_embedding,
                workspace,
                cell_states,
                selected,
                route_weights,
            )
        new_workspace = self._workspace_write(workspace, messages)

        pooled = new_workspace.mean(dim=1)
        output = self.output_head(pooled)
        halt_probability = torch.sigmoid(self.halt_head(pooled)).squeeze(-1)

        return (
            output,
            new_workspace,
            new_cell_states,
            selected,
            route_weights,
            scores,
            halt_probability,
        )

    def forward_event(
        self,
        event: Tensor,
        state: Optional[EcologyState] = None,
        *,
        force_steps: Optional[int] = None,
        add_training_noise: bool = True,
        return_trace: bool = False,
    ) -> Tuple[Tensor, EcologyState, Optional[Dict[str, Tensor]]]:
        if event.ndim != 2 or event.shape[-1] != self.config.event_dim:
            raise ValueError(
                f"event must have shape [batch, {self.config.event_dim}]"
            )

        batch = event.shape[0]
        if state is None:
            state = self.initial_state(
                batch,
                device=event.device,
                dtype=event.dtype,
            )

        workspace = state.workspace
        cell_states = state.cell_states

        max_steps = force_steps or self.config.max_thought_steps
        outputs: List[Tensor] = []
        selected_history: List[Tensor] = []
        route_history: List[Tensor] = []
        score_history: List[Tensor] = []
        halt_history: List[Tensor] = []

        output = self.output_head(workspace.mean(dim=1))

        for thought_index in range(max_steps):
            (
                output,
                workspace,
                cell_states,
                selected,
                route_weights,
                scores,
                halt_probability,
            ) = self.thought_step(
                event,
                workspace,
                cell_states,
                add_training_noise=add_training_noise,
            )

            outputs.append(output)
            selected_history.append(selected)
            route_history.append(route_weights)
            score_history.append(scores)
            halt_history.append(halt_probability)

            if (
                not self.training
                and force_steps is None
                and thought_index + 1 >= self.config.min_thought_steps
                and bool(torch.all(halt_probability >= self.config.halt_threshold))
            ):
                break

        new_state = EcologyState(
            workspace=workspace,
            cell_states=cell_states,
        )

        trace = None
        if return_trace:
            trace = {
                "outputs": torch.stack(outputs, dim=1),
                "selected_cells": torch.stack(selected_history, dim=1),
                "route_weights": torch.stack(route_history, dim=1),
                "router_scores": torch.stack(score_history, dim=1),
                "halt_probabilities": torch.stack(halt_history, dim=1),
            }

        return output, new_state, trace

    def forward(
        self,
        events: Tensor,
        state: Optional[EcologyState] = None,
        *,
        force_steps: Optional[int] = None,
        add_training_noise: bool = True,
        return_trace: bool = False,
    ) -> Tuple[Tensor, EcologyState, Optional[List[Dict[str, Tensor]]]]:
        """
        Process a sequence of external events while preserving private cell state.

        events: [batch, time, event_dim]
        outputs: [batch, time, output_dim]
        """
        if events.ndim != 3 or events.shape[-1] != self.config.event_dim:
            raise ValueError(
                f"events must have shape [batch, time, {self.config.event_dim}]"
            )

        if state is None:
            state = self.initial_state(
                events.shape[0],
                device=events.device,
                dtype=events.dtype,
            )

        outputs: List[Tensor] = []
        traces: List[Dict[str, Tensor]] = []

        for time_index in range(events.shape[1]):
            output, state, trace = self.forward_event(
                events[:, time_index],
                state,
                force_steps=force_steps,
                add_training_noise=add_training_noise,
                return_trace=return_trace,
            )
            outputs.append(output)
            if trace is not None:
                traces.append(trace)

        return (
            torch.stack(outputs, dim=1),
            state,
            traces if return_trace else None,
        )

    def router_balance_loss(self, router_scores: Tensor) -> Tensor:
        """
        Penalize collapse onto a few cells using the cheap all-cell router scores.

        router_scores may be [B, N] or [..., N].
        """
        probs = torch.softmax(router_scores, dim=-1)
        mean_usage = probs.reshape(-1, probs.shape[-1]).mean(dim=0)
        # Zero at perfectly uniform usage; approaches N-1 as routing collapses
        # onto one cell. This has a useful scale even for moderately large N.
        return (
            self.config.num_cells * torch.sum(mean_usage.square()) - 1.0
        )

    def communication_cost(self, route_weights: Tensor) -> Tensor:
        """
        Differentiable proxy for public communication pressure.

        This is intentionally simple in v0. Real byte/time cost is measured by
        the Agent Kernel on-device.
        """
        return route_weights.abs().sum(dim=-1).mean()
