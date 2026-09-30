from __future__ import annotations

import argparse
import itertools
import json
import random
import string
from dataclasses import dataclass

REL=("creates","causes","depends_on","constrains","enables","opposes","protects","transforms")

def name(i):
    a=string.ascii_lowercase
    out="";n=i+1
    while n:
        n,r=divmod(n-1,26);out=a[r]+out
    return "n"+out

@dataclass(frozen=True,order=True)
class Edge:
    pred:str
    a:str
    b:str

@dataclass
class Domain:
    nodes:list[str]
    edges:set[Edge]
    attrs:dict[str,str]

def connected_template(rng,n=5,m=6):
    nodes=[f"r{i}" for i in range(n)]
    edges=set()
    # Ensure a connected directed backbone.
    order=list(nodes);rng.shuffle(order)
    for i in range(n-1):
        edges.add(Edge(rng.choice(REL),order[i],order[i+1]))
    while len(edges)<m:
        a,b=rng.sample(nodes,2)
        edges.add(Edge(rng.choice(REL),a,b))
    return Domain(nodes,edges,{x:"" for x in nodes})

def renamed(domain,rng,prefix,extra=0,wrong_surface=False):
    new_nodes=[prefix+name(rng.randrange(1,2_000_000)) for _ in domain.nodes]
    mp=dict(zip(domain.nodes,new_nodes))
    edges={Edge(e.pred,mp[e.a],mp[e.b]) for e in domain.edges}
    while extra:
        a,b=rng.sample(new_nodes,2);e=Edge(rng.choice(REL),a,b)
        if e not in edges:edges.add(e);extra-=1
    # Surface attributes can intentionally imply the WRONG correspondence.
    attrs={}
    shuffled=new_nodes[:];rng.shuffle(shuffled)
    for i,node in enumerate(new_nodes):
        source=domain.nodes[i] if not wrong_surface else domain.nodes[new_nodes.index(shuffled[i])]
        attrs[node]="surface_"+source
    return Domain(new_nodes,edges,attrs),mp

def project(edge,mapping):
    return Edge(edge.pred,mapping[edge.a],mapping[edge.b])

def connected_bonus(edges):
    es=list(edges);bonus=0
    for i in range(len(es)):
        for j in range(i+1,len(es)):
            x,y=es[i],es[j]
            if {x.a,x.b}&{y.a,y.b}:bonus+=1
    return bonus

def best_mapping(base,target):
    if len(base.nodes)!=len(target.nodes):return None
    best=None
    for perm in itertools.permutations(target.nodes):
        mp=dict(zip(base.nodes,perm))
        matched={e for e in base.edges if project(e,mp) in target.edges}
        # Relations dominate. Connected matched systems break equal-match ties.
        score=(len(matched),connected_bonus(matched))
        if best is None or score>best[0]:
            best=(score,mp,matched)
    score,mp,matched=best
    unmatched=sorted(base.edges-matched)
    projected_unmatched=[project(e,mp) for e in unmatched]
    return {
      "mapping":mp,
      "matched":sorted(matched),
      "unmatched":unmatched,
      "projected_unmatched":projected_unmatched,
      "ratio":len(matched)/len(base.edges),
      "systematicity":score[1],
    }

def synthesize(base,target):
    m=best_mapping(base,target)
    if m is None:return {"classification":"WEAK","reason":"node-count mismatch"}
    if not m["unmatched"] and len(m["matched"])>=3:
        cls="STRONG"
    elif m["ratio"]>=0.60 and len(m["matched"])>=3:
        cls="PARTIAL"
    else:
        cls="WEAK"
    return {
      "classification":cls,
      **m,
      "useful_connection":cls!="WEAK",
      "limits":[{"pred":e.pred,"a":e.a,"b":e.b} for e in m["unmatched"]],
    }

def mutate_one_relation(target,base_to_target,rng):
    t=Domain(target.nodes[:],set(target.edges),dict(target.attrs))
    source_edge=rng.choice(sorted(base_to_target[0].edges))
    mapped=project(source_edge,base_to_target[1])
    t.edges.remove(mapped)
    replacements=[p for p in REL if p!=mapped.pred]
    t.edges.add(Edge(rng.choice(replacements),mapped.a,mapped.b))
    return t,source_edge

def surface_trap(base,rng):
    # Same number of nodes and deliberately matching-looking attributes,
    # but all predicates come from a disjoint vocabulary.
    nodes=["trap"+name(rng.randrange(1,2_000_000)) for _ in base.nodes]
    mp=dict(zip(base.nodes,nodes))
    negpred={p:"surface_only_"+p for p in REL}
    edges={Edge(negpred[e.pred],mp[e.a],mp[e.b]) for e in base.edges}
    attrs={mp[n]:"surface_"+n for n in base.nodes}
    return Domain(nodes,edges,attrs)

def mapped_edges(base,mp):
    return {project(e,mp) for e in base.edges}

def run(seed,cases=1000):
    rng=random.Random(seed)
    strong=partial=weak=deletion=0
    wrong_surface_ignored=0
    partial_limits=0
    examples={}
    for i in range(cases):
        base=connected_template(rng)
        target,true_mp=renamed(base,rng,"t",extra=rng.randint(0,2),wrong_surface=True)
        s=synthesize(base,target)
        strong += (
          s["classification"]=="STRONG"
          and mapped_edges(base,s["mapping"]).issubset(target.edges)
        )
        wrong_surface_ignored += s["classification"]=="STRONG"

        # Remove/change one true relational fact: analogy should become PARTIAL
        # and name the exact source relation as a limit.
        pt,changed=mutate_one_relation(target,(base,true_mp),rng)
        ps=synthesize(base,pt)
        partial += ps["classification"]=="PARTIAL"
        partial_limits += any(x["pred"]==changed.pred and x["a"]==changed.a and x["b"]==changed.b for x in ps["limits"])

        # Causal deletion of a true edge must also downgrade strong->partial.
        dt=Domain(target.nodes[:],set(target.edges),dict(target.attrs))
        removed=rng.choice(sorted(base.edges));dt.edges.remove(project(removed,true_mp))
        ds=synthesize(base,dt)
        deletion += ds["classification"]=="PARTIAL" and any(x["pred"]==removed.pred for x in ds["limits"])

        # Surface-similar but relation-incompatible target must be rejected.
        trap=surface_trap(base,rng)
        ws=synthesize(base,trap)
        weak += ws["classification"]=="WEAK" and not ws["useful_connection"]

        if i==0:
            examples={
              "strong":s,"partial":ps,"surface_trap":ws,
              "changed_relation":{"pred":changed.pred,"a":changed.a,"b":changed.b},
            }
    return {
      "seed":seed,"cases":cases,
      "strong_exact":strong/cases,
      "partial_detected":partial/cases,
      "partial_limit_exact":partial_limits/cases,
      "causal_deletion_downgrade":deletion/cases,
      "surface_trap_rejected":weak/cases,
      "surface_attributes_failed_to_hijack":wrong_surface_ignored/cases,
      "example":examples,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--cases",type=int,default=1000);ap.add_argument("--out",default="relational_synthesis_v0.json");a=ap.parse_args()
    runs=[run(int(x),a.cases) for x in a.seeds.split(",")]
    passed=all(
      r["strong_exact"]==1.0
      and r["partial_detected"]==1.0
      and r["partial_limit_exact"]==1.0
      and r["causal_deletion_downgrade"]==1.0
      and r["surface_trap_rejected"]==1.0
      and r["surface_attributes_failed_to_hijack"]==1.0
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2,default=lambda x:x.__dict__)
    print(json.dumps({
      "passed":passed,
      "summaries":[{
        k:v for k,v in r.items() if k not in ("example",)
      } for r in runs]
    },indent=2))
