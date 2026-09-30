import argparse,json,random,re,time
from collections import defaultdict,Counter
from dataclasses import dataclass

ATTRS={"color":("color","color"),"pet":("pet","animal"),"place":("place","place")}
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
WRAP_PREFIXES=["please, ","for reference, ","right now, ","in this case, "]
TOK_RE=re.compile(r"<name>|<value>|[a-z]+|'s|[.,?]")

@dataclass(frozen=True)
class Ex:
    text:str; mode:str; attr:str; name:str; value:str|None; value_role:str|None
    @property
    def sem(self): return (self.mode,self.attr,self.name,self.value,self.value_role)

def toks(s): return TOK_RE.findall(s.lower())

def opaque(rng,used):
    while True:
        s=''.join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(4,9)))
        if s not in used: used.add(s); return s

def vocab(seed,n=120):
    rng=random.Random(seed); used=set(); d={"name_train":[],"name_test":[]}
    d["name_train"]=[opaque(rng,used) for _ in range(n)]
    d["name_test"]=[opaque(rng,used) for _ in range(n)]
    for _,(_,role) in ATTRS.items():
        d[role+"_train"]=[opaque(rng,used) for _ in range(n)]
        d[role+"_test"]=[opaque(rng,used) for _ in range(n)]
    return d

def base_ex(mode,attr,si,v,rng,split):
    surf,role=ATTRS[attr]; name=rng.choice(v["name_"+split]); val=None if mode=="ask" else rng.choice(v[role+"_"+split])
    sc=(SET_SCHEMAS if mode=="set" else ASK_SCHEMAS)[si]
    return Ex(sc.format(attr=surf,name=name,value=val or ""),mode,attr,name,val,role if mode=="set" else None)

def wrapped(ex,prefix): return Ex(prefix+ex.text,ex.mode,ex.attr,ex.name,ex.value,ex.value_role)

def mask_args(ex):
    s=ex.text.lower(); reps=[(ex.name,"<name>")]
    if ex.value is not None: reps.append((ex.value,"<value>"))
    for old,new in sorted(reps,key=lambda x:len(x[0]),reverse=True): s=s.replace(old,new)
    return toks(s)

def is_prefix(longer,shorter):
    if len(longer)<=len(shorter): return None
    k=len(longer)-len(shorter)
    return tuple(longer[:k]) if longer[k:]==shorter else None

class DevConstructionGrammar:
    def __init__(self):
        self.attr_lex={}; self.attr_value_role={}
        self.wrappers=set(); self.wrapper_support=Counter()
        self.patterns={}; self.pattern_support=defaultdict(set)
        self.tentative={}; self.tentative_support=defaultdict(set)

    def _learn_attr_lex(self,examples):
        masked=[(e,mask_args(e)) for e in examples]
        vr=defaultdict(Counter)
        for e,_ in masked:
            if e.value_role: vr[e.attr][e.value_role]+=1
        self.attr_value_role={a:c.most_common(1)[0][0] for a,c in vr.items()}
        uniq={(e.mode,e.attr,tuple(ts)):(e,list(ts)) for e,ts in masked}
        groups=defaultdict(list)
        for (m,a,ts),(e,lst) in uniq.items(): groups[(m,len(ts))].append((e,lst))
        votes=defaultdict(Counter)
        for g in groups.values():
            for i in range(len(g)):
                e1,t1=g[i]
                for j in range(i+1,len(g)):
                    e2,t2=g[j]
                    if e1.attr==e2.attr: continue
                    ds=[k for k,(a,b) in enumerate(zip(t1,t2)) if a!=b]
                    if len(ds)!=1: continue
                    k=ds[0]; a,b=t1[k],t2[k]
                    if a.isalpha() and b.isalpha():
                        votes[a][e1.attr]+=1; votes[b][e2.attr]+=1
        for w,c in votes.items():
            a,n=c.most_common(1)[0]
            if len(c)==1 and n>=2:self.attr_lex[w]=a

    def normalize(self,e):
        out=[]
        for z in mask_args(e):
            if z in self.attr_lex and self.attr_lex[z]==e.attr: out.append("<ATTR>")
            else: out.append(z)
        return out

    def fit(self,examples):
        self._learn_attr_lex(examples)
        bysem=defaultdict(list)
        for e in examples: bysem[e.sem].append((e,self.normalize(e)))
        # A wrapper is learned only when the SAME grounded meaning was observed
        # both bare and with a prefix, and the prefix recurs across meanings.
        cand=Counter()
        for pairs in bysem.values():
            for i in range(len(pairs)):
                for j in range(len(pairs)):
                    if i==j:continue
                    p=is_prefix(pairs[i][1],pairs[j][1])
                    if p: cand[p]+=1
        self.wrappers={p for p,n in cand.items() if n>=3}
        self.wrapper_support=Counter({p:cand[p] for p in self.wrappers})

        # Compile core constructions after removing any learned wrappers.
        tmp=defaultdict(lambda:{"modes":Counter(),"attrs":set()})
        for e in examples:
            ts=self.strip_wrappers(self.normalize(e))[0]
            if "<ATTR>" not in ts or "<name>" not in ts:continue
            p=tuple(ts); tmp[p]["modes"][e.mode]+=1; tmp[p]["attrs"].add(e.attr)
        for p,d in tmp.items():
            if len(d["attrs"])>=2:
                self.patterns[p]=d["modes"].most_common(1)[0][0]
                self.pattern_support[p]=set(d["attrs"])
        return self

    def strip_wrappers(self,ts,maxdepth=8):
        ts=list(ts); used=[]; depth=0
        while depth<maxdepth:
            hits=[p for p in self.wrappers if len(p)<=len(ts) and tuple(ts[:len(p)])==p]
            if not hits:break
            p=max(hits,key=len); ts=ts[len(p):]; used.append(p); depth+=1
        return ts,used

    def _match(self,pattern,mode,ts):
        if len(pattern)!=len(ts):return None
        cap={}; attr=None
        for p,z in zip(pattern,ts):
            if p=="<ATTR>":
                if z not in self.attr_lex:return None
                attr=self.attr_lex[z]
            elif p=="<name>":
                if not z.isalpha():return None
                cap["name"]=z
            elif p=="<value>":
                if not z.isalpha():return None
                cap["value"]=z
            elif p!=z:return None
        if attr is None or "name" not in cap:return None
        out={"mode":mode,"attr":attr,"name":cap["name"]}
        if mode=="set":
            if "value" not in cap:return None
            out.update(value=cap["value"],value_role=self.attr_value_role.get(attr))
        return out

    def parse(self,text):
        ts,wr=self.strip_wrappers(toks(text))
        hits=[]
        for p,m in self.patterns.items():
            y=self._match(p,m,ts)
            if y:hits.append(("durable",p,y,wr))
        for p,m in self.tentative.items():
            y=self._match(p,m,ts)
            if y:hits.append(("tentative",p,y,wr))
        if len(hits)!=1:return None
        kind,p,y,wr=hits[0]; y["_kind"]=kind; y["_wrappers"]=len(wr); return y

    def fast_map(self,e):
        # Prior grounded lexicon lets one example expose ATTR as a reusable slot.
        ts,_=self.strip_wrappers(self.normalize(e))
        p=tuple(ts)
        if "<ATTR>" not in p or "<name>" not in p:return False
        if e.mode=="set" and "<value>" not in p:return False
        old=self.tentative.get(p)
        if old is not None and old!=e.mode:return False
        self.tentative[p]=e.mode
        self.tentative_support[p].add(e.attr)
        return True

    def confirm(self,e):
        if not self.fast_map(e):return False
        ts,_=self.strip_wrappers(self.normalize(e)); p=tuple(ts)
        if len(self.tentative_support[p])>=2:
            self.patterns[p]=self.tentative[p]
            self.pattern_support[p]=set(self.tentative_support[p])
            del self.tentative[p]
        return True

def ok(y,e):
    if y is None:return False
    if y["mode"]!=e.mode or y["attr"]!=e.attr or y["name"]!=e.name:return False
    return e.mode=="ask" or (y.get("value")==e.value and y.get("value_role")==e.value_role)

def make_training(seed,v):
    rng=random.Random(seed); out=[]
    # Dense base evidence.
    for mode in ("set","ask"):
      schemas=SET_SCHEMAS if mode=="set" else ASK_SCHEMAS
      for attr in ATTRS:
        for si in range(len(schemas)):
          for _ in range(8): out.append(base_ex(mode,attr,si,v,rng,"train"))
    # Paired wrapper evidence: bare + one wrapper for identical grounded meaning.
    for wi,pref in enumerate(WRAP_PREFIXES):
      for k in range(6):
        mode="set" if (k+wi)%2==0 else "ask"; attr=list(ATTRS)[(k+wi)%3]
        si=(k+wi)%4; e=base_ex(mode,attr,si,v,rng,"train")
        out.extend([e,wrapped(e,pref)])
    rng.shuffle(out); return out

def test_recursive(g,seed,v,n=1200):
    rng=random.Random(seed); good=0; depths=Counter()
    for _ in range(n):
        mode=rng.choice(["set","ask"]); attr=rng.choice(list(ATTRS)); si=rng.randrange(4)
        e=base_ex(mode,attr,si,v,rng,"test")
        # Use 2-3 wrappers; no such nested combination appears in training.
        chosen=rng.sample(WRAP_PREFIXES,rng.choice([2,3]))
        w=e
        # Prefix application means reverse here preserves chosen outer->inner order.
        for pref in reversed(chosen): w=wrapped(w,pref)
        y=g.parse(w.text); good+=ok(y,w)
        if y:depths[y["_wrappers"]]+=1
    return {"n":n,"exact":good/n,"parsed_wrapper_depths":dict(depths)}

NOVEL_SET="archive {value} beneath {name}'s {attr}."
NOVEL_ASK="fetch the {attr} registered for {name}?"

def novel_ex(mode,attr,v,rng,split):
    surf,role=ATTRS[attr]; name=rng.choice(v["name_"+split])
    if mode=="set":
        val=rng.choice(v[role+"_"+split]); text=NOVEL_SET.format(value=val,name=name,attr=surf)
        return Ex(text,mode,attr,name,val,role)
    text=NOVEL_ASK.format(name=name,attr=surf)
    return Ex(text,mode,attr,name,None,None)

def test_novel(g,seed,v,mode,ground_attr,n=600):
    rng=random.Random(seed)
    ground=novel_ex(mode,ground_attr,v,rng,"train")
    before=g.parse(ground.text)
    mapped=g.fast_map(ground)
    attrs=[a for a in ATTRS if a!=ground_attr]
    xs=[novel_ex(mode,rng.choice(attrs),v,rng,"test") for _ in range(n)]
    ys=[g.parse(x.text) for x in xs]
    return ground,mapped,{"n":n,"exact":sum(ok(y,x) for y,x in zip(ys,xs))/n,
                         "tentative_hits":sum(y is not None and y.get("_kind")=="tentative" for y in ys),
                         "ground_preexisting_parse":before is not None}

def run(seed):
    v=vocab(seed+9000); tr=make_training(seed+1,v); g=DevConstructionGrammar().fit(tr)
    # Old-language regression set before new learning.
    rng=random.Random(seed+2)
    old=[base_ex(rng.choice(["set","ask"]),rng.choice(list(ATTRS)),rng.randrange(4),v,rng,"test") for _ in range(1200)]
    old_before=sum(ok(g.parse(x.text),x) for x in old)/len(old)
    rec=test_recursive(g,seed+3,v)

    gs,ms,setfast=test_novel(g,seed+4,v,"set","color")
    ga,ma,askfast=test_novel(g,seed+5,v,"ask","pet")

    old_after_tent=sum(ok(g.parse(x.text),x) for x in old)/len(old)

    # One independent grounded example under another attribute confirms each construction.
    rng2=random.Random(seed+6)
    cs=novel_ex("set","pet",v,rng2,"train"); ca=novel_ex("ask","place",v,rng2,"train")
    g.confirm(cs); g.confirm(ca)
    postset=[novel_ex("set",rng2.choice(list(ATTRS)),v,rng2,"test") for _ in range(600)]
    postask=[novel_ex("ask",rng2.choice(list(ATTRS)),v,rng2,"test") for _ in range(600)]
    durable=(sum(ok(g.parse(x.text),x) for x in postset+postask)/1200)
    old_after=sum(ok(g.parse(x.text),x) for x in old)/len(old)

    return {
      "seed":seed,
      "base_constructions":len(g.patterns),
      "learned_wrappers":[list(x) for x in sorted(g.wrappers)],
      "wrapper_support":{str(k):v for k,v in g.wrapper_support.items()},
      "old_exact_before":old_before,
      "recursive_unseen_composition":rec,
      "one_shot_set":setfast,
      "one_shot_ask":askfast,
      "old_exact_after_tentative":old_after_tent,
      "durable_novel_exact_after_confirmation":durable,
      "old_exact_after_confirmation":old_after,
      "tentative_remaining":len(g.tentative),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="0,1,2"); ap.add_argument("--out",default="developmental_construction_v1.json"); a=ap.parse_args()
    t=time.time(); rs=[run(int(s)) for s in a.seeds.split(",")]
    out={"wall_seconds":time.time()-t,"runs":rs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
