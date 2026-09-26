from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from .lifetime_world import LifetimeWorldConfig


def world_fingerprint(config: LifetimeWorldConfig) -> str:
    payload = json.dumps(
        asdict(config),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class V1Checkpoint:
    next_experience: int
    world_seed: int
    world_fingerprint: str

    @classmethod
    def for_world(
        cls,
        config: LifetimeWorldConfig,
        *,
        next_experience: int,
    ) -> "V1Checkpoint":
        if not 0 <= next_experience <= config.total_experiences:
            raise ValueError("next_experience outside configured lifetime")
        return cls(
            next_experience=next_experience,
            world_seed=config.seed,
            world_fingerprint=world_fingerprint(config),
        )

    def validate_world(self, config: LifetimeWorldConfig) -> None:
        if self.world_seed != config.seed:
            raise ValueError("checkpoint world seed does not match")
        if self.world_fingerprint != world_fingerprint(config):
            raise ValueError("checkpoint world configuration does not match")


def save_checkpoint(path: str | Path, checkpoint: V1Checkpoint) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(asdict(checkpoint), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_checkpoint(path: str | Path) -> V1Checkpoint:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return V1Checkpoint(
        next_experience=int(payload["next_experience"]),
        world_seed=int(payload["world_seed"]),
        world_fingerprint=str(payload["world_fingerprint"]),
    )
