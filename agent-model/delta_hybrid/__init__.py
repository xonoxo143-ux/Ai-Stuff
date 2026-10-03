"""DeltaHybrid V1 reference and experimental components."""

from .delta_chunk import chunk_parallel_scan, chunk_step_parallel
from .delta_reference import (
    DeltaState,
    deserialize_state,
    scan,
    serialize_state,
    step,
    zero_state,
)
from .model_v1 import DeltaHybridV1
from .persistent_state import (
    AttentionHistory,
    DeltaHybridState,
    StatefulDeltaHybridV1,
    state_from_payload,
    state_size_bytes,
    state_to_payload,
)

__all__ = [
    "AttentionHistory",
    "DeltaHybridState",
    "DeltaHybridV1",
    "StatefulDeltaHybridV1",
    "DeltaState",
    "chunk_parallel_scan",
    "chunk_step_parallel",
    "deserialize_state",
    "scan",
    "serialize_state",
    "state_from_payload",
    "state_size_bytes",
    "state_to_payload",
    "step",
    "zero_state",
]
