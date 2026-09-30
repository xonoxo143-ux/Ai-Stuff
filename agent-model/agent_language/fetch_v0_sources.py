from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

SOURCES = {
    "wikitext": {
        "url": "https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip",
        "filename": "wikitext-2-raw-v1.zip",
        "sha256": "ef7edb566e3e2b2d31b29c1fdb0c89a4cc683597484c3dc2517919c615435a11",
    },
    "oasst1": {
        "url": "https://huggingface.co/datasets/OpenAssistant/oasst1/resolve/main/2023-04-12_oasst_ready.messages.jsonl.gz",
        "filename": "oasst1-ready.jsonl.gz",
        "sha256": "286a6e9a5a413b3272ae9c0b5a20d327983dea1c24342ae28cb244a6da65185c",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, path: Path, expected: str) -> None:
    if path.exists() and sha256_file(path) == expected:
        print(f"verified {path}")
        return


    tmp = path.with_suffix(path.suffix + ".part")
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out)
    actual = sha256_file(tmp)
    if actual != expected:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"hash mismatch for {path.name}: expected {expected}, got {actual}"
        )
    tmp.replace(path)
    print(f"downloaded and verified {path}")


def main() -> None:
    raw = Path("data/raw")
    raw.mkdir(parents=True, exist_ok=True)
    for source in SOURCES.values():
        fetch(
            source["url"],
            raw / source["filename"],
            source["sha256"],
        )

    wiki_zip = raw / SOURCES["wikitext"]["filename"]
    wiki_dir = raw / "wikitext-2-raw"
    required = wiki_dir / "wiki.train.raw"
    if not required.exists():
        with zipfile.ZipFile(wiki_zip) as archive:
            archive.extractall(raw)
    if not required.exists():
        raise RuntimeError("WikiText extraction failed")
    print("V0 source data ready")


if __name__ == "__main__":
    main()
