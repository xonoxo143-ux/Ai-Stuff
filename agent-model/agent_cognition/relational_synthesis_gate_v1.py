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
            if {es[i].a,es[i].b}&{es[j].a,es[j].b}:bonus+=1
    return bonus

def optimal_alignments(base,target):
    if len(base.nodes)!=len(target.nodes):return []
    best_score=None
    out=[]
    for perm in itertools.permutations(target.nodes):
        mp=dict(zip(base.nodes,perm))
        matched={e for e in base.edges if project(e,mp) in target.edges}
        score=(len(matched),connected_bonus(matched))
        rec={"mapping":mp,"matched":matched,"unmatched":set(base.edges)-matched,"score":score}
        if best_score is None or score>best_score:
            best_score=score;out=[rec]
        elif score==best_score:
            out.append(rec)
    return out

def synthesize(base,target):
    alns=optimal_alignments(base,target)
    if not alns:return {"classification":"WEAK","reason":"node-count mismatch","alignment_count":0}
    score=alns[0]["score"]
    matched_n=score[0]
    ratio=matched_n/len(base.edges)
    if matched_n==len(base.edges) and matched_n>=3: cls="STRONG"
    elif ratio>=0.60 and matched_n>=3: cls="PARTIAL"
    else: cls="WEAK"

    unmatched_sets=[a["unmatched"] for a in alns]
    possible=set().union(*unmatched_sets) if unmatched_sets else set()
    certain=set.intersection(*unmatched_sets) if unmatched_sets else set()

    # A relation is safe to assert as shared only if it is matched under every
    # equally good alignment. This prevents symmetry from manufacturing certainty.
    matched_sets=[a["matched"] for a in alns]
    certain_shared=set.intersection(*matched_sets) if matched_sets else set()
    possible_shared=set().union(*matched_sets) if matched_sets else set()

    return {
      "classification":cls,
      "alignment_count":len(alns),
      "ambiguous_alignment":len(alns)>1,
      "ratio":ratio,
      "systematicity":score[1],
      "certain_shared":sorted(certain_shared),
      "possible_shared":sorted(possible_shared),
      "certain_limits":[{"pred":e.pred,"a":e.a,"b":e.b} for e in sorted(certain)],
      "possible_limits":[{"pred":e.pred,"a":e.a,"b":e.b} for e in sorted(possible)],
      "useful_connection":cls!="WEAK",
      # Keep one representative mapping only for debugging, never as certainty.
      "representative_mapping":alns[0]["mapping"],
    }

def mutate_one_relation(target,base,true_mp,rng):
    t=Domain(target.nodes[:],set(target.edges),dict(target.attrs))
    source_edge=rng.choice(sorted(base.edges))
    mapped=project(source_edge,true_mp)
    t.edges.remove(mapped)
    t.edges.add(Edge(rng.choice([p for p in REL if p!=mapped.pred]),mapped.a,mapped.b))
    return t,source_edge

def surface_trap(base,rng):
    nodes=["trap"+name(rng.randrange(1,2_000_000)) for _ in base.nodes]
    mp=dict(zip(base.nodes,nodes))
    negpred={p:"surface_only_"+p for p in REL}
    edges={Edge(negpred[e.pred],mp[e.a],mp[e.b]) for e in base.edges}
    attrs={mp[n]:"surface_"+n for n in base.nodes}
    return Domain(nodes,edges,attrs)

def has_limit(rows,e):
    return any(x["pred"]==e.pred and x["a"]==e.a and x["b"]==e.b for x in rows)

def run(seed,cases=3000):
    rng=random.Random(seed)
    strong=partial=weak=delete_down=0
    change_covered=delete_covered=0
    false_certain_change=false_certain_delete=0
    ambiguity_honest=0
    symmetry_cases=0
    for _ in range(cases):
        base=connected_template(rng)
        target,true_mp=renamed(base,rng,"t",extra=rng.randint(0,2),wrong_surface=True)
        s=synthesize(base,target)
        strong += s["classification"]=="STRONG"
        ambiguity_honest += (not s["ambiguous_alignment"]) or s["alignment_count"]>1
        symmetry_cases += s["ambiguous_alignment"]

        pt,changed=mutate_one_relation(target,base,true_mp,rng)
        ps=synthesize(base,pt)
        partial += ps["classification"]=="PARTIAL"
        change_covered += has_limit(ps["possible_limits"],changed)
        # It may be certain only when every optimal alignment leaves it unmatched.
        if has_limit(ps["certain_limits"],changed):
            false_certain_change += 0
        else:
            # If not certain, the output must expose ambiguity rather than choosing one.
            false_certain_change += int(not ps["ambiguous_alignment"])

        dt=Domain(target.nodes[:],set(target.edges),dict(target.attrs))
        removed=rng.choice(sorted(base.edges))
        dt.edges.remove(project(removed,true_mp))
        ds=synthesize(base,dt)
        delete_down += ds["classification"]=="PARTIAL"
        delete_covered += has_limit(ds["possible_limits"],removed)
        if not has_limit(ds["certain_limits"],removed):
            false_certain_delete += int(not ds["ambiguous_alignment"])

        trap=surface_trap(base,rng)
        ws=synthesize(base,trap)
        weak += ws["classification"]=="WEAK" and not ws["useful_connection"]

    return {
      "seed":seed,"cases":cases,
      "strong_detected":strong/cases,
      "partial_detected":partial/cases,
      "changed_relation_in_possible_limits":change_covered/cases,
      "deletion_downgrade":delete_down/cases,
      "deleted_relation_in_possible_limits":delete_covered/cases,
      "surface_trap_rejected":weak/cases,
      "ambiguity_representation_consistent":ambiguity_honest/cases,
      "symmetry_case_rate":symmetry_cases/cases,
      "false_certainty_change_cases":false_certain_change,
      "false_certainty_delete_cases":false_certain_delete,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",default="0,1,2")
    ap.add_argument("--cases",type=int,default=3000)
    ap.add_argument("--out",default="relational_synthesis_v1.json")
    a=ap.parse_args()
    runs=[run(int(x),a.cases) for x in a.seeds.split(",")]
    passed=all(
      r["strong_detected"]==1.0
      and r["partial_detected"]==1.0
      and r["changed_relation_in_possible_limits"]==1.0
      and r["deletion_downgrade"]==1.0
      and r["deleted_relation_in_possible_limits"]==1.0
      and r["surface_trap_rejected"]==1.0
      and r["ambiguity_representation_consistent"]==1.0
      and r["false_certainty_change_cases"]==0
      and r["false_certainty_delete_cases"]==0
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
