from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import product

OPS = {
    "DOUBLE": lambda x: x * 2,
    "ADD3": lambda x: x + 3,
    "SQUARE": lambda x: x * x,
    "NEG": lambda x: -x,
    "ABS": lambda x: abs(x),
}
OP_NAMES = tuple(OPS)
PHRASES = {
    "DOUBLE": ("double it", "multiply it by two"),
    "ADD3": ("add three", "increase it by three"),
    "SQUARE": ("square it", "multiply it by itself"),
    "NEG": ("negate it", "flip its sign"),
    "ABS": ("take its absolute value", "make it nonnegative"),
}
CONNECTORS = (
    "first {a}, then {b}",
    "{a}, and after that {b}",
    "do {a} before you {b}",
)

def execute(program, x):
    for op in program:
        x = OPS[op](x)
    return x

def examples(program, xs):
    return [(x, execute(program, x)) for x in xs]

def consistent(program, pairs):
    return all(execute(program, x) == y for x, y in pairs)

def search_programs(pairs, min_len=1, max_len=2):
    out=[]
    for n in range(min_len,max_len+1):
        for prog in product(OP_NAMES, repeat=n):
            if consistent(prog,pairs): out.append(prog)
    return out

@dataclass
class PhraseHypothesis:
    candidates:set[tuple[str,...]]
    support:int=0

class GroundedLanguageLearner:
    def __init__(self):
        self.phrases:dict[str,PhraseHypothesis]={}
        self.durable_phrases:dict[str,tuple[str,...]]={}
        self.connectors:dict[str,tuple[int,int]]={}
        self.connector_support=defaultdict(int)

    def observe_atomic(self, phrase, pairs):
        candidates=set(search_programs(pairs,1,1))
        if phrase in self.phrases:
            candidates &= self.phrases[phrase].candidates
            support=self.phrases[phrase].support+1
        else:
            support=1
        self.phrases[phrase]=PhraseHypothesis(candidates,support)
        if len(candidates)==1:
            self.durable_phrases[phrase]=next(iter(candidates))
        return sorted(candidates)

    def phrase_program(self, phrase):
        return self.durable_phrases.get(phrase)

    def _locate_known_phrases(self, text):
        hits=[]
        for p,prog in self.durable_phrases.items():
            start=text.find(p)
            if start>=0:hits.append((start,start+len(p),p,prog))
        # Keep non-overlapping longest hits greedily.
        hits.sort(key=lambda h:(h[0],-(h[1]-h[0])))
        out=[]
        end=-1
        for h in hits:
            if h[0]>=end:
                out.append(h);end=h[1]
        return out

    def observe_composition(self,text,pairs):
        hits=self._locate_known_phrases(text)
        if len(hits)!=2:return None
        (s1,e1,p1,pr1),(s2,e2,p2,pr2)=hits
        skeleton=(text[:s1]+"<A>"+text[e1:s2]+"<B>"+text[e2:]).strip()
        candidates=[]
        if consistent(pr1+pr2,pairs):candidates.append((0,1))
        if consistent(pr2+pr1,pairs):candidates.append((1,0))
        if len(candidates)!=1:return {"skeleton":skeleton,"order":None}
        order=candidates[0]
        self.connector_support[(skeleton,order)]+=1
        if self.connector_support[(skeleton,order)]>=2:
            self.connectors[skeleton]=order
        return {"skeleton":skeleton,"order":order}

    def parse_composition(self,text):
        hits=self._locate_known_phrases(text)
        if len(hits)!=2:return None
        (s1,e1,p1,pr1),(s2,e2,p2,pr2)=hits
        skeleton=(text[:s1]+"<A>"+text[e1:s2]+"<B>"+text[e2:]).strip()
        order=self.connectors.get(skeleton)
        if order is None:return None
        return (pr1,pr2)[order[0]] + (pr1,pr2)[order[1]]

def run(seed):
    rng=random.Random(seed)
    L=GroundedLanguageLearner()

    # Phase 1: no gold semantics. Infer each phrase from observed behavior.
    atomic_records=[]
    for op in OP_NAMES:
        for phrase in PHRASES[op]:
            xs=rng.sample([-5,-3,-2,-1,1,2,3,4,5],3)
            cand=L.observe_atomic(phrase,examples((op,),xs))
            atomic_records.append({"phrase":phrase,"candidates":cand})
    atomic_exact=sum(
        L.phrase_program(p)==(op,)
        for op,ps in PHRASES.items() for p in ps
    )

    # Phase 2: infer connector order from consequences, not labels.
    connector_records=[]
    for ci,conn in enumerate(CONNECTORS):
        # two grounded examples are required before connector becomes durable.
        pairs=[("DOUBLE","ADD3"),("NEG","ABS")]
        for aop,bop in pairs:
            a=PHRASES[aop][ci%2];b=PHRASES[bop][(ci+1)%2]
            text=conn.format(a=a,b=b)
            xs=rng.sample([-4,-3,-2,1,2,3,4],3)
            rec=L.observe_composition(text,examples((aop,bop),xs))
            connector_records.append({"text":text,"record":rec})

    # Test unseen op-pair and phrase combinations through learned connector semantics.
    combo_tests=[]
    combo_ok=0
    for _ in range(300):
        aop,bop=rng.sample(OP_NAMES,2)
        conn=rng.choice(CONNECTORS)
        a=rng.choice(PHRASES[aop]);b=rng.choice(PHRASES[bop])
        text=conn.format(a=a,b=b)
        prog=L.parse_composition(text)
        x=rng.choice([-6,-4,-3,-2,-1,1,2,3,4,6])
        want=execute((aop,bop),x)
        got=None if prog is None else execute(prog,x)
        ok=(got==want)
        combo_ok+=ok
        combo_tests.append((text,prog,x,got,want,ok))

    # Phase 3: one-shot new surface phrase from execution evidence.
    novel="make it twice as large"
    novel_pairs=examples(("DOUBLE",),[-3,2,5])
    pre=L.phrase_program(novel)
    novel_candidates=L.observe_atomic(novel,novel_pairs)
    post=L.phrase_program(novel)

    novel_combo_ok=0
    for _ in range(150):
        bop=rng.choice([x for x in OP_NAMES if x!="DOUBLE"])
        b=rng.choice(PHRASES[bop])
        conn=rng.choice(CONNECTORS)
        text=conn.format(a=novel,b=b)
        prog=L.parse_composition(text)
        x=rng.choice([-5,-2,-1,1,2,4,5])
        want=execute(("DOUBLE",bop),x)
        got=None if prog is None else execute(prog,x)
        novel_combo_ok+=got==want

    # Phase 4: ambiguous evidence must remain tentative until another context resolves it.
    ambiguous="zeroish"
    first=L.observe_atomic(ambiguous,[(0,0)])
    after_first=L.phrase_program(ambiguous)
    second=L.observe_atomic(ambiguous,[(3,6)])
    after_second=L.phrase_program(ambiguous)

    # Regression: all old atomic mappings remain intact.
    regression=sum(
        L.phrase_program(p)==(op,)
        for op,ps in PHRASES.items() for p in ps
    )

    return {
        "seed":seed,
        "atomic_grounded_exact":atomic_exact,
        "atomic_grounded_total":sum(len(v) for v in PHRASES.values()),
        "durable_connectors":len(L.connectors),
        "connector_expected":len(CONNECTORS),
        "unseen_composition_exact":combo_ok/len(combo_tests),
        "one_shot_novel_preexisting":pre is not None,
        "one_shot_novel_candidates":[list(x) for x in novel_candidates],
        "one_shot_novel_durable":post==("DOUBLE",),
        "one_shot_novel_composition_exact":novel_combo_ok/150,
        "ambiguous_first_candidates":[list(x) for x in first],
        "ambiguous_promoted_after_one":after_first is not None,
        "ambiguous_second_candidates":[list(x) for x in second],
        "ambiguous_resolved_to_double":after_second==("DOUBLE",),
        "old_phrase_regression_exact":regression,
        "old_phrase_regression_total":sum(len(v) for v in PHRASES.values()),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",default="0,1,2")
    ap.add_argument("--out",default="execution_grounding_v0.json")
    a=ap.parse_args()
    runs=[run(int(x)) for x in a.seeds.split(",")]
    out={"runs":runs,"passed":all(
        r["atomic_grounded_exact"]==r["atomic_grounded_total"]
        and r["durable_connectors"]==r["connector_expected"]
        and r["unseen_composition_exact"]==1.0
        and r["one_shot_novel_durable"]
        and r["one_shot_novel_composition_exact"]==1.0
        and not r["ambiguous_promoted_after_one"]
        and r["ambiguous_resolved_to_double"]
        and r["old_phrase_regression_exact"]==r["old_phrase_regression_total"]
        for r in runs)}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
