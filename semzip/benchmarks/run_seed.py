from __future__ import annotations

import json
from pathlib import Path

from semzip import SemZipCodec


def main() -> None:
    codec = SemZipCodec()
    rows = [
        json.loads(line)
        for line in Path(__file__).with_name("seed.jsonl").read_text().splitlines()
        if line.strip()
    ]

    baseline = codec.encode(rows[0]["text"])
    print(f"baseline_hash={baseline.semantic_hash()}")
    failures = 0

    for row in rows:
        graph = codec.encode(row["text"])
        same = graph == baseline
        expected = bool(row["equivalent"])
        ok = same == expected
        failures += int(not ok)
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{row['group']}: equivalent={same} hash={graph.semantic_hash()[:12]}"
        )

    if failures:
        raise SystemExit(f"{failures} benchmark case(s) failed")


if __name__ == "__main__":
    main()
