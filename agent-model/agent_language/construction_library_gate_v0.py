import argparse,json,random,re,time
from collections import defaultdict,Counter
from dataclasses import dataclass

ATTRS={
 "color":("color","color"),
 "pet":("pet","animal"),
 "place":("place","place"),
}
SET_SCHEMAS=[
 "set the {attr} for {name} to {value}.",
 "store {value} as the {attr} for {name}.",
 "for {name}, set the {attr} to {value}.",
 "{name}'s {attr} is {value}.",
]
ASK_SCHEMAS=[
 "what is the {attr} for {name}?",
 "tell me the {attr} for {name}.",
 "for {name}, what is the {attr}?",
 "give me {name}'s {attr}.",
]
HOLD={
 ("set","color"):0,("set","pet"):1,("set","place"):2,
 ("ask","color"):1,("ask","pet"):2,("ask","place"):3,
}
TOK_RE=re.compile(r"<name>|<value>|[a-z]+|'s|[.,?]")

@dataclass(frozen=True)
class Example:
    text:str
    mode:str
    attr:str
    name:str
    value:str|None
    value_role:str|None

def toks(s): return TOK_RE.findall(s.lower())

def opaque(rng,used):
    while True:
        s=''.join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(4,9)))
        if s not in used: used.add(s); return s

def vocab(seed,n=100):
    rng=random.Random(seed); used=set(); d={}
    d["name_train"]=[opaque(rng,used) for _ in range(n)]
    d["name_test"]=[opaque(rng,used) for _ in range(n)]
    for _,(_,role) in ATTRS.items():
        d[role+"_train"]=[opaque(rng,used) for _ in range(n)]
        d[role+"_test"]=[opaque(rng,used) for _ in range(n)]
    return d

def make_ex(mode,attr,si,v,rng,split):
    surf,role=ATTRS[attr]; name=rng.choice(v["name_"+split])
    val=None if mode=="ask" else rng.choice(v[role+"_"+split])
    schema=(SET_SCHEMAS if mode=="set" else ASK_SCHEMAS)[si]
    text=schema.format(attr=surf,name=name,value=val or "")
    return Example(text,mode,attr,name,val,role if mode=="set" else None)

def training(seed,n,v):
    rng=random.Random(seed); pairs=[]
    for mode in ("set","ask"):
      schemas=SET_SCHEMAS if mode=="set" else ASK_SCHEMAS
      for attr in ATTRS:
        for si in range(len(schemas)):
          if si!=HOLD[(mode,attr)]: pairs.append((mode,attr,si))
    return [make_ex(*rng.choice(pairs),v,rng,"train") for _ in range(n)]

def holdout(seed,n,v,split):
    rng=random.Random(seed); pairs=[(m,a,si) for (m,a),si in HOLD.items()]
    return [make_ex(*rng.choice(pairs),v,rng,split) for _ in range(n)]

def mask_args(ex):
    s=ex.text.lower()
    # opaque values are unique substrings; longest first protects accidental overlap.
    reps=[(ex.name,"<name>")]
    if ex.value is not None: reps.append((ex.value,"<value>"))
    for old,new in sorted(reps,key=lambda x:len(x[0]),reverse=True):
        s=s.replace(old,new)
    return toks(s)

class ConstructionLibrary:
    def __init__(self):
        self.attr_lex={}
        self.attr_evidence=Counter()
        self.patterns={}   # pattern tuple -> mode
        self.pattern_attrs=defaultdict(set)
        self.attr_value_role={}

    def fit(self,examples):
        masked=[(ex,mask_args(ex)) for ex in examples]

        # Learn value-role semantics from grounded examples.
        vr=defaultdict(Counter)
        for ex,_ in masked:
            if ex.value_role: vr[ex.attr][ex.value_role]+=1
        self.attr_value_role={a:c.most_common(1)[0][0] for a,c in vr.items()}

        # Anti-unify UNIQUE grounded patterns rather than all duplicate examples.
        # This makes induction cost depend on construction diversity, not corpus size.
        votes=defaultdict(Counter)
        uniq={}
        for ex,ts in masked:
            uniq[(ex.mode,ex.attr,tuple(ts))]=ex
        by_mode_len=defaultdict(list)
        for (mode,attr,ts),ex in uniq.items():
            by_mode_len[(mode,len(ts))].append((ex,list(ts)))
        for group in by_mode_len.values():
            for i in range(len(group)):
                e1,t1=group[i]
                for j in range(i+1,len(group)):
                    e2,t2=group[j]
                    if e1.attr==e2.attr: continue
                    dif=[k for k,(a,b) in enumerate(zip(t1,t2)) if a!=b]
                    if len(dif)!=1: continue
                    k=dif[0]; a,b=t1[k],t2[k]
                    if not (a.isalpha() and b.isalpha()): continue
                    votes[a][e1.attr]+=1; votes[b][e2.attr]+=1

        # Accept only unambiguous surface->semantic mappings with repeated evidence.
        for word,c in votes.items():
            attr,count=c.most_common(1)[0]
            if count>=2 and len(c)==1:
                self.attr_lex[word]=attr
                self.attr_evidence[word]=count

        # Compile generalized constructions. Require each construction to have
        # been grounded in at least two semantic attributes before it can generalize.
        tmp=defaultdict(lambda: {"modes":Counter(),"attrs":set()})
        for ex,ts in masked:
            gt=[]
            replaced=False
            for z in ts:
                if z in self.attr_lex and self.attr_lex[z]==ex.attr:
                    gt.append("<ATTR>"); replaced=True
                else: gt.append(z)
            if not replaced: continue
            p=tuple(gt); tmp[p]["modes"][ex.mode]+=1; tmp[p]["attrs"].add(ex.attr)
        for p,d in tmp.items():
            if len(d["attrs"])>=2:
                self.patterns[p]=d["modes"].most_common(1)[0][0]
                self.pattern_attrs[p]=set(d["attrs"])
        return self

    def parse(self,text):
        ts=toks(text); candidates=[]
        for p,mode in self.patterns.items():
            if len(p)!=len(ts): continue
            cap={}; attr=None; ok=True
            for pat,z in zip(p,ts):
                if pat=="<ATTR>":
                    if z not in self.attr_lex: ok=False; break
                    attr=self.attr_lex[z]
                elif pat=="<name>":
                    if not z.isalpha(): ok=False; break
                    cap["name"]=z
                elif pat=="<value>":
                    if not z.isalpha(): ok=False; break
                    cap["value"]=z
                elif pat!=z:
                    ok=False; break
            if ok and attr is not None and "name" in cap:
                candidates.append((p,mode,attr,cap))
        if len(candidates)!=1: return None
        p,mode,attr,cap=candidates[0]
        out={"mode":mode,"attr":attr,"name":cap["name"]}
        if mode=="set":
            if "value" not in cap: return None
            out["value"]=cap["value"]; out["value_role"]=self.attr_value_role.get(attr)
        return out

def correct(pred,ex):
    if pred is None:return False
    if pred["mode"]!=ex.mode or pred["attr"]!=ex.attr or pred["name"]!=ex.name:return False
    if ex.mode=="set":
        return pred.get("value")==ex.value and pred.get("value_role")==ex.value_role
    return True

def run(seed):
    v=vocab(seed+5000); tr=training(seed+1,9000,v); st=holdout(seed+2,1800,v,"train"); so=holdout(seed+3,1800,v,"test")
    t=time.time(); lib=ConstructionLibrary().fit(tr); fit_s=time.time()-t
    def ev(xs):
        ys=[lib.parse(x.text) for x in xs]
        return {"n":len(xs),"exact":sum(correct(y,x) for y,x in zip(ys,xs))/len(xs),"unparsed":sum(y is None for y in ys)}
    return {
      "seed":seed,"fit_seconds":fit_s,
      "learned_attr_lexicon":lib.attr_lex,
      "attr_evidence":dict(lib.attr_evidence),
      "constructions":len(lib.patterns),
      "construction_support":{str(k):sorted(v) for k,v in lib.pattern_attrs.items()},
      "structural_ood":ev(st),
      "structural_plus_oov_args":ev(so),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="0,1,2"); ap.add_argument("--out",default="construction_library_v0.json"); a=ap.parse_args()
    rs=[run(int(s)) for s in a.seeds.split(",")]
    with open(a.out,"w") as f: json.dump(rs,f,indent=2)
    for r in rs: print(r)
