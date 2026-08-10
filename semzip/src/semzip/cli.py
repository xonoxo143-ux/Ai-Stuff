from __future__ import annotations

import argparse
import json

from .codec import SemZipCodec, UnsupportedMeaningError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="semzip")
    sub = parser.add_subparsers(dest="command", required=True)

    encode = sub.add_parser("encode", help="encode English into a canonical graph")
    encode.add_argument("text")

    compare = sub.add_parser("compare", help="compare two inputs semantically")
    compare.add_argument("left")
    compare.add_argument("right")

    roundtrip = sub.add_parser("roundtrip", help="encode, regenerate, and re-encode")
    roundtrip.add_argument("text")
    return parser


def main() -> int:
    args = _parser().parse_args()
    codec = SemZipCodec()

    try:
        if args.command == "encode":
            graph = codec.encode(args.text)
            print(graph.canonical_json())
            print(f"hash={graph.semantic_hash()}")
            return 0

        if args.command == "compare":
            left = codec.encode(args.left)
            right = codec.encode(args.right)
            equivalent = codec.equivalent(left, right)
            print(json.dumps({
                "equivalent": equivalent,
                "left_hash": left.semantic_hash(),
                "right_hash": right.semantic_hash(),
            }, indent=2))
            return 0 if equivalent else 1

        if args.command == "roundtrip":
            first, regenerated, second = codec.roundtrip(args.text)
            print(f"generated={regenerated}")
            print(f"stable={first == second}")
            print(f"hash={first.semantic_hash()}")
            return 0 if first == second else 2
    except UnsupportedMeaningError as exc:
        print(json.dumps({
            "error": "unsupported_meaning",
            "message": str(exc),
        }, indent=2))
        return 3

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
