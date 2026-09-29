from __future__ import annotations

from dataclasses import dataclass
import random

import torch

PAD = 0
ENTITY = 1
RELATION = 2
EVENT = 3
RULE = 4
MEMORY = 5
QUERY = 6

OP_OLDER = 1
OP_AT = 2
OP_MOVE = 3
OP_EDGE = 4
OP_MAP = 5
OP_VALUE = 6
OP_SET = 7
OP_INC = 8
OP_DEC = 9

Q_COMPARE = 1
Q_STATE = 2
Q_REACHABLE = 3
Q_MAP = 4
Q_RECALL = 5

TRUE = 30
FALSE = 31

MAX_SYMBOL = 31
MAX_OPERATOR = 12
MAX_POSITION = 31
MAX_SLOTS = 24

FAMILY_RELATION = 0
FAMILY_STATE = 1
FAMILY_GRAPH = 2
FAMILY_RULE = 3
FAMILY_MEMORY = 4
FAMILY_NAMES = ("relation", "state", "graph", "rule", "memory")


@dataclass(frozen=True)
class Example:
    slots: torch.Tensor
    mask: torch.Tensor
    answer: int
    family: int
    difficulty: int


def _pack(rows, answer: int, family: int, difficulty: int) -> Example:
    if len(rows) > MAX_SLOTS:
        raise ValueError("too many slots")
    slots = torch.zeros(MAX_SLOTS, 6, dtype=torch.long)
    mask = torch.zeros(MAX_SLOTS, dtype=torch.bool)
    for i, row in enumerate(rows):
        slots[i] = torch.tensor(row, dtype=torch.long)
        mask[i] = True
    return Example(slots, mask, int(answer), int(family), int(difficulty))


def relation_example(rng: random.Random, *, ood: bool) -> Example:
    hops = rng.randint(4, 6) if ood else rng.randint(2, 4)
    entities = rng.sample(range(1, 20), hops + 1)
    rows = [(ENTITY, entity, 0, 0, 0, pos) for pos, entity in enumerate(entities)]
    facts = [
        (RELATION, entities[pos], entities[pos + 1], 0, OP_OLDER, pos)
        for pos in range(hops)
    ]
    rng.shuffle(facts)
    rows.extend(facts)
    min_distance = 3 if ood and hops >= 3 else 2
    i = rng.randint(0, max(0, len(entities) - min_distance - 1))
    j = rng.randint(i + min_distance, len(entities) - 1)
    if rng.random() < 0.5:
        a, b, answer = entities[i], entities[j], TRUE
    else:
        a, b, answer = entities[j], entities[i], FALSE
    rows.append((QUERY, a, b, 0, Q_COMPARE, len(rows)))
    return _pack(rows, answer, FAMILY_RELATION, j - i)


def state_example(rng: random.Random, *, ood: bool) -> Example:
    events = rng.randint(5, 8) if ood else rng.randint(2, 4)
    obj = rng.randint(1, 8)
    value = rng.randint(1, 8)
    rows = [
        (ENTITY, obj, 0, 0, 0, 0),
        (MEMORY, obj, value, 0, OP_AT, 0),
    ]
    for step in range(1, events + 1):
        op_choice = rng.random()
        if op_choice < 0.25:
            value = rng.randint(1, 8)
            rows.append((EVENT, obj, value, 0, OP_SET, step))
        elif op_choice < 0.625:
            value = (value % 8) + 1
            rows.append((EVENT, obj, 0, 0, OP_INC, step))
        else:
            value = ((value - 2) % 8) + 1
            rows.append((EVENT, obj, 0, 0, OP_DEC, step))
        if rng.random() < 0.35 and len(rows) < MAX_SLOTS - 2:
            other = rng.choice([x for x in range(1, 9) if x != obj])
            distract_op = rng.choice((OP_INC, OP_DEC, OP_SET))
            distract_value = rng.randint(1, 8) if distract_op == OP_SET else 0
            rows.append((EVENT, other, distract_value, 0, distract_op, step))
    rows.append((QUERY, obj, 0, 0, Q_STATE, events + 1))
    return _pack(rows, value, FAMILY_STATE, events)


def graph_example(rng: random.Random, *, ood: bool) -> Example:
    n = rng.randint(8, 10) if ood else rng.randint(4, 6)
    nodes = rng.sample(range(1, 21), n)
    want_reachable = bool(rng.getrandbits(1))
    rows = [(ENTITY, node, 0, 0, 0, i) for i, node in enumerate(nodes)]
    edges = set()
    if want_reachable:
        path_len = (
            rng.randint(max(2, n - 3), n - 1)
            if ood
            else rng.randint(1, min(3, n - 1))
        )
        path_nodes = (
            [nodes[0]]
            + rng.sample(nodes[1:-1], max(0, path_len - 1))
            + [nodes[-1]]
        )
        for a, b in zip(path_nodes, path_nodes[1:]):
            edges.add(tuple(sorted((a, b))))
    else:
        left = set(nodes[: max(2, n // 2)])
        right = set(nodes) - left
        if nodes[-1] in left:
            left.remove(nodes[-1])
            right.add(nodes[-1])
        if nodes[0] not in left:
            right.remove(nodes[0])
            left.add(nodes[0])
        for group in (list(left), list(right)):
            rng.shuffle(group)
            for a, b in zip(group, group[1:]):
                edges.add(tuple(sorted((a, b))))
    possible = [
        tuple(sorted((a, b)))
        for i, a in enumerate(nodes)
        for b in nodes[i + 1 :]
    ]
    rng.shuffle(possible)
    target_edges = min(len(possible), n + 2)
    for a, b in possible:
        if len(edges) >= target_edges:
            break
        if not want_reachable:
            left_side = a in left and b in left
            right_side = a in right and b in right
            if not (left_side or right_side):
                continue
        edges.add((a, b))
    for pos, (a, b) in enumerate(edges):
        rows.append((RELATION, a, b, 0, OP_EDGE, pos))
    rows.append((QUERY, nodes[0], nodes[-1], 0, Q_REACHABLE, len(rows)))
    return _pack(rows, TRUE if want_reachable else FALSE, FAMILY_GRAPH, n)


def rule_example(rng: random.Random, *, ood: bool) -> Example:
    offset = rng.randint(1, 3)
    values = list(range(1, 9))
    rng.shuffle(values)
    example_count = 2 if not ood else 3
    query_x = values[example_count]
    rows = []
    for pos, x in enumerate(values[:example_count]):
        y = ((x - 1 + offset) % 8) + 1
        rows.append((RULE, x, y, 0, OP_MAP, pos))
    rows.append((QUERY, query_x, 0, 0, Q_MAP, len(rows)))
    answer = ((query_x - 1 + offset) % 8) + 1
    return _pack(rows, answer, FAMILY_RULE, example_count)


def memory_example(rng: random.Random, *, ood: bool) -> Example:
    pairs = rng.randint(8, 12) if ood else rng.randint(3, 6)
    keys = rng.sample(range(1, 14), pairs)
    values = rng.sample(range(14, 30), pairs)
    rows = []
    order = list(range(pairs))
    rng.shuffle(order)
    for pos, i in enumerate(order):
        rows.append((MEMORY, keys[i], values[i], 0, OP_VALUE, pos))
    q = rng.randrange(pairs)
    rows.append((QUERY, keys[q], 0, 0, Q_RECALL, len(rows)))
    return _pack(rows, values[q], FAMILY_MEMORY, pairs)


GENERATORS = (
    relation_example,
    state_example,
    graph_example,
    rule_example,
    memory_example,
)


def generate_example(
    rng: random.Random,
    family: int | None = None,
    *,
    ood: bool = False,
) -> Example:
    if family is None:
        family = rng.randrange(len(GENERATORS))
    return GENERATORS[family](rng, ood=ood)


def batch_examples(
    seed: int,
    batch_size: int,
    *,
    family: int | None = None,
    ood: bool = False,
):
    rng = random.Random(seed)
    examples = [
        generate_example(rng, family, ood=ood)
        for _ in range(batch_size)
    ]
    slots = torch.stack([e.slots for e in examples])
    mask = torch.stack([e.mask for e in examples])
    answer = torch.tensor([e.answer for e in examples], dtype=torch.long)
    families = torch.tensor([e.family for e in examples], dtype=torch.long)
    return slots, mask, answer, families


def oracle_answer(example: Example) -> int:
    rows = example.slots[example.mask].tolist()
    query = next(row for row in rows if row[0] == QUERY)
    qop = query[4]

    if qop == Q_COMPARE:
        source, target = query[1], query[2]
        adjacency = {}
        for kind, a, b, _c, op, _pos in rows:
            if kind == RELATION and op == OP_OLDER:
                adjacency.setdefault(a, []).append(b)
        seen = {source}
        frontier = [source]
        while frontier:
            node = frontier.pop()
            if node == target:
                return TRUE
            for nxt in adjacency.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return FALSE

    if qop == Q_STATE:
        obj = query[1]
        initial = [
            row
            for row in rows
            if row[0] == MEMORY and row[4] == OP_AT and row[1] == obj
        ]
        if not initial:
            raise ValueError("missing initial state")
        value = initial[0][2]
        events = sorted(
            [row for row in rows if row[0] == EVENT and row[1] == obj],
            key=lambda row: row[5],
        )
        for _kind, _a, b, _c, op, _pos in events:
            if op == OP_SET:
                value = b
            elif op == OP_INC:
                value = (value % 8) + 1
            elif op == OP_DEC:
                value = ((value - 2) % 8) + 1
        return value

    if qop == Q_REACHABLE:
        source, target = query[1], query[2]
        adjacency = {}
        for kind, a, b, _c, op, _pos in rows:
            if kind == RELATION and op == OP_EDGE:
                adjacency.setdefault(a, []).append(b)
                adjacency.setdefault(b, []).append(a)
        seen = {source}
        frontier = [source]
        while frontier:
            node = frontier.pop()
            if node == target:
                return TRUE
            for nxt in adjacency.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return FALSE

    if qop == Q_MAP:
        examples = [
            row
            for row in rows
            if row[0] == RULE and row[4] == OP_MAP
        ]
        if not examples:
            raise ValueError("missing rule examples")
        x, y = examples[0][1], examples[0][2]
        offset = (y - x) % 8
        query_x = query[1]
        return ((query_x - 1 + offset) % 8) + 1

    if qop == Q_RECALL:
        key = query[1]
        for kind, a, b, _c, op, _pos in rows:
            if kind == MEMORY and op == OP_VALUE and a == key:
                return b
        raise ValueError("missing memory key")

    raise ValueError(f"unknown query op {qop}")
