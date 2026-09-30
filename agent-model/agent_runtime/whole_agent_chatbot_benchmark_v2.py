from __future__ import annotations

import argparse,json,re,tempfile,random
from pathlib import Path
from time import perf_counter
import torch
import torch.nn as nn

from .contracts import CapabilityContext,CapabilityOffer,CapabilityResult,CapabilityRole,PublicMessage
from .runtime import AgentRuntime
from .sqlite_memory import SQLiteAgentMemory
from .whole_agent_procedure_gate_v1 import LearnedProcedureLanguage,ProcedureCapability
from agent_cognition.math_word_grounding_gate_v1 import GroundedPercentLexicon,solve,fmt

COPY_VALUE=256
COPY_FACTORS=257
COPY_FINAL=258
EOS=259
BOS=260
VOCAB_OUT=260
VOCAB_IN=261
KINDS=("number","math","fail")
KID={k:i for i,k in enumerate(KINDS)}
SCAFFOLDS={
 "number":[COPY_VALUE,EOS],
 "math":[*b"Original price: $",COPY_VALUE,*b". Check: $",COPY_VALUE,*b" x ",COPY_FACTORS,*b" = $",COPY_FINAL,ord("."),EOS],
 "fail":[*b"I didn't understand that.",EOS],
}

class MathCapability:
    name="grounded-percent-math"
    role=CapabilityRole.CONTRIBUTOR
    contract_version="0.1"
    def __init__(self,lex):self.lex=lex
    def _solve(self,text):return solve(text,self.lex)
    def offer(self,context):
        got=self._solve(context.user_text)
        if got is None:return None
        return CapabilityOffer(capability=self.name,relevance=1.0,estimated_cost=0.01,confidence=1.0,tags=("math","symbolic"))
    def run(self,context):
        started=perf_counter();got=self._solve(context.user_text)
        if got is None:
            state={"kind":"fail"}
        else:
            steps,final,factor_total,original=got
            state={
              "kind":"math",
              "value":fmt(original),
              "factors":" x ".join(fmt(s["factor"]) for s in steps),
              "final":fmt(final),
            }
        return CapabilityResult(
          messages=(PublicMessage(kind="response_state",content=state,source=self.name,confidence=1.0),),
          measured_cost=perf_counter()-started,
        )

class Producer(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb=nn.Embedding(VOCAB_IN,32)
        self.kind=nn.Embedding(len(KINDS),40)
        self.init=nn.Linear(40,64)
        self.gru=nn.GRU(32,64,batch_first=True)
        self.out=nn.Linear(64,VOCAB_OUT)

def train_producer(seed,steps=450):
    random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(2)
    m=Producer();opt=torch.optim.AdamW(m.parameters(),lr=8e-3)
    L=max(len(v) for v in SCAFFOLDS.values())
    kinds=[];prev=[];targ=[]
    for k in KINDS:
        t=list(SCAFFOLDS[k]);p=[BOS]+t[:-1];pad=L-len(t)
        kinds.append(KID[k]);prev.append(p+[BOS]*pad);targ.append(t+[-100]*pad)
    kinds=torch.tensor(kinds);prev=torch.tensor(prev);targ=torch.tensor(targ)
    for _ in range(steps):
        h0=torch.tanh(m.init(m.kind(kinds))).unsqueeze(0)
        h,_=m.gru(m.emb(prev),h0);logits=m.out(h)
        loss=nn.functional.cross_entropy(logits.reshape(-1,VOCAB_OUT),targ.reshape(-1),ignore_index=-100)
        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(m.parameters(),1);opt.step()
    return m.eval()

@torch.no_grad()
def gen(m,kind):
    kid=torch.tensor([KID[kind]])
    hidden=torch.tanh(m.init(m.kind(kid))).unsqueeze(0)
    tok=torch.tensor([[BOS]]);out=[]
    for _ in range(128):
        h,hidden=m.gru(m.emb(tok),hidden);n=int(m.out(h[:,-1]).argmax(-1))
        out.append(n)
        if n==EOS:break
        tok=torch.tensor([[n]])
    return out

def render(tokens,state):
    b=bytearray()
    for t in tokens:
        if t<256:b.append(t)
        elif t==COPY_VALUE:b.extend(str(state.get("value","")).encode())
        elif t==COPY_FACTORS:b.extend(str(state.get("factors","")).encode())
        elif t==COPY_FINAL:b.extend(str(state.get("final","")).encode())
        elif t==EOS:break
    return b.decode()

class Composer:
    name="homegrown-hybrid-composer-v2"
    role=CapabilityRole.COMPOSER
    contract_version="0.2"
    def __init__(self,m):self.m=m
    def offer(self,context):return None
    def run(self,context):
        states=[x.content for x in context.contributions if x.kind=="response_state" and isinstance(x.content,dict)]
        chosen=None
        for s in states:
            if s.get("kind")!="fail":chosen=s
        if chosen is None:chosen=states[-1] if states else {"kind":"fail"}
        kind=str(chosen.get("kind","fail"))
        if kind not in KID:kind="fail"
        text=render(gen(self.m,kind),chosen)
        return CapabilityResult(
          messages=(PublicMessage(kind="assistant_text",content=text,source=self.name,metadata={"response_kind":kind}),),
          measured_cost=0.0,
        )

def checks(text,cs):
    if not cs:return None
    res=[]
    for c in cs:
        if c["type"]=="regex":res.append(bool(re.search(c["pattern"],text)))
        elif c["type"]=="contains_all":
            low=text.casefold();res.append(all(str(v).casefold() in low for v in c["values"]))
        else:raise ValueError(c["type"])
    return all(res)

def load_bench():
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:return json.load(f)

def run_seed(seed):
    procedure_lang=LearnedProcedureLanguage().develop(seed+100)
    percent_lex=GroundedPercentLexicon().develop(seed+300)
    producer=train_producer(seed+500)
    bench=load_bench();rows=[]
    with tempfile.TemporaryDirectory() as td:
        rts={};mems={}
        for t in bench["turns"]:
            th=str(t["thread"])
            if th not in rts:
                mem=SQLiteAgentMemory(Path(td)/(th+".sqlite"))
                rts[th]=AgentRuntime(
                  composer=Composer(producer),
                  contributors=(ProcedureCapability(procedure_lang),MathCapability(percent_lex)),
                  memory=mem,
                );mems[th]=mem
            response,trace=rts[th].turn(t["prompt"])
            kind=str(trace.response_metadata.get("response_kind",""))
            rows.append({
              "id":t["id"],"response":response,"response_kind":kind,
              "perception_success":kind!="fail",
              "automatic_pass":checks(response,t.get("checks",[])),
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
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="whole_agent_chatbot_v2.json");a=ap.parse_args()
    runs=[run_seed(int(x)) for x in a.seeds.split(",")]
    out={"benchmark":"chatbot-v0","runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps({"summaries":[{
      "seed":r["seed"],"perception":f"{r['perception_successes']}/{r['turns_total']}",
      "automatic":f"{r['automatic_passes']}/{r['automatic_total']}",
      "passing":[x["id"] for x in r["rows"] if x["automatic_pass"] is True],
      "math_response":next((x["response"] for x in r["rows"] if x["id"]=="math_01"),None)
    } for r in runs]},indent=2))
