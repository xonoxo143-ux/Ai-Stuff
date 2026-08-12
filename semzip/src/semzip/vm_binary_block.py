from __future__ import annotations

from dataclasses import dataclass

from .vm_binary import AtomTable, decode_patch_binary, decode_varint, encode_patch_binary, encode_varint
from .vm_patch import SemanticPatch
from .vm_relations import RelationRegistry


_MAGIC = b"SVM1"
_SIGNATURE_BYTES = 32


@dataclass(frozen=True, slots=True)
class DecodedSemanticBlock:
    patches: tuple[SemanticPatch, ...]
    atom_count: int
    registry_signature: str


def encode_semantic_block(
    patches,
    registry: RelationRegistry,
) -> bytes:
    """Encode many patches with one shared atom table + semantic vocabulary signature."""

    values = tuple(patches)
    if not values:
        raise ValueError("semantic block cannot be empty")
    if any(not isinstance(patch, SemanticPatch) for patch in values):
        raise TypeError("all block values must be SemanticPatch")

    atoms = AtomTable()
    payloads = tuple(encode_patch_binary(patch, atoms, registry) for patch in values)
    signature = bytes.fromhex(registry.signature())
    if len(signature) != _SIGNATURE_BYTES:
        raise ValueError("registry signature is not SHA-256 sized")

    output = bytearray(_MAGIC)
    output.extend(signature)
    output.extend(encode_varint(len(atoms)))
    for atom in atoms.atoms:
        raw = atom.encode("utf-8")
        output.extend(encode_varint(len(raw)))
        output.extend(raw)
    output.extend(encode_varint(len(payloads)))
    for payload in payloads:
        output.extend(encode_varint(len(payload)))
        output.extend(payload)
    return bytes(output)


def decode_semantic_block(
    data: bytes,
    registry: RelationRegistry,
) -> DecodedSemanticBlock:
    if not data.startswith(_MAGIC):
        raise ValueError("not a SemVM semantic memory block")
    offset = len(_MAGIC)
    if len(data) < offset + _SIGNATURE_BYTES:
        raise ValueError("truncated semantic memory block signature")
    stored_signature = data[offset : offset + _SIGNATURE_BYTES].hex()
    offset += _SIGNATURE_BYTES
    expected = registry.signature()
    if stored_signature != expected:
        raise ValueError(
            "semantic memory registry signature mismatch; refusing to reinterpret relation IDs"
        )

    atom_count, offset = decode_varint(data, offset)
    atoms = AtomTable()
    for _ in range(atom_count):
        length, offset = decode_varint(data, offset)
        end = offset + length
        if end > len(data):
            raise ValueError("truncated atom table entry")
        try:
            text = data[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid UTF-8 atom in semantic memory block") from exc
        atoms.intern(text)
        offset = end

    patch_count, offset = decode_varint(data, offset)
    patches = []
    for _ in range(patch_count):
        length, offset = decode_varint(data, offset)
        end = offset + length
        if end > len(data):
            raise ValueError("truncated patch payload")
        patches.append(decode_patch_binary(data[offset:end], atoms, registry))
        offset = end

    if offset != len(data):
        raise ValueError("trailing bytes after semantic memory block")
    return DecodedSemanticBlock(tuple(patches), len(atoms), stored_signature)
