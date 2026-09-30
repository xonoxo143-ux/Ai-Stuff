from __future__ import annotations

import argparse
import json
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
PROBE_DOMAIN = tuple(range(-7, 8))

def execute(program, x):
    for op in program:
        x = OPS[op](x)
    return x

def consistent(program, pairs):
    return all(execute(program, x) == y for x, y in pairs)

def search_programs(pairs, min_len=1, max_len=2):
    out=[]
    for n in range(min_len,max_len+1):
        for prog in product(OP_NAMES, repeat=n):
            if consistent(prog,pairs): out.append(prog)
    return out

def best_probe(candidates, used=()):
    used=set(used)
    best=None
    for x in PROBE_DOMAIN:
        if x in used: continue
        outputs=defaultdict(list)
        for p in candidates:
            outputs[execute(p,x)].append(p)
        # Prefer maximum semantic partition count; then smallest largest bucket;
        # then smaller |x| for cheap/simple experiments.
        if len(outputs)<=1: continue
        largest=max(len(v) for v in outputs.values())
        score=(len(outputs),-largest,-abs(x))
        if best is None or score>best[0]: best=(score,x)
    return None if best is None else best[1]

@dataclass
class PhraseHypothesis:
    candidates:set[tuple[str,...]]
    evidence:list[tuple[int,int]]

class ActiveGroundedLearner:
    def __init__(self):
        self.phrases={}
        self.durable_phrases={}
        self.connectors={}
        self.connector_hypotheses={}
        self.active_probes=0

    def observe_atomic(self, phrase, pair):
        current=set(search_programs([pair],1,1))
        if phrase in self.phrases:
            current &= self.phrases[phrase].candidates
            ev=self.phrases[phrase].evidence+[pair]
        else:
            ev=[pair]
        self.phrases[phrase]=PhraseHypothesis(current,ev)
        if len(current)==1:self.durable_phrases[phrase]=next(iter(current))
        return current

    def actively_ground_atomic(self, phrase, hidden_op, initial_x):
        self.observe_atomic(phrase,(initial_x,OPS[hidden_op](initial_x)))
        while len(self.phrases[phrase].candidates)>1:
            h=self.phrases[phrase]
            x=best_probe(h.candidates,[a for a,_ in h.evidence])
            if x is None:break
            self.active_probes+=1
            self.observe_atomic(phrase,(x,OPS[hidden_op](x)))
        return self.durable_phrases.get(phrase)

    def _locate(self,text):
        hits=[]
        for p,prog in self.durable_phrases.items():
            s=text.find(p)
            if s>=0:hits.append((s,s+len(p),p,prog))
        hits.sort(key=lambda h:(h[0],-(h[1]-h[0])))
        out=[]; end=-1
        for h in hits:
            if h[0]>=end:out.append(h);end=h[1]
        return out

    def connector_skeleton(self,text):
        hits=self._locate(text)
        if len(hits)!=2:return None,None
        (s1,e1,p1,pr1),(s2,e2,p2,pr2)=hits
        sk=(text[:s1]+"<A>"+text[e1:s2]+"<B>"+text[e2:]).strip()
        return sk,(pr1,pr2)

    def observe_connector(self,text,pair):
        sk,parts=self.connector_skeleton(text)
        if sk is None:return None
        options={(0,1),(1,0)}
        if sk in self.connector_hypotheses:
            options &= self.connector_hypotheses[sk]["orders"]
            ev=self.connector_hypotheses[sk]["evidence"]+[pair]
        else:ev=[pair]
        good=set()
        for order in options:
            prog=parts[order[0]]+parts[order[1]]
            if consistent(prog,ev):good.add(order)
        self.connector_hypotheses[sk]={"orders":good,"evidence":ev,"parts":parts}
        if len(good)==1:self.connectors[sk]=next(iter(good))
        return sk

    def actively_ground_connector(self,text,hidden_order=(0,1),initial_x=0):
        sk,parts=self.connector_skeleton(text)
        true_prog=parts[hidden_order[0]]+parts[hidden_order[1]]
        self.observe_connector(text,(initial_x,execute(true_prog,initial_x)))
        h=self.connector_hypotheses[sk]
        while len(h["orders"])>1:
            programs=[parts[o[0]]+parts[o[1]] for o in sorted(h["orders"])]
            x=best_probe(programs,[a for a,_ in h["evidence"]])
            if x is None:break
            self.active_probes+=1
            self.observe_connector(text,(x,execute(true_prog,x)))
            h=self.connector_hypotheses[sk]
        return self.connectors.get(sk)

    def parse_composition(self,text):
        sk,parts=self.connector_skeleton(text)
        if sk is None or sk not in self.connectors:return None
        o=self.connectors[sk]
        return parts[o[0]]+parts[o[1]]

def run(seed):
    rng=random.Random(seed)
    L=ActiveGroundedLearner()

    # Start with only ONE passive observation per phrase; active probes must resolve ambiguity.
    for op in OP_NAMES:
        for phrase in PHRASES[op]:
            x=rng.choice(PROBE_DOMAIN)
            L.actively_ground_atomic(phrase,op,x)

    atomic=sum(L.durable_phrases.get(p)==(op,) for op,ps in PHRASES.items() for p in ps)

    # Learn each sequencing construction from one passive observation + active disambiguation.
    for ci,conn in enumerate(CONNECTORS):
        aop,bop=("DOUBLE","ADD3") if ci%2==0 else ("NEG","SQUARE")
        a=PHRASES[aop][ci%2];b=PHRASES[bop][(ci+1)%2]
        text=conn.format(a=a,b=b)
        L.actively_ground_connector(text,(0,1),rng.choice(PROBE_DOMAIN))

    # Unseen lexical/op compositions.
    combo=0
    for _ in range(500):
        aop,bop=rng.sample(OP_NAMES,2);conn=rng.choice(CONNECTORS)
        a=rng.choice(PHRASES[aop]);b=rng.choice(PHRASES[bop]);text=conn.format(a=a,b=b)
        p=L.parse_composition(text);x=rng.choice(PROBE_DOMAIN)
        combo += p is not None and execute(p,x)==execute((aop,bop),x)

    # New phrase: one ordinary observation, then only ask for a probe if still ambiguous.
    novel="make it twice as large"
    initial_x=rng.choice(PROBE_DOMAIN)
    before=L.durable_phrases.get(novel)
    probes_before=L.active_probes
    L.actively_ground_atomic(novel,"DOUBLE",initial_x)
    novel_probes=L.active_probes-probes_before
    novel_ok=L.durable_phrases.get(novel)==("DOUBLE",)

    novel_combo=0
    for _ in range(200):
        bop=rng.choice([x for x in OP_NAMES if x!="DOUBLE"]);b=rng.choice(PHRASES[bop])
        text=rng.choice(CONNECTORS).format(a=novel,b=b);p=L.parse_composition(text);x=rng.choice(PROBE_DOMAIN)
        novel_combo += p is not None and execute(p,x)==execute(("DOUBLE",bop),x)

    # Force ambiguous first evidence, verify no premature commitment,
    # then let the learner actively choose the distinguishing input.
    amb="zeroish"
    L.observe_atomic(amb,(0,0))
    first=sorted(L.phrases[amb].candidates)
    premature=amb in L.durable_phrases
    x=best_probe(L.phrases[amb].candidates,[0])
    L.active_probes+=1
    # Hidden intended meaning is DOUBLE.
    L.observe_atomic(amb,(x,OPS["DOUBLE"](x)))
    resolved=L.durable_phrases.get(amb)==("DOUBLE",)

    regression=sum(L.durable_phrases.get(p)==(op,) for op,ps in PHRASES.items() for p in ps)

    return {
        "seed":seed,
        "atomic_exact":atomic,"atomic_total":10,
        "connectors_exact":len(L.connectors),"connectors_total":3,
        "unseen_composition_exact":combo/500,
        "novel_preexisting":before is not None,
        "novel_resolved":novel_ok,
        "novel_active_probes":novel_probes,
        "novel_composition_exact":novel_combo/200,
        "forced_ambiguous_first_candidates":[list(p) for p in first],
        "forced_ambiguous_premature_promotion":premature,
        "forced_ambiguous_probe_x":x,
        "forced_ambiguous_resolved":resolved,
        "old_phrase_regression_exact":regression,
        "active_probe_count_total":L.active_probes,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="active_execution_grounding_v1.json");a=ap.parse_args()
    runs=[run(int(x)) for x in a.seeds.split(",")]
    passed=all(
        r["atomic_exact"]==10 and r["connectors_exact"]==3
        and r["unseen_composition_exact"]==1.0
        and r["novel_resolved"] and r["novel_composition_exact"]==1.0
        and not r["forced_ambiguous_premature_promotion"]
        and r["forced_ambiguous_resolved"]
        and r["old_phrase_regression_exact"]==10
        for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
