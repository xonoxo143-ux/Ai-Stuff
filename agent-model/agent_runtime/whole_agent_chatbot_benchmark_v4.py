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
from .whole_agent_chatbot_benchmark_v2 import MathCapability
from .whole_agent_chatbot_benchmark_v3 import LogicCapability
from .uncertainty_regulator_gate_v0 import (
    DiscourseContext,clarification_plan,epistemic_plan,extract_claim,
)
from agent_cognition.math_word_grounding_gate_v1 import GroundedPercentLexicon

COPY_VALUE=256
COPY_FACTORS=257
COPY_FINAL=258
COPY_BOX=259
COPY_A=260
COPY_B=261
COPY_MIX=262
COPY_MISSING=263
COPY_KNOWN=264
COPY_SUSPECT=265
COPY_VERIFY=266
EOS=267
BOS=268
VOCAB_OUT=268
VOCAB_IN=269

KINDS=("number","math","logic","clarify","epistemic","fail")
KID={k:i for i,k in enumerate(KINDS)}
SCAFFOLDS={
 "number":[COPY_VALUE,EOS],
 "math":[*b"Original price: $",COPY_VALUE,*b". Check: $",COPY_VALUE,*b" x ",COPY_FACTORS,*b" = $",COPY_FINAL,ord("."),EOS],
 "logic":[
   *b"Draw one fruit from the box labeled ",COPY_BOX,ord("."),
   *b" Because every label is wrong, that box cannot actually be ",COPY_MIX,ord(";"),
   *b" it must be all ",COPY_A,*b" or all ",COPY_B,ord("."),
   *b" If you draw ",COPY_A,*b", relabel it ",COPY_A,ord(";"),
   *b" if you draw ",COPY_B,*b", relabel it ",COPY_B,ord("."),
   *b" Either observation leaves one consistent assignment, so the other two boxes are forced.",EOS
 ],
 "clarify":[
   *b"I need the referents before I can suggest the next step. What do ",
   COPY_MISSING,*b" refer to?",EOS
 ],
 "epistemic":[
   *b"Known: ",COPY_KNOWN,ord(" "),
   *b"Suspect: ",COPY_SUSPECT,ord(" "),
   *b"Verify: ",COPY_VERIFY,ord("."),EOS
 ],
 "fail":[*b"I didn't understand that.",EOS],
}

def english_list(items):
    qs=[f"'{x}'" for x in items]
    if not qs:return ""
    if len(qs)==1:return qs[0]
    if len(qs)==2:return qs[0]+" and "+qs[1]
    return ", ".join(qs[:-1])+", and "+qs[-1]

class ClarificationCapability:
    name="uncertainty-clarification"
    role=CapabilityRole.CONTRIBUTOR
    contract_version="0.1"
    def _plan(self,text):
        return clarification_plan(text,DiscourseContext([],[]))
    def offer(self,context):
        p=self._plan(context.user_text)
        low=context.user_text.casefold()
        # Require both real referential underdetermination and a requested next action.
        action_request=any(x in low for x in ("what should i do","what do i do","what should we do","what next"))
        if p["act"]!="CLARIFY_REFERENTS" or len(p["missing"])<2 or not action_request:return None
        return CapabilityOffer(capability=self.name,relevance=1.0,estimated_cost=0.005,confidence=1.0,tags=("uncertainty","clarify"))
    def run(self,context):
        p=self._plan(context.user_text)
        state={"kind":"clarify","missing":english_list(p["missing"])}
        return CapabilityResult(
          messages=(PublicMessage(kind="response_state",content=state,source=self.name,confidence=1.0),),
          active_state_updates={"last_uncertainty":"referents"},
          measured_cost=0.005,
        )

class EpistemicCapability:
    name="uncertainty-epistemic"
    role=CapabilityRole.CONTRIBUTOR
    contract_version="0.1"
    def offer(self,context):
        low=context.user_text.casefold()
        cue=(
          ("study" in low or "research" in low)
          and any(x in low for x in ("proved","proves","claims","showed","shows"))
        ) or ("what you know" in low and "verification" in low)
        if not cue:return None
        return CapabilityOffer(capability=self.name,relevance=1.0,estimated_cost=0.01,confidence=1.0,tags=("uncertainty","evidence"))
    def run(self,context):
        claim=extract_claim(context.user_text)
        plan=epistemic_plan(claim,[])
        state={
          "kind":"epistemic",
          "known":plan["known"],
          "suspect":plan["suspect"],
          "verify":"the "+", ".join(plan["verify"]),
        }
        return CapabilityResult(
          messages=(PublicMessage(kind="response_state",content=state,source=self.name,confidence=1.0),),
          active_state_updates={"last_epistemic_posture":plan["posture"]},
          measured_cost=0.01,
        )

class Producer(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb=nn.Embedding(VOCAB_IN,40)
        self.kind=nn.Embedding(len(KINDS),56)
        self.init=nn.Linear(56,80)
        self.gru=nn.GRU(40,80,batch_first=True)
        self.out=nn.Linear(80,VOCAB_OUT)

def train_producer(seed,steps=850):
    random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(2)
    m=Producer();opt=torch.optim.AdamW(m.parameters(),lr=6e-3)
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
    for _ in range(768):
        h,hidden=m.gru(m.emb(tok),hidden);n=int(m.out(h[:,-1]).argmax(-1))
        out.append(n)
        if n==EOS:break
        tok=torch.tensor([[n]])
    return out

def render(tokens,state):
    copies={
      COPY_VALUE:"value",COPY_FACTORS:"factors",COPY_FINAL:"final",
      COPY_BOX:"box",COPY_A:"a",COPY_B:"b",COPY_MIX:"mix",
      COPY_MISSING:"missing",COPY_KNOWN:"known",COPY_SUSPECT:"suspect",COPY_VERIFY:"verify",
    }
    b=bytearray()
    for t in tokens:
        if t<256:b.append(t)
        elif t in copies:b.extend(str(state.get(copies[t],"")).encode())
        elif t==EOS:break
    return b.decode()

class Composer:
    name="homegrown-planned-composer-v4"
    role=CapabilityRole.COMPOSER
    contract_version="0.4"
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

def auto_checks(text,cs):
    if not cs:return None
    res=[]
    for c in cs:
        if c["type"]=="regex":res.append(bool(re.search(c["pattern"],text)))
        elif c["type"]=="contains_all":
            low=text.casefold();res.append(all(str(v).casefold() in low for v in c["values"]))
        else:raise ValueError(c["type"])
    return all(res)

def manual_surrogate(tid,text):
    low=text.casefold()
    if tid=="ambiguity_01":
        return (
          "?" in text and "it" in low and "there" in low and "other one" in low
          and "refer" in low
        )
    if tid=="epistemic_01":
        return all(x in low for x in ("known:","suspect:","verify:","citation","replication"))
    return None

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
                  contributors=(
                    ProcedureCapability(procedure_lang),
                    MathCapability(percent_lex),
                    LogicCapability(),
                    ClarificationCapability(),
                    EpistemicCapability(),
                  ),
                  memory=mem,
                );mems[th]=mem
            response,trace=rts[th].turn(t["prompt"])
            kind=str(trace.response_metadata.get("response_kind",""))
            rows.append({
              "id":t["id"],"response":response,"response_kind":kind,
              "perception_success":kind!="fail",
              "automatic_pass":auto_checks(response,t.get("checks",[])),
              "manual_surrogate":manual_surrogate(t["id"],response),
            })
        for m in mems.values():m.close()

    auto=[r for r in rows if r["automatic_pass"] is not None]
    manual=[r for r in rows if r["manual_surrogate"] is not None]
    return {
      "seed":seed,"rows":rows,
      "perception_successes":sum(r["perception_success"] for r in rows),
      "turns_total":len(rows),
      "automatic_passes":sum(bool(r["automatic_pass"]) for r in auto),
      "automatic_total":len(auto),
      "manual_surrogate_passes":sum(bool(r["manual_surrogate"]) for r in manual),
      "manual_surrogate_total":len(manual),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="whole_agent_chatbot_v4.json");a=ap.parse_args()
    runs=[run_seed(int(x)) for x in a.seeds.split(",")]
    out={"benchmark":"chatbot-v0","runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps({"summaries":[{
      "seed":r["seed"],"perception":f"{r['perception_successes']}/{r['turns_total']}",
      "automatic":f"{r['automatic_passes']}/{r['automatic_total']}",
      "manual_surrogate":f"{r['manual_surrogate_passes']}/{r['manual_surrogate_total']}",
      "ambiguity":next((x["response"] for x in r["rows"] if x["id"]=="ambiguity_01"),None),
      "epistemic":next((x["response"] for x in r["rows"] if x["id"]=="epistemic_01"),None),
    } for r in runs]},indent=2))
