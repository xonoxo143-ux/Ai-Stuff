from __future__ import annotations

from dataclasses import dataclass, field

from .vm_delta import RelationDelta
from .vm_patch import ReturnObligation, SemanticPatch, StateAssignment, StateClear
from .vm_relations import RelationRegistry


_TAG_TRANSITION = 0
_TAG_ASSIGNMENT = 1
_TAG_CLEAR = 2
_TAG_RETURN = 3
_FORMAT_VERSION = 1


def encode_varint(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("varint requires a non-negative integer")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    shift = 0
    position = offset
    while position < len(data):
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
        if shift > 63:
            raise ValueError("varint is too large")
    raise ValueError("truncated varint")


@dataclass(slots=True)
class AtomTable:
    """Shared string interning table for compact semantic storage."""

    atoms: list[str] = field(default_factory=list)
    _ids: dict[str, int] = field(default_factory=dict)

    def intern(self, value: str) -> int:
        text = str(value)
        found = self._ids.get(text)
        if found is not None:
            return found
        atom_id = len(self.atoms)
        self.atoms.append(text)
        self._ids[text] = atom_id
        return atom_id

    def resolve(self, atom_id: int) -> str:
        if not 0 <= atom_id < len(self.atoms):
            raise KeyError(f"unknown atom id {atom_id}")
        return self.atoms[atom_id]

    def __len__(self) -> int:
        return len(self.atoms)


def _dimension_id(name: str, registry: RelationRegistry) -> int:
    try:
        return registry.resolve_name(name).relation_id
    except KeyError as exc:
        raise ValueError(
            f"dimension {name!r} is not registered for binary semantic encoding"
        ) from exc


def encode_patch_binary(
    patch: SemanticPatch,
    atoms: AtomTable,
    registry: RelationRegistry,
) -> bytes:
    """Encode one patch; atom table and relation registry are shared externally."""

    records: list[tuple] = []
    for delta in patch.deltas:
        for dimension in delta.relations:
            records.append(
                (
                    _TAG_TRANSITION,
                    _dimension_id(dimension, registry),
                    atoms.intern(delta.subject),
                    atoms.intern(delta.source),
                    atoms.intern(delta.destination),
                )
            )
    for item in patch.assignments:
        records.append(
            (
                _TAG_ASSIGNMENT,
                _dimension_id(item.dimension, registry),
                atoms.intern(item.subject),
                atoms.intern(item.value),
            )
        )
    for item in patch.clears:
        records.append(
            (
                _TAG_CLEAR,
                _dimension_id(item.dimension, registry),
                atoms.intern(item.subject),
            )
        )
    for item in patch.return_obligations:
        records.append(
            (
                _TAG_RETURN,
                atoms.intern(item.subject),
                atoms.intern(item.holder),
                atoms.intern(item.return_to),
            )
        )

    output = bytearray()
    output.extend(encode_varint(_FORMAT_VERSION))
    output.extend(encode_varint(len(records)))
    for record in records:
        for value in record:
            output.extend(encode_varint(value))
    return bytes(output)


def decode_patch_binary(
    data: bytes,
    atoms: AtomTable,
    registry: RelationRegistry,
) -> SemanticPatch:
    version, offset = decode_varint(data, 0)
    if version != _FORMAT_VERSION:
        raise ValueError(f"unsupported semantic binary format version {version}")
    record_count, offset = decode_varint(data, offset)

    transitions: list[RelationDelta] = []
    assignments: list[StateAssignment] = []
    clears: list[StateClear] = []
    returns: list[ReturnObligation] = []

    for _ in range(record_count):
        tag, offset = decode_varint(data, offset)
        if tag == _TAG_TRANSITION:
            dimension_id, offset = decode_varint(data, offset)
            subject_id, offset = decode_varint(data, offset)
            source_id, offset = decode_varint(data, offset)
            destination_id, offset = decode_varint(data, offset)
            dimension = registry.resolve_id(dimension_id).name
            transitions.append(
                RelationDelta.build(
                    atoms.resolve(subject_id),
                    atoms.resolve(source_id),
                    atoms.resolve(destination_id),
                    (dimension,),
                    registry=registry,
                )
            )
        elif tag == _TAG_ASSIGNMENT:
            dimension_id, offset = decode_varint(data, offset)
            subject_id, offset = decode_varint(data, offset)
            value_id, offset = decode_varint(data, offset)
            dimension = registry.resolve_id(dimension_id).name
            assignments.append(
                StateAssignment.build(
                    atoms.resolve(subject_id), dimension, atoms.resolve(value_id)
                )
            )
        elif tag == _TAG_CLEAR:
            dimension_id, offset = decode_varint(data, offset)
            subject_id, offset = decode_varint(data, offset)
            dimension = registry.resolve_id(dimension_id).name
            clears.append(StateClear.build(atoms.resolve(subject_id), dimension))
        elif tag == _TAG_RETURN:
            subject_id, offset = decode_varint(data, offset)
            holder_id, offset = decode_varint(data, offset)
            return_to_id, offset = decode_varint(data, offset)
            returns.append(
                ReturnObligation.build(
                    atoms.resolve(subject_id),
                    atoms.resolve(holder_id),
                    atoms.resolve(return_to_id),
                )
            )
        else:
            raise ValueError(f"unknown semantic binary record tag {tag}")

    if offset != len(data):
        raise ValueError("trailing bytes after semantic patch")
    if not transitions and not assignments and not clears and not returns:
        raise ValueError("decoded semantic patch is empty")
    return SemanticPatch.build(
        tuple(transitions),
        assignments=tuple(assignments),
        clears=tuple(clears),
        return_obligations=tuple(returns),
    )
