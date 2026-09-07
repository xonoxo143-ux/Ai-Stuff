from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn
import torch.nn.functional as F


@dataclass
class FluidConfig:
    vocab_size: int
    grid_size: int = 6
    dt: float = 0.04
    diffusion: float = 0.08
    viscosity: float = 0.08
    pressure: float = 0.60
    source_scale: float = 0.08
    force_scale: float = 0.06
    drag: float = 0.20
    velocity_clip: float = 2.0


class FluidLM(nn.Module):
    """Character LM whose recurrent state is a small 2D semantic fluid.

    The state is a normalized density field plus a 2D velocity field on a
    periodic grid. Each token provides a learned density redistribution and
    force field. The state then advances by a deliberately simple discretized
    advection/diffusion/pressure update before being decoded to next-token
    logits.
    """

    def __init__(self, config: FluidConfig):
        super().__init__()
        self.config = config
        n = config.grid_size * config.grid_size

        # Per-token fields: density source, x-force, y-force.
        self.token_drive = nn.Embedding(config.vocab_size, 3 * n)
        nn.init.normal_(self.token_drive.weight, mean=0.0, std=0.02)

        self.readout = nn.Sequential(
            nn.LayerNorm(3 * n),
            nn.Linear(3 * n, 2 * n),
            nn.GELU(),
            nn.Linear(2 * n, config.vocab_size),
        )

    @property
    def grid_size(self) -> int:
        return self.config.grid_size

    def init_state(
        self,
        batch_size: int,
        device: torch.device | str | None = None,
    ) -> tuple[Tensor, Tensor]:
        h = self.grid_size
        device = device or self.token_drive.weight.device
        rho = torch.full((batch_size, h, h), 1.0 / (h * h), device=device)
        velocity = torch.zeros((batch_size, 2, h, h), device=device)
        return rho, velocity

    @staticmethod
    def _grad_x(field: Tensor) -> Tensor:
        return 0.5 * (
            torch.roll(field, shifts=-1, dims=-1)
            - torch.roll(field, shifts=1, dims=-1)
        )

    @staticmethod
    def _grad_y(field: Tensor) -> Tensor:
        return 0.5 * (
            torch.roll(field, shifts=-1, dims=-2)
            - torch.roll(field, shifts=1, dims=-2)
        )

    @staticmethod
    def _laplacian(field: Tensor) -> Tensor:
        return (
            torch.roll(field, shifts=1, dims=-1)
            + torch.roll(field, shifts=-1, dims=-1)
            + torch.roll(field, shifts=1, dims=-2)
            + torch.roll(field, shifts=-1, dims=-2)
            - 4.0 * field
        )

    def step(
        self,
        token: Tensor,
        state: tuple[Tensor, Tensor],
    ) -> tuple[Tensor, tuple[Tensor, Tensor]]:
        cfg = self.config
        rho, velocity = state
        batch = token.shape[0]
        h = self.grid_size

        drive = self.token_drive(token).view(batch, 3, h, h)
        source, force_x, force_y = drive[:, 0], drive[:, 1], drive[:, 2]

        # A token redistributes density rather than creating unlimited mass.
        source = source - source.mean(dim=(-2, -1), keepdim=True)

        # Keep token forcing momentum-neutral on the closed periodic grid.
        # Without this, repeated token forcing can accelerate the entire fluid
        # forever because viscosity only damps velocity gradients, not the
        # spatially uniform velocity mode.
        force_x = force_x - force_x.mean(dim=(-2, -1), keepdim=True)
        force_y = force_y - force_y.mean(dim=(-2, -1), keepdim=True)

        ux, uy = velocity[:, 0], velocity[:, 1]

        flux_x = rho * ux
        flux_y = rho * uy
        divergence = self._grad_x(flux_x) + self._grad_y(flux_y)

        rho_raw = rho + cfg.dt * (
            -divergence
            + cfg.diffusion * self._laplacian(rho)
            + cfg.source_scale * source
        )
        rho_next = F.softplus(rho_raw)
        rho_next = rho_next / rho_next.sum(dim=(-2, -1), keepdim=True).clamp_min(1e-8)

        grad_rho_x = self._grad_x(rho_next)
        grad_rho_y = self._grad_y(rho_next)

        advect_x = ux * self._grad_x(ux) + uy * self._grad_y(ux)
        advect_y = ux * self._grad_x(uy) + uy * self._grad_y(uy)

        ux_next = ux + cfg.dt * (
            -advect_x
            - cfg.pressure * grad_rho_x
            + cfg.viscosity * self._laplacian(ux)
            - cfg.drag * ux
            + cfg.force_scale * force_x
        )
        uy_next = uy + cfg.dt * (
            -advect_y
            - cfg.pressure * grad_rho_y
            + cfg.viscosity * self._laplacian(uy)
            - cfg.drag * uy
            + cfg.force_scale * force_y
        )

        ux_next = ux_next.clamp(-cfg.velocity_clip, cfg.velocity_clip)
        uy_next = uy_next.clamp(-cfg.velocity_clip, cfg.velocity_clip)
        velocity_next = torch.stack((ux_next, uy_next), dim=1)

        features = torch.cat(
            (
                rho_next.flatten(1),
                ux_next.flatten(1),
                uy_next.flatten(1),
            ),
            dim=1,
        )
        logits = self.readout(features)
        return logits, (rho_next, velocity_next)

    def forward(
        self,
        tokens: Tensor,
        state: tuple[Tensor, Tensor] | None = None,
    ) -> tuple[Tensor, tuple[Tensor, Tensor]]:
        if tokens.ndim != 2:
            raise ValueError("tokens must have shape [batch, sequence]")

        batch, sequence = tokens.shape
        if state is None:
            state = self.init_state(batch, tokens.device)

        outputs: list[Tensor] = []
        for index in range(sequence):
            logits, state = self.step(tokens[:, index], state)
            outputs.append(logits)

        return torch.stack(outputs, dim=1), state

    @classmethod
    def vorticity(cls, velocity: Tensor) -> Tensor:
        """Return scalar 2D curl: d(v_y)/dx - d(v_x)/dy."""
        ux, uy = velocity[:, 0], velocity[:, 1]
        return cls._grad_x(uy) - cls._grad_y(ux)
