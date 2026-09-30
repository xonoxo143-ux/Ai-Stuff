import argparse,json,random,time,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from structured_span_gate_v0 import Model,DS,collate,step,evalset,Ex,INTENTS,II,RI,ROLES,PAD
import torch
from torch.utils.data import DataLoader

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

def opaque(rng,used):
    while True:
        s=''.join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(4,9)))
        if s not in used: used.add(s); return s

def make_vocab(seed,n=100):
    rng=random.Random(seed); used=set(); d={}
    d["name_train"]=[opaque(rng,used) for _ in range(n)]
    d["name_test"]=[opaque(rng,used) for _ in range(n)]
    for a,(_,role) in ATTRS.items():
        d[role+"_train"]=[opaque(rng,used) for _ in range(n)]
        d[role+"_test"]=[opaque(rng,used) for _ in range(n)]
    return d

def make_ex(mode,attr,si,v,rng,split):
    surf,role=ATTRS[attr]; name=rng.choice(v["name_"+split]); val=rng.choice(v[role+"_"+split])
    schema=(SET_SCHEMAS if mode=="set" else ASK_SCHEMAS)[si]
    text=schema.format(attr=surf,name=name,value=val)
    intent=("set_" if mode=="set" else "ask_")+attr
    spans={"name":(text.index(name),text.index(name)+len(name)-1)}
    if mode=="set":
        spans[role]=(text.index(val),text.index(val)+len(val)-1)
    return Ex(text,II[intent],spans)

def gen_train(seed,n,v):
    rng=random.Random(seed); out=[]; pairs=[]
    for mode in ("set","ask"):
      schemas=SET_SCHEMAS if mode=="set" else ASK_SCHEMAS
      for attr in ATTRS:
        for si in range(len(schemas)):
          if si!=HOLD[(mode,attr)]: pairs.append((mode,attr,si))
    for _ in range(n):
      mode,attr,si=rng.choice(pairs); out.append(make_ex(mode,attr,si,v,rng,"train"))
    return out

def gen_hold(seed,n,v,split):
    rng=random.Random(seed); out=[]
    pairs=[(m,a,si) for (m,a),si in HOLD.items()]
    for _ in range(n):
      m,a,si=rng.choice(pairs); out.append(make_ex(m,a,si,v,rng,split))
    return out

def function_vocab(xs):
    words=set()
    for x in xs:
      s=x.text.lower()
      # Replace all gold argument spans before extracting surface vocabulary.
      spans=sorted([v for v in x.spans.values()],reverse=True)
      for a,b in spans: s=s[:a]+" SLOT "+s[b+1:]
      words.update(re.findall(r"[a-z]+|'s",s))
    return words

def run(seed,steps):
    random.seed(seed); torch.manual_seed(seed); v=make_vocab(seed+5000)
    tr=gen_train(seed+1,9000,v)
    st=gen_hold(seed+2,1800,v,"train")
    so=gen_hold(seed+3,1800,v,"test")
    tv=function_vocab(tr); sv=function_vocab(st)
    missing=sorted(sv-tv)
    if missing: raise RuntimeError("test contains unseen function words: "+repr(missing))
    m=Model(); opt=torch.optim.AdamW(m.parameters(),lr=2e-3,weight_decay=1e-4)
    dl=DataLoader(DS(tr),batch_size=64,shuffle=True,drop_last=True,collate_fn=collate); it=iter(dl); t=time.time()
    for i in range(steps):
      try:b=next(it)
      except StopIteration: it=iter(dl); b=next(it)
      opt.zero_grad(); loss,_,_=step(m,b,torch.device("cpu")); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1); opt.step()
      if (i+1)%300==0: print(seed,i+1,float(loss.detach()),flush=True)
    return {
      "seed":seed,"steps":steps,"params":sum(p.numel() for p in m.parameters()),"train_seconds":time.time()-t,
      "train_function_vocab":len(tv),"structural_function_vocab":len(sv),
      "structural_ood":evalset(m,st,torch.device("cpu")),
      "structural_plus_oov_args":evalset(m,so,torch.device("cpu")),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="0,1,2"); ap.add_argument("--steps",type=int,default=1200); ap.add_argument("--out",default="structured_span_deconfound_v1.json"); a=ap.parse_args()
    rs=[run(int(s),a.steps) for s in a.seeds.split(",")]
    with open(a.out,"w") as f: json.dump(rs,f,indent=2)
    for r in rs: print(r)
