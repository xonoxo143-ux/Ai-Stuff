from __future__ import annotations
import argparse,json,random
import relational_synthesis_gate_v1 as g

def edge(e): return {"pred":e.pred,"a":e.a,"b":e.b}
def dom(d): return {"nodes":d.nodes,"edges":[edge(e) for e in sorted(d.edges)],"attrs":d.attrs}

def run(seed,cases):
    rng=random.Random(seed); bad=[]
    for i in range(cases):
        base=g.connected_template(rng)
        target,true_mp=g.renamed(base,rng,"t",extra=rng.randint(0,2),wrong_surface=True)
        g.synthesize(base,target)

        pt,changed=g.mutate_one_relation(target,base,true_mp,rng)
        ps=g.synthesize(base,pt)
        if not g.has_limit(ps["certain_limits"],changed) and not ps["ambiguous_alignment"]:
            bad.append({"kind":"change","case":i,"intervention":edge(changed),
              "base":dom(base),"target":dom(pt),"true_mapping":true_mp,"synthesis":ps})

        dt=g.Domain(target.nodes[:],set(target.edges),dict(target.attrs))
        removed=rng.choice(sorted(base.edges)); dt.edges.remove(g.project(removed,true_mp))
        ds=g.synthesize(base,dt)
        if not g.has_limit(ds["certain_limits"],removed) and not ds["ambiguous_alignment"]:
            bad.append({"kind":"delete","case":i,"intervention":edge(removed),
              "base":dom(base),"target":dom(dt),"true_mapping":true_mp,"synthesis":ds})
        g.synthesize(base,g.surface_trap(base,rng))
    return {"seed":seed,"cases":cases,"flagged":len(bad),"counterexamples":bad}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--seeds",default="0,1,2");p.add_argument("--cases",type=int,default=3000);p.add_argument("--out",default="relational_synthesis_counterexamples_v1.json");a=p.parse_args()
    out={"diagnostic_version":"counterexample-v1","runs":[run(int(s),a.cases) for s in a.seeds.split(",")]}
    with open(a.out,"w") as f: json.dump(out,f,indent=2)
    print(json.dumps({"out":a.out,"counts":[{"seed":r["seed"],"flagged":r["flagged"]} for r in out["runs"]]},indent=2))
