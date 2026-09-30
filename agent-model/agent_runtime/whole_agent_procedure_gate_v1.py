from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import re
import tempfile
from time import perf_counter

import torch
import torch.nn as nn

from .contracts import CapabilityContext, CapabilityOffer, CapabilityResult, CapabilityRole, PublicMessage
from .runtime import AgentRuntime
from .sqlite_memory import SQLiteAgentMemory

OPS = {
    "DOUBLE": lambda x: x * 2,
    "ADD3": lambda x: x + 3,
    "SQUARE": lambda x: x * x,
    "SUB9": lambda x: x - 9,
}
PHRASE_SURFACES = {
    "DOUBLE": ("double it", "double the number", "multiply it by two"),
    "ADD3": ("add 3", "add three", "increase it by three"),
    "SQUARE": ("square the result", "square it", "multiply it by itself"),
    "SUB9": ("subtract 9", "subtract nine", "decrease it by nine"),
}
PROBE_DOMAIN = tuple(range(-8, 9))

COPY_VALUE=256
EOS=257
BOS=258
VOCAB_OUT=258
VOCAB_IN=259
KINDS=("number","fail")
KID={k:i for i,k in enumerate(KINDS)}
SCAFFOLDS={
    "number":[COPY_VALUE,EOS],
    "fail":[*b"I didn't understand that.",EOS],
}

def execute(program,x):
    for op in program:x=OPS[op](x)
    return x

def candidates_for(pairs):
    out=set()
    for op in OPS:
        if all(OPS[op](x)==y for x,y in pairs):out.add(op)
    return out

def best_probe(cands,used):
    best=None
    for x in PROBE_DOMAIN:
        if x in used:continue
        outs={}
        for op in cands:outs.setdefault(OPS[op](x),0);outs[OPS[op](x)]+=1
        if len(outs)<=1:continue
        largest=max(outs.values())
        score=(len(outs),-largest,-abs(x))
        if best is None or score>best[0]:best=(score,x)
    return None if best is None else best[1]

class LearnedProcedureLanguage:
    def __init__(self):
        self.surface_to_op={}
        self.evidence={}
        self.active_probes=0

    def ground_phrase(self,surface,hidden_op,initial_x):
        pairs=[(initial_x,OPS[hidden_op](initial_x))]
        cands=candidates_for(pairs)
        while len(cands)>1:
            x=best_probe(cands,{a for a,_ in pairs})
            if x is None:break
            self.active_probes+=1
            pairs.append((x,OPS[hidden_op](x)))
            cands=candidates_for(pairs)
        if len(cands)==1:self.surface_to_op[surface]=next(iter(cands))
        self.evidence[surface]=pairs

    def develop(self,seed):
        rng=random.Random(seed)
        for hidden_op,surfaces in PHRASE_SURFACES.items():
            for surface in surfaces:
                self.ground_phrase(surface,hidden_op,rng.choice(PROBE_DOMAIN))
        return self

    def extract_program(self,text):
        low=text.casefold()
        hits=[]
        for surface,op in self.surface_to_op.items():
            start=low.find(surface)
            if start>=0:hits.append((start,-len(surface),surface,op))
        hits.sort()
        chosen=[];end=-1
        for start,neglen,surface,op in hits:
            stop=start+len(surface)
            if start>=end:
                chosen.append((start,op,surface));end=stop
        return tuple(x[1] for x in chosen)

    @staticmethod
    def extract_n(text):
        m=re.search(r"\bn\s*=\s*(-?\d+)\b",text,re.I)
        return None if m is None else int(m.group(1))

class ProcedureCapability:
    name="learned-procedure"
    role=CapabilityRole.CONTRIBUTOR
    contract_version="0.1"

    def __init__(self,lang):
        self.lang=lang

    def offer(self,context):
        program=self.lang.extract_program(context.user_text)
        n=self.lang.extract_n(context.user_text)
        low=context.user_text.casefold()
        if len(program)>=2 and n is not None:
            return CapabilityOffer(capability=self.name,relevance=1.0,estimated_cost=0.01,confidence=1.0,tags=("procedure","grounded"))
        if "same transformation" in low and n is not None:
            return CapabilityOffer(capability=self.name,relevance=1.0,estimated_cost=0.01,confidence=1.0,tags=("procedure","reuse"))
        return None

    def run(self,context):
        started=perf_counter()
        text=context.user_text
        program=self.lang.extract_program(text)
        n=self.lang.extract_n(text)
        updates={}
        if len(program)>=2:
            updates["procedure::current"]=list(program)
        elif "same transformation" in text.casefold():
            stored=context.semantic_memory.get("procedure::current")
            program=tuple(stored) if isinstance(stored,list) else ()
        if n is None or not program:
            state={"kind":"fail","value":""}
        else:
            state={"kind":"number","value":str(execute(program,n))}
        return CapabilityResult(
            messages=(PublicMessage(kind="response_state",content=state,source=self.name,confidence=1.0),),
            semantic_updates=updates,
            active_state_updates={"last_procedure_length":len(program)},
            measured_cost=perf_counter()-started,
        )

class NumberProducer(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb=nn.Embedding(VOCAB_IN,24)
        self.kind=nn.Embedding(len(KINDS),32)
        self.init=nn.Linear(32,48)
        self.gru=nn.GRU(24,48,batch_first=True)
        self.out=nn.Linear(48,VOCAB_OUT)

def train_producer(seed,steps=350):
    random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(2)
    m=NumberProducer();opt=torch.optim.AdamW(m.parameters(),lr=1e-2)
    maxlen=max(len(v) for v in SCAFFOLDS.values())
    kinds=[];prev=[];targ=[]
    for k in KINDS:
        t=SCAFFOLDS[k];p=[BOS]+t[:-1];pad=maxlen-len(t)
        kinds.append(KID[k]);prev.append(p+[BOS]*pad);targ.append(t+[-100]*pad)
    kinds=torch.tensor(kinds);prev=torch.tensor(prev);targ=torch.tensor(targ)
    for _ in range(steps):
        h0=torch.tanh(m.init(m.kind(kinds))).unsqueeze(0)
        h,_=m.gru(m.emb(prev),h0);logits=m.out(h)
        loss=nn.functional.cross_entropy(logits.reshape(-1,VOCAB_OUT),targ.reshape(-1),ignore_index=-100)
        opt.zero_grad();loss.backward();opt.step()
    return m.eval()

@torch.no_grad()
def gen(model,kind):
    kid=torch.tensor([KID[kind]])
    hidden=torch.tanh(model.init(model.kind(kid))).unsqueeze(0)
    tok=torch.tensor([[BOS]]);out=[]
    for _ in range(64):
        h,hidden=model.gru(model.emb(tok),hidden);nxt=int(model.out(h[:,-1]).argmax(-1))
        out.append(nxt)
        if nxt==EOS:break
        tok=torch.tensor([[nxt]])
    return out

def render(tokens,value):
    b=bytearray()
    for t in tokens:
        if t<256:b.append(t)
        elif t==COPY_VALUE:b.extend(str(value).encode())
        elif t==EOS:break
    return b.decode()

class NumberComposer:
    name="homegrown-number-composer"
    role=CapabilityRole.COMPOSER
    contract_version="0.1"
    def __init__(self,model):self.model=model
    def offer(self,context):return None
    def run(self,context):
        states=[m.content for m in context.contributions if m.kind=="response_state" and isinstance(m.content,dict)]
        state=states[-1] if states else {"kind":"fail","value":""}
        kind=state.get("kind","fail")
        if kind not in KID:kind="fail"
        text=render(gen(self.model,kind),state.get("value",""))
        return CapabilityResult(
            messages=(PublicMessage(kind="assistant_text",content=text,source=self.name,metadata={"response_kind":kind}),),
            measured_cost=0.0,
        )

def score_regex(text,pattern):
    return bool(re.search(pattern,text))

def benchmark_turns():
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:bench=json.load(f)
    return [x for x in bench["turns"] if x["id"].startswith("compression_")]

def run_seed(seed):
    lang=LearnedProcedureLanguage().develop(seed+100)
    learned_ok=len(lang.surface_to_op)==sum(len(v) for v in PHRASE_SURFACES.values())
    model=train_producer(seed+200)
    turns=benchmark_turns();rows=[]
    with tempfile.TemporaryDirectory() as td:
        mem=SQLiteAgentMemory(Path(td)/"agent.sqlite")
        rt=AgentRuntime(composer=NumberComposer(model),contributors=(ProcedureCapability(lang),),memory=mem)
        for t in turns:
            response,trace=rt.turn(t["prompt"])
            check=t["checks"][0]
            passed=score_regex(response,check["pattern"])
            rows.append({"id":t["id"],"prompt":t["prompt"],"response":response,"passed":passed,"trace":trace.to_dict()})
        stored=mem.semantic.get("procedure::current")
        mem.close()
    return {
        "seed":seed,
        "learned_phrase_count":len(lang.surface_to_op),
        "expected_phrase_count":sum(len(v) for v in PHRASE_SURFACES.values()),
        "active_grounding_probes":lang.active_probes,
        "development_passed":learned_ok,
        "stored_program":stored,
        "benchmark_passes":sum(r["passed"] for r in rows),
        "benchmark_total":len(rows),
        "rows":rows,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="whole_agent_procedure_v1.json");a=ap.parse_args()
    runs=[run_seed(int(x)) for x in a.seeds.split(",")]
    out={"passed":all(r["development_passed"] and r["benchmark_passes"]==r["benchmark_total"] for r in runs),"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps({"passed":out["passed"],"summaries":[{
        "seed":r["seed"],"phrases":f"{r['learned_phrase_count']}/{r['expected_phrase_count']}",
        "active_probes":r["active_grounding_probes"],"program":r["stored_program"],
        "benchmark":f"{r['benchmark_passes']}/{r['benchmark_total']}",
        "responses":[x["response"] for x in r["rows"]],
    } for r in runs]},indent=2))
