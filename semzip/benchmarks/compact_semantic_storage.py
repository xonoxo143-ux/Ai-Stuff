from __future__ import annotations

import json
import random
import time
from pathlib import Path

from semzip.vm_binary import AtomTable, decode_patch_binary, encode_patch_binary
from semzip.vm_delta import RelationDelta
from semzip.vm_patch import SemanticPatch
from semzip.vm_relations import RelationRegistry


def main():
    count = 100_000
    object_count = 2_000
    person_count = 200
    rng = random.Random(404)
    registry = RelationRegistry(("owner", "possessor", "location"))
    atoms = AtomTable()

    payloads = []
    start = time.perf_counter()
    for index in range(count):
        subject = f"object#{index % object_count}"
        source_index = rng.randrange(person_count)
        destination_index = rng.randrange(person_count - 1)
        if destination_index >= source_index:
            destination_index += 1
        source = f"person#{source_index}"
        destination = f"person#{destination_index}"
        patch = SemanticPatch.build((
            RelationDelta.build(
                subject,
                source,
                destination,
                ("owner", "possessor"),
            ),
        ))
        payloads.append(encode_patch_binary(patch, atoms, registry))
    encode_seconds = time.perf_counter() - start

    payload_bytes = sum(len(value) for value in payloads)
    atom_utf8_bytes = sum(len(atom.encode("utf-8")) for atom in atoms.atoms)
    # A compact native table still needs offsets/lengths. Eight bytes per atom is a
    # deliberately conservative accounting allowance here, not a measured allocator.
    atom_index_allowance = len(atoms) * 8
    total_estimated = payload_bytes + atom_utf8_bytes + atom_index_allowance

    # Decode a deterministic sample to verify the shared-table corpus remains valid.
    start = time.perf_counter()
    checksum = 0
    for index in range(0, count, 97):
        patch = decode_patch_binary(payloads[index], atoms, registry)
        checksum += len(patch.deltas) + len(patch.deltas[0].relations)
    decode_seconds = time.perf_counter() - start

    report = {
        "patch_count": count,
        "object_count": object_count,
        "person_count": person_count,
        "atom_count": len(atoms),
        "payload_bytes": payload_bytes,
        "mean_payload_bytes_per_patch": payload_bytes / count,
        "atom_utf8_bytes": atom_utf8_bytes,
        "atom_index_allowance_bytes": atom_index_allowance,
        "estimated_total_bytes": total_estimated,
        "estimated_total_mb": total_estimated / (1024 * 1024),
        "estimated_bytes_per_patch_including_shared_atoms": total_estimated / count,
        "encode_seconds": encode_seconds,
        "encode_patches_per_second": count / encode_seconds,
        "sample_decode_seconds": decode_seconds,
        "sample_decode_count": len(range(0, count, 97)),
        "sample_checksum": checksum,
        "caveat": (
            "Compact-format prototype estimate, not process RSS. It counts binary patch "
            "payloads, UTF-8 atom bytes, and an 8-byte-per-atom index allowance; container, "
            "database-page, transaction, and native-runtime overhead are not included."
        ),
    }
    Path("compact-semantic-storage.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
