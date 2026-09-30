from __future__ import annotations
import argparse,json,random,re,string
from dataclasses import dataclass,asdict
from pathlib import Path

ENTER="ENTER_ROLE"
EXIT="EXIT_ROLE"
RESUME="RESUME_ROLE"
ANALYZE="ANALYTIC"

GROUNDING={
 ENTER:[
   ("Roleplay as Iris, a cautious medic. I arrive with a cracked compass.",ENTER),
   ("Roleplay as Toma, a skeptical pilot. A sealed chart is on the table.",ENTER),
   ("Roleplay as Quinn, a patient engineer. The alarm has just stopped.",ENTER),
 ],
 EXIT:[
   ("Switch out of roleplay. Explain the mechanism.",EXIT),
   ("Out of roleplay. Compare the two ideas.",EXIT),
   ("Leave the roleplay for now and analyze the claim.",EXIT),
 ],
 RESUME:[
   ("Back to Iris. Continue from the compass.",RESUME),
   ("Back to Toma. Pick up where the chart scene stopped.",RESUME),
   ("Resume Quinn and continue the scene.",RESUME),
 ],
 ANALYZE:[
   ("Compare the themes in these two novels.",ANALYZE),
   ("Take this philosophical claim seriously and challenge it.",ANALYZE),
   ("Explain the connection between these arguments.",ANALYZE),
 ]
}

def tokenize(text):
    return re.findall(r"[a-z]+",text.casefold())

class DialogueOpLexicon:
    def __init__(self):
        self.token_votes={}
        self.op_tokens={}

    def fit(self,grounding):
        votes={}
        global_count={}
        for rows in grounding.values():
            for text,op in rows:
                toks=set(tokenize(text))
                for t in toks:
                    global_count[t]=global_count.get(t,0)+1
                    votes.setdefault(t,{})
                    votes[t][op]=votes[t].get(op,0)+1
        # Keep tokens whose evidence is strongly operation-specific.
        for tok,row in votes.items():
            op,n=max(row.items(),key=lambda x:x[1])
            other=sum(row.values())-n
            if n>=2 and other==0:
                self.token_votes[t]=op
        by={}
        for tok,op in self.token_votes.items():by.setdefault(op,set()).add(tok)
        self.op_tokens=by
        return self

    def predict(self,text):
        toks=set(tokenize(text))
        scores={op:len(toks & ts) for op,ts in self.op_tokens.items()}
        if not scores:return ANALYZE
        op,score=max(scores.items(),key=lambda x:(x[1],x[0]))
        # roleplay control needs explicit evidence; generic content defaults analytic.
        return op if score>0 else ANALYZE

PERSONA_RE=re.compile(r"(?:roleplay as|back to|resume)\s+([A-Z][A-Za-z0-9_-]*)",re.I)

def persona_from(text):
    m=PERSONA_RE.search(text)
    return None if m is None else m.group(1)

def content_terms(text):
    stop={
      "roleplay","switch","out","back","resume","continue","from","the","a","an",
      "as","to","of","and","with","for","now","again","pick","up","where","scene",
      "leave","explain","compare","analyze","take","this","claim","seriously"
    }
    return [t for t in tokenize(text) if t not in stop]

@dataclass
class Thread:
    persona:str
    initial_text:str
    role_history:list[str]

class DialogueState:
    def __init__(self,lexicon):
        self.lexicon=lexicon
        self.mode="analytic"
        self.active_role=None
        self.role_threads={}
        self.analytic_history=[]
        self.last_plan=None

    def apply(self,text):
        op=self.lexicon.predict(text)
        p=persona_from(text)
        if op==ENTER:
            if p is None:return {"op":"ERROR","reason":"missing persona"}
            self.mode="roleplay";self.active_role=p
            self.role_threads[p]=Thread(p,text,[text])
            self.last_plan={"op":ENTER,"persona":p,"thread":"role:"+p}
        elif op==EXIT:
            self.mode="analytic"
            self.analytic_history.append(text)
            self.last_plan={"op":EXIT,"thread":"analytic"}
        elif op==RESUME:
            if p is None:
                p=self.active_role
            if p is None or p not in self.role_threads:
                self.last_plan={"op":"CLARIFY","missing":"role thread"}
                return self.last_plan
            self.mode="roleplay";self.active_role=p
            self.role_threads[p].role_history.append(text)
            self.last_plan={
              "op":RESUME,"persona":p,"thread":"role:"+p,
              "recover":self.role_threads[p].initial_text,
            }
        else:
            self.mode="analytic"
            self.analytic_history.append(text)
            self.last_plan={"op":ANALYZE,"thread":"analytic","topic_terms":content_terms(text)}
        return self.last_plan

def synthetic_sequence(rng,lex):
    names=["Ari","Bea","Cato","Dara","Emil","Faye","Gio","Hana"]
    objects=["compass","box","map","radio","key","notebook","lens","token"]
    persona=rng.choice(names);obj=rng.choice(objects)
    state=DialogueState(lex)
    enter=f"Roleplay as {persona}, a careful observer. I bring a sealed {obj}."
    p1=state.apply(enter)
    interruptions=[]
    for i in range(rng.randint(1,6)):
        text=rng.choice([
          "Switch out of roleplay. Compare two explanations.",
          "Out of roleplay. Analyze a philosophical objection.",
          "Leave the roleplay for now and explain a technical idea.",
          "Compare the themes in these two stories.",
        ])
        interruptions.append(text);state.apply(text)
    resume=f"Back to {persona}. Continue from the {obj}."
    pr=state.apply(resume)
    thread=state.role_threads.get(persona)
    return {
      "correct":(
        p1["op"]==ENTER and pr["op"]==RESUME
        and state.mode=="roleplay"
        and thread is not None
        and thread.initial_text==enter
        and all(x not in thread.role_history for x in interruptions)
      ),
      "persona":persona,"object":obj,"plan":pr,
    }

def benchmark_switching(seed,lex):
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:b=json.load(f)
    turns=[x for x in b["turns"] if x["thread"]=="switching"]
    s=DialogueState(lex);rows=[]
    for t in turns:
        plan=s.apply(t["prompt"])
        rows.append({"id":t["id"],"plan":plan,"mode":s.mode,"active_role":s.active_role})
    mara=s.role_threads.get("Mara")
    rp2=next(x for x in rows if x["id"]=="rp_02")
    return {
      "rows":rows,
      "mara_exists":mara is not None,
      "mara_initial_has_brass_box":bool(mara and "brass box" in mara.initial_text.casefold()),
      "mara_role_history_count":0 if mara is None else len(mara.role_history),
      "rp2_resumes_mara":rp2["plan"].get("op")==RESUME and rp2["active_role"]=="Mara",
      "rp2_recovered_brass_box": "brass box" in str(rp2["plan"].get("recover","")).casefold(),
      "analytic_turns_not_in_role_history":bool(
        mara and all("Frankenstein" not in x and "causal organization" not in x for x in mara.role_history)
      )
    }

def run(seed):
    rng=random.Random(seed)
    lex=DialogueOpLexicon().fit(GROUNDING)
    stress=[synthetic_sequence(rng,lex) for _ in range(1000)]
    bench=benchmark_switching(seed,lex)
    return {
      "seed":seed,
      "learned_token_map":lex.token_votes,
      "synthetic_thread_recovery":sum(x["correct"] for x in stress)/len(stress),
      "benchmark":bench,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="dialogue_state_v0.json");a=ap.parse_args()
    runs=[run(int(x)) for x in a.seeds.split(",")]
    passed=all(
      r["synthetic_thread_recovery"]==1.0
      and r["benchmark"]["mara_exists"]
      and r["benchmark"]["rp2_resumes_mara"]
      and r["benchmark"]["rp2_recovered_brass_box"]
      and r["benchmark"]["analytic_turns_not_in_role_history"]
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
