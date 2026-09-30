import argparse,json,random,time
from dataclasses import dataclass
import torch
import torch.nn as nn
from torch.utils.data import Dataset,DataLoader

INTENTS=["set_color","ask_color","set_pet","ask_pet","set_place","ask_place"]
ROLES=["name","color","animal","place"]
RI={r:i for i,r in enumerate(ROLES)}; II={x:i for i,x in enumerate(INTENTS)}
RBI={"set_color":("name","color"),"ask_color":("name",),"set_pet":("name","animal"),"ask_pet":("name",),"set_place":("name","place"),"ask_place":("name",)}
TRAIN={
"set_color":["remember that {name} likes {color}.","{name}'s color is {color}.","set {name}'s color to {color}.","note {name} with color {color}.","store {color} as the color for {name}."],
"ask_color":["what color does {name} like?","tell me {name}'s color.","what is the color for {name}?","give me the color stored for {name}."],
"set_pet":["remember that {name} has a {animal}.","{name}'s animal is {animal}.","set {name}'s pet to {animal}.","note {name} with animal {animal}.","store {animal} as the pet for {name}."],
"ask_pet":["what animal does {name} have?","tell me {name}'s pet.","what is the animal for {name}?","give me the pet stored for {name}."],
"set_place":["remember that {name} is in {place}.","{name}'s place is {place}.","set {name}'s location to {place}.","note {name} at place {place}.","store {place} as the location for {name}."],
"ask_place":["where is {name}?","tell me {name}'s place.","what is the location for {name}?","give me the place stored for {name}."]}
OOD={
"set_color":["for {name}, keep {color} as the color.","the color associated with {name} is {color}.","please record {color} for {name}'s color."],
"ask_color":["which color is stored for {name}?","for {name}, what color should I recall?","retrieve the color associated with {name}."],
"set_pet":["for {name}, keep {animal} as the pet.","the animal associated with {name} is {animal}.","please record {animal} for {name}'s pet."],
"ask_pet":["which animal is stored for {name}?","for {name}, what pet should I recall?","retrieve the animal associated with {name}."],
"set_place":["for {name}, keep {place} as the place.","the location associated with {name} is {place}.","please record {place} for {name}'s location."],
"ask_place":["which place is stored for {name}?","for {name}, what location should I recall?","retrieve the place associated with {name}."]}

def opaque(rng,used):
    while 1:
        s=''.join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(4,9)))
        if s not in used: used.add(s); return s

def vocab(seed,n=80):
    rng=random.Random(seed); used=set(); d={}
    for r in ROLES:
        d[r+"_train"]=[opaque(rng,used) for _ in range(n)]
        d[r+"_test"]=[opaque(rng,used) for _ in range(n)]
    return d

@dataclass
class Ex: text:str; intent:int; spans:dict

def gen(seed,n,tmpls,v,split):
    rng=random.Random(seed); out=[]
    for _ in range(n):
        intent=rng.choice(INTENTS); vals={r:rng.choice(v[r+"_"+split]) for r in RBI[intent]}
        text=rng.choice(tmpls[intent]).format(**vals); spans={}
        for r,val in vals.items():
            s=text.index(val); spans[r]=(s,s+len(val)-1)
        out.append(Ex(text,II[intent],spans))
    return out

class DS(Dataset):
    def __init__(self,x): self.x=x
    def __len__(self): return len(self.x)
    def __getitem__(self,i): return self.x[i]
PAD=256

def collate(batch):
    L=max(len(x.text) for x in batch); B=len(batch)
    ids=torch.full((B,L),PAD,dtype=torch.long); mask=torch.zeros((B,L),dtype=torch.bool)
    intents=torch.tensor([x.intent for x in batch]); gold=torch.full((B,4,2),-1,dtype=torch.long); present=torch.zeros((B,4),dtype=torch.bool)
    texts=[]
    for i,x in enumerate(batch):
        b=x.text.encode(); ids[i,:len(b)]=torch.tensor(list(b)); mask[i,:len(b)]=1; texts.append(x.text)
        for r,(s,e) in x.spans.items(): j=RI[r]; gold[i,j]=torch.tensor([s,e]); present[i,j]=1
    return ids,mask,intents,gold,present,texts

class Model(nn.Module):
    def __init__(self):
        super().__init__(); self.emb=nn.Embedding(257,40,padding_idx=PAD); self.gru=nn.GRU(40,64,batch_first=True,bidirectional=True)
        self.intent=nn.Sequential(nn.Linear(256,96),nn.ReLU(),nn.Linear(96,6))
        self.start=nn.Linear(128,4); self.end=nn.Linear(128,4); self.null=nn.Parameter(torch.zeros(4))
    def forward(self,x,m):
        h,_=self.gru(self.emb(x)); mf=m.unsqueeze(-1); mean=(h*mf).sum(1)/m.sum(1,keepdim=True).clamp_min(1)
        mx=h.masked_fill(~mf,torch.finfo(h.dtype).min).max(1).values
        return self.intent(torch.cat([mean,mx],-1)),self.start(h),self.end(h)

def scores(sl,el,mask,r,maxspan=16,null=None):
    B,L,_=sl.shape; sc=sl[:,:,r].unsqueeze(2)+el[:,:,r].unsqueeze(1); z=torch.arange(L,device=sl.device); w=z[None,:]-z[:,None]+1
    valid=((w>=1)&(w<=maxspan)).unsqueeze(0)&mask.unsqueeze(2)&mask.unsqueeze(1)
    sc=sc.masked_fill(~valid,-1e9).reshape(B,L*L)
    return torch.cat([sc,null[r].expand(B,1)],1)

def step(model,batch,device):
    ids,mask,intents,gold,present,texts=batch; ids,mask,intents,gold,present=[x.to(device) for x in (ids,mask,intents,gold,present)]
    il,sl,el=model(ids,mask); loss=nn.functional.cross_entropy(il,intents); pred=il.argmax(-1).cpu(); ps={}
    L=mask.size(1); ni=L*L
    for r,name in enumerate(ROLES):
        sc=scores(sl,el,mask,r,null=model.null)
        target=torch.where(present[:,r],gold[:,r,0]*L+gold[:,r,1],torch.full_like(gold[:,r,0],ni))
        loss=loss+nn.functional.cross_entropy(sc,target); pp=sc.argmax(-1).tolist(); ps[name]=[(-1,-1) if j==ni else (j//L,j%L) for j in pp]
    return loss,pred,ps

@torch.no_grad()
def evalset(model,xs,device):
    n=ex=io=ro=rt=0
    for batch in DataLoader(DS(xs),batch_size=128,collate_fn=collate):
        _,pi,ps=step(model,batch,device); _,_,ints,gold,present,texts=batch
        for b,t in enumerate(texts):
            n+=1; ok=int(pi[b])==int(ints[b]); io+=ok
            for r,name in enumerate(ROLES):
                g=(-1,-1) if not present[b,r] else (int(gold[b,r,0]),int(gold[b,r,1])); p=ps[name][b]
                rt+=1; ro+=p==g; ok &= p==g
            ex+=ok
    return {"n":n,"intent":io/n,"role":ro/rt,"exact":ex/n}

def run(seed,steps):
    random.seed(seed); torch.manual_seed(seed); v=vocab(seed+1000)
    tr=gen(seed+1,6000,TRAIN,v,"train"); tests={
      "iid":gen(seed+2,1200,TRAIN,v,"train"),
      "paraphrase":gen(seed+3,1200,OOD,v,"train"),
      "oov_familiar":gen(seed+4,1200,TRAIN,v,"test"),
      "oov_paraphrase":gen(seed+5,1200,OOD,v,"test")}
    dev=torch.device("cpu"); m=Model().to(dev); opt=torch.optim.AdamW(m.parameters(),lr=2e-3,weight_decay=1e-4)
    dl=DataLoader(DS(tr),batch_size=64,shuffle=True,drop_last=True,collate_fn=collate); it=iter(dl); t=time.time()
    for i in range(steps):
        try: b=next(it)
        except StopIteration: it=iter(dl); b=next(it)
        opt.zero_grad(); loss,_,_=step(m,b,dev); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(),1); opt.step()
        if (i+1)%300==0: print(seed,i+1,float(loss.detach()),flush=True)
    return {"seed":seed,"steps":steps,"params":sum(p.numel() for p in m.parameters()),"train_seconds":time.time()-t,**{k:evalset(m,x,dev) for k,x in tests.items()}}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="0,1,2"); ap.add_argument("--steps",type=int,default=1200); ap.add_argument("--out",default="structured_span_result.json"); a=ap.parse_args()
    rs=[run(int(s),a.steps) for s in a.seeds.split(",")]
    with open(a.out,"w") as f: json.dump(rs,f,indent=2)
    for r in rs: print(r)
