from __future__ import annotations

import argparse, json, re, tempfile
from pathlib import Path

from .runtime import AgentRuntime
from .sqlite_memory import SQLiteAgentMemory
from .whole_agent_procedure_gate_v1 import (
    LearnedProcedureLanguage, ProcedureCapability, NumberComposer, train_producer
)

def score_checks(text,checks):
    if not checks:return None
    out=[]
    for c in checks:
        if c["type"]=="regex":out.append(bool(re.search(c["pattern"],text)))
        elif c["type"]=="contains_all":
            low=text.casefold();out.append(all(str(v).casefold() in low for v in c["values"]))
        else:raise ValueError(c["type"])
    return all(out)

def load_bench():
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:return json.load(f)

def run_seed(seed):
    bench=load_bench()
    lang=LearnedProcedureLanguage().develop(seed+100)
    producer=train_producer(seed+200)
    rows=[]
    with tempfile.TemporaryDirectory() as td:
        runtimes={};mems={}
        for t in bench["turns"]:
            thread=str(t["thread"])
            if thread not in runtimes:
                mem=SQLiteAgentMemory(Path(td)/f"{thread}.sqlite")
                rt=AgentRuntime(
                    composer=NumberComposer(producer),
                    contributors=(ProcedureCapability(lang),),
                    memory=mem,
                )
                runtimes[thread]=rt;mems[thread]=mem
            response,trace=runtimes[thread].turn(t["prompt"])
            kind=str(trace.response_metadata.get("response_kind",""))
            rows.append({
                "id":t["id"],"category":t["category"],"response":response,
                "response_kind":kind,"perception_success":kind!="fail",
                "automatic_pass":score_checks(response,t.get("checks",[])),
            })
        for m in mems.values():m.close()
    auto=[r for r in rows if r["automatic_pass"] is not None]
    return {
        "seed":seed,"rows":rows,
        "perception_successes":sum(r["perception_success"] for r in rows),
        "turns_total":len(rows),
        "automatic_passes":sum(bool(r["automatic_pass"]) for r in auto),
        "automatic_total":len(auto),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="whole_agent_chatbot_v1.json");a=ap.parse_args()
    runs=[run_seed(int(x)) for x in a.seeds.split(",")]
    out={"benchmark":"chatbot-v0","runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps({"summaries":[{
        "seed":r["seed"],"perception":f"{r['perception_successes']}/{r['turns_total']}",
        "automatic":f"{r['automatic_passes']}/{r['automatic_total']}",
        "passing":[x["id"] for x in r["rows"] if x["automatic_pass"] is True]
    } for r in runs]},indent=2))
