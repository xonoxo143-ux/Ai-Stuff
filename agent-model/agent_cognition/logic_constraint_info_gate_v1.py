from __future__ import annotations
import argparse,json,itertools,random,re
from pathlib import Path

def worlds_for(labels):
    # True contents are the same three semantic categories as the labels:
    # pure A, pure B, mixture AB. Every displayed label is wrong.
    pure_a,pure_b,mix=labels
    contents=(pure_a,pure_b,mix)
    worlds=[]
    for perm in itertools.permutations(contents):
        if all(perm[i]!=labels[i] for i in range(3)):
            worlds.append(dict(zip(labels,perm)))
    return worlds

def observations(content,pure_a,pure_b,mix):
    if content==pure_a:return {pure_a}
    if content==pure_b:return {pure_b}
    if content==mix:return {pure_a,pure_b}
    raise ValueError(content)

def filter_worlds(worlds,box,obs,pure_a,pure_b,mix):
    return [w for w in worlds if obs in observations(w[box],pure_a,pure_b,mix)]

def action_score(worlds,box,pure_a,pure_b,mix):
    possible=set()
    for w in worlds:
        possible |= observations(w[box],pure_a,pure_b,mix)
    branches={}
    for obs in possible:
        survivors=filter_worlds(worlds,box,obs,pure_a,pure_b,mix)
        branches[obs]=len(survivors)
    worst=max(branches.values()) if branches else 10**9
    expected=sum(n*n for n in branches.values())/sum(branches.values()) if branches else 10**9
    return worst,expected,branches

def solve(labels):
    pure_a,pure_b,mix=labels
    worlds=worlds_for(labels)
    scored={}
    for box in labels:
        scored[box]=action_score(worlds,box,pure_a,pure_b,mix)
    # exact minimax, then expected survivors, then stable label order
    best=min(labels,key=lambda b:(scored[b][0],scored[b][1],labels.index(b)))
    mappings={}
    for obs in (pure_a,pure_b):
        survivors=filter_worlds(worlds,best,obs,pure_a,pure_b,mix)
        mappings[obs]=survivors[0] if len(survivors)==1 else None
    return {
        "labels":labels,
        "world_count":len(worlds),
        "scores":{k:{"worst":v[0],"expected":v[1],"branches":v[2]} for k,v in scored.items()},
        "best_box":best,
        "outcome_worlds":mappings,
        "solves_in_one_draw":all(v is not None for v in mappings.values()),
    }

def parse_benchmark(text):
    # The benchmark names the three labels in order and states every label is wrong.
    m=re.search(
        r"labeled\s+([A-Z][A-Z0-9_-]*)\s*,\s*([A-Z][A-Z0-9_-]*)\s*,\s*and\s+([A-Z][A-Z0-9_-]*)",
        text
    )
    if not m:return None
    labels=m.groups()
    if "every label is wrong" not in text.casefold():return None
    # Identify the mixture label semantically from the surface token.
    mix_idx=None
    for i,x in enumerate(labels):
        if x.casefold() in {"mixed","mix","mixture","both","combo","blend"}:
            mix_idx=i;break
    if mix_idx is None:return None
    pures=[x for i,x in enumerate(labels) if i!=mix_idx]
    return (pures[0],pures[1],labels[mix_idx])

def explain(sol):
    a,b,mix=sol["labels"]
    box=sol["best_box"]
    return (
        f"Draw one fruit from the box labeled {box}. "
        f"Because every label is wrong, that box cannot actually be {mix}; "
        f"it must be all {a} or all {b}. "
        f"If you draw {a}, relabel that box {a}; if you draw {b}, relabel it {b}. "
        f"After that observation only one consistent assignment remains, so the other two boxes are forced."
    )

def generated_case(rng):
    base=rng.sample([
        "RUBIES","SAPPHIRES","PEARS","PLUMS","CATS","DOGS",
        "RED","BLUE","TEA","COFFEE","GOLD","SILVER"
    ],2)
    mix=rng.choice(["MIXED","BOTH","COMBO","BLEND"])
    labels=(base[0],base[1],mix)
    rng.shuffle(base)  # irrelevant noise to ensure no reliance on lexical ordering
    return labels

def run(seed,benchmark_prompt):
    rng=random.Random(seed)
    parsed=parse_benchmark(benchmark_prompt)
    benchmark=None if parsed is None else solve(parsed)
    response=None if benchmark is None else explain(benchmark)

    random_ok=0
    random_total=1000
    action_hist={}
    for _ in range(random_total):
        labels=generated_case(rng)
        sol=solve(labels)
        expected=labels[2]
        ok=(
            sol["best_box"]==expected
            and sol["solves_in_one_draw"]
            and sol["scores"][expected]["worst"]==1
        )
        random_ok+=ok
        action_hist[sol["best_box"]]=action_hist.get(sol["best_box"],0)+1

    # Falsification check: choosing either pure-labeled box must have a worse
    # worst-case ambiguity than the optimal mixed-labeled box.
    dominance=False
    if benchmark:
        a,b,mix=benchmark["labels"]
        dominance=(
            benchmark["scores"][mix]["worst"]
            < benchmark["scores"][a]["worst"]
            and benchmark["scores"][mix]["worst"]
            < benchmark["scores"][b]["worst"]
        )

    return {
        "seed":seed,
        "benchmark_parsed":parsed,
        "benchmark_world_count":None if benchmark is None else benchmark["world_count"],
        "benchmark_best_box":None if benchmark is None else benchmark["best_box"],
        "benchmark_scores":None if benchmark is None else benchmark["scores"],
        "benchmark_solves_one_draw":None if benchmark is None else benchmark["solves_in_one_draw"],
        "benchmark_response":response,
        "benchmark_contains_mixed":bool(response and "MIXED" in response),
        "optimal_action_strictly_dominates":dominance,
        "generated_exact":random_ok/random_total,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",default="0,1,2")
    ap.add_argument("--out",default="logic_constraint_info_v1.json")
    a=ap.parse_args()
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:
        bench=json.load(f)
    prompt=next(x["prompt"] for x in bench["turns"] if x["id"]=="logic_01")
    runs=[run(int(s),prompt) for s in a.seeds.split(",")]
    out={
        "passed":all(
            r["benchmark_best_box"]=="MIXED"
            and r["benchmark_solves_one_draw"]
            and r["optimal_action_strictly_dominates"]
            and r["generated_exact"]==1.0
            for r in runs
        ),
        "runs":runs,
    }
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
