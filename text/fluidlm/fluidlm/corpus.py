from __future__ import annotations

import random
import urllib.request
from pathlib import Path


URLS = {
    "tiny-shakespeare": "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",
    "alice": "https://www.gutenberg.org/cache/epub/11/pg11.txt",
}


def synthetic_corpus(lines: int = 12000, seed: int = 0) -> str:
    """Create a deterministic toy language with recurring entities and relations."""
    rng = random.Random(seed)
    people = ["alice", "bob", "carol", "david", "eve", "frank"]
    objects = ["red ball", "blue book", "small key", "glass cup", "green box", "silver coin"]
    places = ["garden", "kitchen", "library", "hall", "workshop", "river"]
    verbs = ["finds", "moves", "holds", "drops", "gives", "takes", "sees", "hides"]

    out: list[str] = []
    for _ in range(lines):
        a, b = rng.sample(people, 2)
        obj = rng.choice(objects)
        place = rng.choice(places)
        verb = rng.choice(verbs)
        template = rng.randrange(6)
        if template == 0:
            out.append(f"{a} {verb} the {obj} in the {place}.")
        elif template == 1:
            out.append(f"{a} sees {b} near the {place}.")
        elif template == 2:
            out.append(f"the {obj} is in the {place}.")
        elif template == 3:
            out.append(f"{a} gives the {obj} to {b}.")
        elif template == 4:
            out.append(f"after {a} visits the {place}, {a} {verb} the {obj}.")
        else:
            out.append(f"{b} asks {a} where the {obj} is.")
    return "\n".join(out) + "\n"


def load_corpus(name: str, cache_dir: str | Path = "data/cache") -> str:
    """Load a supported corpus, downloading and caching public text when needed."""
    if name == "synthetic":
        return synthetic_corpus()

    if name not in URLS:
        raise ValueError(f"Unknown corpus: {name}")

    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{name}.txt"

    if not path.exists():
        try:
            request = urllib.request.Request(
                URLS[name],
                headers={"User-Agent": "FluidLM research prototype/0.1"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
            path.write_text(text, encoding="utf-8")
        except Exception as exc:
            raise RuntimeError(
                f"Could not download {name} from {URLS[name]}: {exc}"
            ) from exc

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) < 1000:
        raise RuntimeError(f"Corpus {name} is unexpectedly small ({len(text)} chars)")
    return text
