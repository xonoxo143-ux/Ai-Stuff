from __future__ import annotations

import random
import torch


def make_micro_english(seed: int, examples: int = 2200) -> bytes:
    """Deterministic synthetic English-ish corpus for fast architecture tests."""
    r = random.Random(seed)
    names = ["Mia", "Leo", "Ava", "Noah", "Ivy", "Owen", "Luna", "Ezra"]
    animals = ["cat", "dog", "fox", "rabbit", "bird", "mouse"]
    colors = ["red", "blue", "green", "yellow", "purple", "orange"]
    places = ["garden", "forest", "house", "river", "hill", "school"]
    objects = ["ball", "book", "key", "apple", "box", "kite"]
    moods = ["happy", "curious", "tired", "brave", "quiet", "excited"]
    verbs = ["found", "carried", "lost", "shared", "watched", "followed"]
    lines: list[str] = []
    for _ in range(examples):
        name = r.choice(names)
        animal = r.choice(animals)
        color = r.choice(colors)
        place = r.choice(places)
        obj = r.choice(objects)
        mood = r.choice(moods)
        verb = r.choice(verbs)
        kind = r.randrange(5)
        if kind == 0:
            lines.append(
                f"{name} saw a {color} {animal} near the {place}. "
                f"The {animal} {verb} a {obj}. {name} felt {mood}.\n"
            )
        elif kind == 1:
            lines.append(
                f"Question: Where did {name} see the {animal}? "
                f"Answer: near the {place}.\n"
            )
        elif kind == 2:
            lines.append(
                f"Question: What color was the {animal}? Answer: {color}.\n"
            )
        elif kind == 3:
            lines.append(
                f"{name} had a {obj}. Then {name} went to the {place}. "
                f"The {obj} was important because {name} was {mood}.\n"
            )
        else:
            other = r.choice([candidate for candidate in names if candidate != name])
            lines.append(
                f'{name} told {other}, "The {color} {animal} is by the {place}." '
                f"{other} remembered the message.\n"
            )
    return "".join(lines).encode("utf-8")


class ByteBatchStream:
    def __init__(self, data: bytes, seed: int = 0) -> None:
        self.data = torch.tensor(list(data), dtype=torch.long)
        self.rng = random.Random(seed)

    def batch(
        self,
        batch_size: int,
        sequence_length: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if sequence_length + 1 >= len(self.data):
            raise ValueError("sequence longer than corpus")
        starts = [
            self.rng.randrange(0, len(self.data) - sequence_length - 1)
            for _ in range(batch_size)
        ]
        x = torch.stack(
            [self.data[s : s + sequence_length] for s in starts]
        )
        y = torch.stack(
            [self.data[s + 1 : s + sequence_length + 1] for s in starts]
        )
        return x, y
