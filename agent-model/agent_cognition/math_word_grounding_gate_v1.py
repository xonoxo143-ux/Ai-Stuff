from __future__ import annotations
import argparse,json,random,re,math
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=28

VERBS={
 "discounts":"DEC","reduces":"DEC","cuts":"DEC",
 "raises":"INC","increases":"INC","boosts":"INC"
}
CAND=("DEC","INC")

def apply(mode,x,p):
    f=Decimal(1)-Decimal(p)/100 if mode=="DEC" else Decimal(1)+Decimal(p)/100
    return x*f

class GroundedPercentLexicon:
    def __init__(self):self.meaning={}
    def observe(self,verb,start,p,end):
        c=[m for m in CAND if apply(m,start,p)==end]
        if len(c)==1:self.meaning[verb]=c[0]
        return c
    def develop(self,seed):
        rng=random.Random(seed)
        for verb,hidden in VERBS.items():
            start=Decimal(rng.choice([40,50,80,100,125,200]))
            p=rng.choice([5,10,20,25,40])
            end=apply(hidden,start,p)
            self.observe(verb,start,p,end)
        return self

def parse_problem(text,lex):
    low=text.casefold()
    found=[]
    for verb,mode in lex.meaning.items():
        for m in re.finditer(r"\b"+re.escape(verb)+r"\b",low):
            found.append((m.start(),verb,mode))
    found.sort()
    perc=[Decimal(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%",low)]
    money=[Decimal(x.replace(",","")) for x in re.findall(r"$\s*(\d[\d,]*(?:\.\d+)?)",low)]
    if not found or len(found)!=len(perc) or not money:return None
    final=money[-1]
    steps=[]
    for (_,verb,mode),p in zip(found,perc):
        factor=Decimal(1)-p/100 if mode=="DEC" else Decimal(1)+p/100
        steps.append({"verb":verb,"mode":mode,"percent":p,"factor":factor})
    return steps,final

def solve(text,lex):
    parsed=parse_problem(text,lex)
    if parsed is None:return None
    steps,final=parsed
    total=Decimal(1)
    for s in steps:total*=s["factor"]
    if total==0:return None
    original=final/total
    return steps,final,total,original

def fmt(d):
    q=d.quantize(Decimal("0.0000001")).normalize()
    s=format(q,"f")
    return s.rstrip("0").rstrip(".") if "." in s else s

def make_problem(verbs,ps,orig):
    x=Decimal(orig)
    clauses=[]
    for v,p in zip(verbs,ps):
        mode=VERBS[v];x=apply(mode,x,Decimal(p))
        clauses.append(f"{v} an item by {p}%")
    return f"A store {', then '.join(clauses)}. The final price is ${fmt(x)}. What was the original price?",x

def run(seed,benchmark_prompt):
    rng=random.Random(seed)
    lex=GroundedPercentLexicon().develop(seed+100)
    lex_ok=lex.meaning==VERBS
    random_ok=0;case_total=300
    for _ in range(case_total):
        n=rng.choice([1,2,3])
        verbs=[rng.choice(list(VERBS)) for _ in range(n)]
        ps=[rng.choice([5,10,15,20,25,30,40]) for _ in range(n)]
        orig=rng.choice([20,40,50,80,100,125,200,250])
        text,_=make_problem(verbs,ps,orig)
        got=solve(text,lex)
        if got is not None and abs(got[3]-Decimal(orig))<Decimal("0.00001"):random_ok+=1
    b=solve(benchmark_prompt,lex)
    bval=None if b is None else b[3]
    deriv=None
    if b is not None:
        steps,final,factor_total,original=b
        parts=[fmt(s["factor"]) for s in steps]
        deriv=f"Original price: ${fmt(original)}. Check: ${fmt(original)} × {' × '.join(parts)} = ${fmt(final)}."
    return {
      "seed":seed,"lexicon_exact":lex_ok,"learned_lexicon":lex.meaning,
      "heldout_random_exact":random_ok/case_total,
      "benchmark_value":None if bval is None else fmt(bval),
      "benchmark_response":deriv,
      "benchmark_pass":bval is not None and abs(bval-Decimal(100))<Decimal("0.00001")
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="math_word_grounding_v1.json");a=ap.parse_args()
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:bench=json.load(f)
    prompt=next(x["prompt"] for x in bench["turns"] if x["id"]=="math_01")
    runs=[run(int(s),prompt) for s in a.seeds.split(",")]
    out={"passed":all(r["lexicon_exact"] and r["heldout_random_exact"]==1.0 and r["benchmark_pass"] for r in runs),"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2,default=str)
    print(json.dumps(out,indent=2,default=str))
