from __future__ import annotations
import argparse,json,random,re
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict,Counter

ENTER="ENTER_ROLE"
EXIT="EXIT_ROLE"
RESUME="RESUME_ROLE"
ANALYZE="ANALYTIC"

GROUNDING=[
 ("Roleplay as Iris, a cautious medic. I arrive with a cracked compass.",ENTER),
 ("Roleplay as Toma, a skeptical pilot. A sealed chart is on the table.",ENTER),
 ("Roleplay as Quinn, a patient engineer. The alarm has just stopped.",ENTER),
 ("Switch out of roleplay. Explain the mechanism.",EXIT),
 ("Out of roleplay. Compare the two ideas.",EXIT),
 ("Leave the roleplay for now and analyze the claim.",EXIT),
 ("Back to Iris. Continue from the compass.",RESUME),
 ("Back to Toma. Pick up where the chart scene stopped.",RESUME),
 ("Resume Quinn and continue the scene.",RESUME),
 ("Compare the themes in these two novels.",ANALYZE),
 ("Take this philosophical claim seriously and challenge it.",ANALYZE),
 ("Explain the connection between these arguments.",ANALYZE),
]

def toks(text):
    return re.findall(r"[a-z]+",text.casefold())

def ngrams(tokens,max_n=4):
    out=set()
    for n in range(1,min(max_n,len(tokens))+1):
        for i in range(len(tokens)-n+1):
            out.add(tuple(tokens[i:i+n]))
    return out

class DialogueConstructionLexicon:
    def __init__(self):
        self.rules=[]

    def fit(self,rows):
        votes=defaultdict(Counter)
        for text,op in rows:
            for ng in ngrams(toks(text)):
                votes[ng][op]+=1
        rules=[]
        for ng,c in votes.items():
            op,support=c.most_common(1)[0]
            total=sum(c.values())
            # Grounded at least twice, perfectly operation-specific.
            if support>=2 and support==total:
                rules.append((ng,op,support))
        # Long constructions are more diagnostic; support breaks ties.
        self.rules=sorted(rules,key=lambda x:(-len(x[0]),-x[2],x[0]))
        return self

    def predict(self,text):
        ts=toks(text)
        s=" ".join(ts)
        hits=[]
        for ng,op,support in self.rules:
            phrase=" ".join(ng)
            # token-boundary match
            if re.search(r"(?:^| )"+re.escape(phrase)+r"(?: |$)",s):
                hits.append((len(ng),support,op,ng))
        if not hits:return ANALYZE,()
        # A control operation beats generic analytic evidence when equally specific.
        priority={ENTER:3,RESUME:3,EXIT:3,ANALYZE:1}
        best=max(hits,key=lambda h:(h[0],h[1],priority[h[2]]))
        return best[2],best[3]

PERSONA_RE=re.compile(r"(?:roleplay as|back to|resume)\s+([A-Z][A-Za-z0-9_-]*)",re.I)

def persona_from(text):
    m=PERSONA_RE.search(text)
    return None if m is None else m.group(1)

@dataclass
class Thread:
    persona:str
    initial_text:str
    role_history:list[str]

class DialogueState:
    def __init__(self,lex):
        self.lex=lex
        self.mode="analytic"
        self.active_role=None
        self.role_threads={}
        self.analytic_history=[]
        self.plan_history=[]

    def apply(self,text):
        op,cue=self.lex.predict(text)
        p=persona_from(text)
        if op==ENTER:
            if p is None:
                plan={"op":"CLARIFY","missing":"persona","cue":list(cue)}
            else:
                self.mode="roleplay";self.active_role=p
                self.role_threads[p]=Thread(p,text,[text])
                plan={"op":ENTER,"persona":p,"thread":"role:"+p,"cue":list(cue)}
        elif op==RESUME:
            if p is None:p=self.active_role
            if p is None or p not in self.role_threads:
                plan={"op":"CLARIFY","missing":"role thread","cue":list(cue)}
            else:
                self.mode="roleplay";self.active_role=p
                th=self.role_threads[p];th.role_history.append(text)
                plan={"op":RESUME,"persona":p,"thread":"role:"+p,"recover":th.initial_text,"cue":list(cue)}
        elif op==EXIT:
            self.mode="analytic";self.analytic_history.append(text)
            plan={"op":EXIT,"thread":"analytic","cue":list(cue)}
        else:
            self.mode="analytic";self.analytic_history.append(text)
            plan={"op":ANALYZE,"thread":"analytic","cue":list(cue)}
        self.plan_history.append(plan)
        return plan

def stress_one(rng,lex):
    names=["Ari","Bea","Cato","Dara","Emil","Faye","Gio","Hana"]
    objects=["compass","box","map","radio","key","notebook","lens","token"]
    p=rng.choice(names);obj=rng.choice(objects)
    st=DialogueState(lex)
    enter=f"Roleplay as {p}, a careful observer. I bring a sealed {obj}."
    a=st.apply(enter)
    interruptions=[]
    for _ in range(rng.randint(1,8)):
        q=rng.choice([
          "Switch out of roleplay. Compare two explanations.",
          "Out of roleplay. Compare two unrelated ideas.",
          "Leave the roleplay for now and analyze the claim.",
          "Compare the themes in these two stories.",
          "Take this philosophical claim seriously and challenge it.",
        ])
        interruptions.append(q);st.apply(q)
    resume=rng.choice([
      f"Back to {p}. Continue from the {obj}.",
      f"Back to {p}. Pick up where the {obj} scene stopped.",
    ])
    b=st.apply(resume)
    th=st.role_threads.get(p)
    return bool(
      a.get("op")==ENTER and b.get("op")==RESUME
      and st.mode=="roleplay" and th is not None
      and th.initial_text==enter
      and all(q not in th.role_history for q in interruptions)
      and b.get("recover")==enter
    )

def benchmark(lex):
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:b=json.load(f)
    turns=[x for x in b["turns"] if x["thread"]=="switching"]
    st=DialogueState(lex);rows=[]
    for t in turns:
        plan=st.apply(t["prompt"])
        rows.append({"id":t["id"],"plan":plan,"mode":st.mode,"active_role":st.active_role})
    mara=st.role_threads.get("Mara")
    by={x["id"]:x for x in rows}
    return {
      "rows":rows,
      "rp01_entered":by["rp_01"]["plan"].get("op")==ENTER,
      "lit01_exited":by["lit_01"]["plan"].get("op")==EXIT,
      "phil01_analytic":by["phil_01"]["plan"].get("op")==ANALYZE,
      "rp02_resumed":by["rp_02"]["plan"].get("op")==RESUME and by["rp_02"]["active_role"]=="Mara",
      "cross01_analytic":by["cross_01"]["mode"]=="analytic",
      "recovered_brass_box":bool(mara and "brass box" in str(by["rp_02"]["plan"].get("recover","")).casefold()),
      "no_analytic_leak":bool(mara and all("Frankenstein" not in x and "causal organization" not in x for x in mara.role_history)),
    }

def run(seed):
    rng=random.Random(seed)
    lex=DialogueConstructionLexicon().fit(GROUNDING)
    stress=sum(stress_one(rng,lex) for _ in range(2000))/2000
    b=benchmark(lex)
    return {
      "seed":seed,
      "learned_rules":[{"ngram":" ".join(ng),"op":op,"support":sup} for ng,op,sup in lex.rules[:40]],
      "synthetic_thread_recovery":stress,
      "benchmark":b,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="dialogue_state_v1.json");a=ap.parse_args()
    runs=[run(int(x)) for x in a.seeds.split(",")]
    passed=all(
      r["synthetic_thread_recovery"]==1.0
      and all(r["benchmark"][k] for k in (
        "rp01_entered","lit01_exited","phil01_analytic","rp02_resumed",
        "cross01_analytic","recovered_brass_box","no_analytic_leak"
      ))
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
