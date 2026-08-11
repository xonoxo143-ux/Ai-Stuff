from __future__ import annotations

from semzip.vm_delta import RelationDelta
from semzip.vm_patch import ReturnObligation, SemanticPatch
from semzip.vm_patch_mdl import (
    discover_patch_macro_candidates,
    factor_pattern,
    patch_pattern,
)


def transfer(subject, source, destination):
    return SemanticPatch.build((
        RelationDelta.build(subject, source, destination, ("owner", "possessor")),
    ))


def exchange(goods, seller, buyer, payment):
    return SemanticPatch.build((
        RelationDelta.build(goods, seller, buyer, ("owner", "possessor")),
        RelationDelta.build(payment, buyer, seller, ("owner", "possessor")),
    ))


def loan(subject, lender, borrower):
    return SemanticPatch.build(
        (RelationDelta.build(subject, lender, borrower, ("possessor",)),),
        return_obligations=(ReturnObligation.build(subject, borrower, lender),),
    )


def main():
    corpus = (
        transfer("book", "john", "mary"),
        transfer("key", "alice", "bob"),
        transfer("gem", "quinn", "zara"),
        transfer("map", "lee", "sam"),
        exchange("sword", "anna", "ben", "coin"),
        exchange("shield", "cara", "dave", "token"),
        exchange("ring", "erin", "finn", "credit"),
        loan("camera", "gina", "hugo"),
        loan("tool", "iris", "jules"),
    )

    candidates = discover_patch_macro_candidates(
        corpus,
        min_records=2,
        max_records=4,
        min_occurrences=2,
    )
    assert candidates, "no cost-saving effect macro discovered"

    transfer_shape = patch_pattern(transfer("thing", "source", "destination")).pattern
    best = candidates[0]
    assert best.pattern == transfer_shape, "most useful macro should be reusable transfer effect"
    assert best.savings > 0
    assert best.encoded_cost < best.base_cost

    exchange_shape = patch_pattern(
        exchange("goods", "seller", "buyer", "payment")
    ).pattern
    factorization = factor_pattern(exchange_shape, transfer_shape)
    assert factorization is not None
    assert len(factorization) == 2

    print("patch_abstraction_gate=PASS")
    print(f"corpus_patches={len(corpus)}")
    print(f"candidate_count={len(candidates)}")
    print(f"best_macro_records={best.pattern.record_count}")
    print(f"best_macro_occurrences={best.occurrences}")
    print(f"base_description_cost={best.base_cost}")
    print(f"encoded_description_cost={best.encoded_cost}")
    print(f"description_savings={best.savings}")
    print(f"exchange_transfer_factors={len(factorization)}")


if __name__ == "__main__":
    main()
