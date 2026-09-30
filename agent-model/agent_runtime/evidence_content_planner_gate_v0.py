from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import string
import tempfile
from pathlib import Path
from time import perf_counter

import torch
import torch.nn as nn

RELATIONS=("origin","method","goal","constraint","effect","theme")

def word(i:int)->str:
    letters=string.ascii_lowercase
    out=""
    n=i+1
    while n:
        n,r=divmod(n-1,26)
        out=letters[r]+out
    return "q"+out

class EvidenceStore:
    def __init__(self,path:Path):
        self.path=str(path)
        self.db=sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=OFF")
        self.db.executescript("""
        CREATE TABLE evidence(
          entity TEXT NOT NULL,
          relation TEXT NOT NULL,
          value TEXT NOT NULL,
          source TEXT NOT NULL,
          confidence REAL NOT NULL,
          PRIMARY KEY(entity,relation)
        );
        CREATE INDEX evidence_er ON evidence(entity,relation);
        """)
        self.db.commit()

    def add(self,rows):
        self.db.executemany(
          "INSERT OR REPLACE INTO evidence(entity,relation,value,source,confidence) VALUES(?,?,?,?,?)",
          rows
        )
        self.db.commit()

    def fetch(self,entities,relations):
        started=perf_counter()
        qs=",".join("?"*len(entities))
        rs=",".join("?"*len(relations))
        rows=self.db.execute(
          f"SELECT entity,relation,value,source,confidence FROM evidence "
          f"WHERE entity IN ({qs}) AND relation IN ({rs})",
          tuple(entities)+tuple(relations)
        ).fetchall()
        return rows,(perf_counter()-started)*1000

    def delete(self,entity,relation):
        self.db.execute("DELETE FROM evidence WHERE entity=? AND relation=?",(entity,relation))
        self.db.commit()

    def bytes(self):
        self.db.execute("PRAGMA wal_checkpoint(FULL)")
        self.db.commit()
        return sum(
          os.path.getsize(p)
          for p in (self.path,self.path+"-wal",self.path+"-shm")
          if os.path.exists(p)
        )

    def close(self):
        self.db.close()

def make_rows(seed,count,target=None):
    rng=random.Random(seed)
    rows=[]
    used=set()
    if target:
        for row in target:
            rows.append(row);used.add((row[0],row[1]))
    i=0
    while len(rows)<count:
        ent="ent"+word(i)
        rel=rng.choice(RELATIONS)
        key=(ent,rel);i+=1
        if key in used:continue
        used.add(key)
        val="val"+word(rng.randrange(1,10_000_000))
        src="src"+word(rng.randrange(1,100_000))
        rows.append((ent,rel,val,src,0.9))
    return rows

def plan_compare(store,a,b,r1,r2):
    rows,lat=store.fetch((a,b),(r1,r2))
    by={(e,r):(v,s,c) for e,r,v,s,c in rows}
    needed=[(a,r1),(b,r1),(a,r2),(b,r2)]
    missing=[x for x in needed if x not in by]
    plan={
      "kind":"compare_complete" if not missing else "compare_missing",
      "a":a,"b":b,"r1":r1,"r2":r2,
      "retrieved_rows":len(rows),
      "lookup_ms":lat,
      "missing":[{"entity":e,"relation":r} for e,r in missing],
    }
    for tag,e,r in (
      ("a1",a,r1),("b1",b,r1),("a2",a,r2),("b2",b,r2)
    ):
        val=by.get((e,r))
        plan[tag]="" if val is None else val[0]
        plan[tag+"_source"]="" if val is None else val[1]
    if missing:
        plan["missing_text"]=", ".join(f"{e}:{r}" for e,r in missing)
    else:
        plan["r1_relation"]="same" if plan["a1"]==plan["b1"] else "different"
        plan["r2_relation"]="same" if plan["a2"]==plan["b2"] else "different"
    return plan

COPY_A=256;COPY_B=257;COPY_R1=258;COPY_R2=259
COPY_A1=260;COPY_B1=261;COPY_A2=262;COPY_B2=263
COPY_MISSING=264;EOS=265;BOS=266
OUT=266;INP=267
KINDS=("compare_complete","compare_missing")
KID={k:i for i,k in enumerate(KINDS)}

SCAFFOLDS={
 "compare_complete":[
   *b"On ",COPY_R1,*b", ",COPY_A,*b" has ",COPY_A1,*b", while ",COPY_B,*b" has ",COPY_B1,ord("."),
   *b" On ",COPY_R2,*b", ",COPY_A,*b" has ",COPY_A2,*b", while ",COPY_B,*b" has ",COPY_B2,ord("."),EOS
 ],
 "compare_missing":[
   *b"I have insufficient evidence for ",COPY_MISSING,ord("."),
   *b" I will not fill the missing fact from memory.",EOS
 ],
}

class Realizer(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb=nn.Embedding(INP,36)
        self.kind=nn.Embedding(len(KINDS),44)
        self.init=nn.Linear(44,72)
        self.gru=nn.GRU(36,72,batch_first=True)
        self.out=nn.Linear(72,OUT)

def train_realizer(seed,steps=650):
    random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(2)
    m=Realizer();opt=torch.optim.AdamW(m.parameters(),lr=7e-3)
    L=max(len(v) for v in SCAFFOLDS.values())
    kinds=[];prev=[];target=[]
    for k in KINDS:
        t=list(SCAFFOLDS[k]);p=[BOS]+t[:-1];pad=L-len(t)
        kinds.append(KID[k]);prev.append(p+[BOS]*pad);target.append(t+[-100]*pad)
    kinds=torch.tensor(kinds);prev=torch.tensor(prev);target=torch.tensor(target)
    for _ in range(steps):
        h0=torch.tanh(m.init(m.kind(kinds))).unsqueeze(0)
        h,_=m.gru(m.emb(prev),h0)
        logits=m.out(h)
        loss=nn.functional.cross_entropy(logits.reshape(-1,OUT),target.reshape(-1),ignore_index=-100)
        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(m.parameters(),1);opt.step()
    return m.eval(),sum(p.numel() for p in m.parameters())

@torch.no_grad()
def generate(model,kind):
    kid=torch.tensor([KID[kind]])
    hidden=torch.tanh(model.init(model.kind(kid))).unsqueeze(0)
    tok=torch.tensor([[BOS]]);out=[]
    for _ in range(512):
        h,hidden=model.gru(model.emb(tok),hidden)
        nxt=int(model.out(h[:,-1]).argmax(-1))
        out.append(nxt)
        if nxt==EOS:break
        tok=torch.tensor([[nxt]])
    return out

def render(tokens,plan):
    fields={
      COPY_A:"a",COPY_B:"b",COPY_R1:"r1",COPY_R2:"r2",
      COPY_A1:"a1",COPY_B1:"b1",COPY_A2:"a2",COPY_B2:"b2",
      COPY_MISSING:"missing_text",
    }
    b=bytearray()
    for t in tokens:
        if 0<=t<=255:b.append(t)
        elif t in fields:b.extend(str(plan.get(fields[t],"")).encode())
        elif t==EOS:break
        else:raise ValueError(t)
    return b.decode()

def expected_complete(plan):
    return (
      f"On {plan['r1']}, {plan['a']} has {plan['a1']}, while {plan['b']} has {plan['b1']}."
      f" On {plan['r2']}, {plan['a']} has {plan['a2']}, while {plan['b']} has {plan['b2']}."
    )

def expected_missing(plan):
    return (
      f"I have insufficient evidence for {plan['missing_text']}."
      " I will not fill the missing fact from memory."
    )

def one_seed(seed,stages):
    rng=random.Random(seed)
    model,params=train_realizer(seed+100)
    a="target"+word(seed*10+1);b="target"+word(seed*10+2)
    r1,r2=rng.sample(RELATIONS,2)
    # Values are seed-specific opaque strings never used in realizer training.
    a1="fact"+word(seed*100+11)
    b1="fact"+word(seed*100+12)
    a2="fact"+word(seed*100+13)
    b2="fact"+word(seed*100+14)
    target=[
      (a,r1,a1,"sourceA1",0.99),(b,r1,b1,"sourceB1",0.99),
      (a,r2,a2,"sourceA2",0.99),(b,r2,b2,"sourceB2",0.99),
    ]
    results=[]
    with tempfile.TemporaryDirectory() as td:
      for stage in stages:
        path=Path(td)/f"ev-{stage}.sqlite"
        store=EvidenceStore(path)
        store.add(make_rows(seed+stage,stage,target))
        plan=plan_compare(store,a,b,r1,r2)
        text=render(generate(model,plan["kind"]),plan)
        complete_exact=text==expected_complete(plan)
        before_deleted=b2 in text
        active_bytes=sum(len(str(plan.get(k,""))) for k in ("a","b","r1","r2","a1","b1","a2","b2"))

        # Causal intervention: delete a fact without retraining/changing the model.
        store.delete(b,r2)
        ablated=plan_compare(store,a,b,r1,r2)
        ablated_text=render(generate(model,ablated["kind"]),ablated)
        missing_exact=ablated_text==expected_missing(ablated)
        no_leak=b2 not in ablated_text
        facts_after=ablated["retrieved_rows"]
        size=store.bytes()
        results.append({
          "facts":stage,
          "cold_bytes":size,
          "retrieved_rows_complete":plan["retrieved_rows"],
          "retrieved_rows_after_delete":facts_after,
          "lookup_ms_complete":plan["lookup_ms"],
          "lookup_ms_after_delete":ablated["lookup_ms"],
          "active_payload_bytes":active_bytes,
          "complete_exact":complete_exact,
          "required_value_present_before_delete":before_deleted,
          "missing_exact":missing_exact,
          "deleted_value_leaked":not no_leak,
          "complete_text":text,
          "ablated_text":ablated_text,
        })
        store.close()
    return {
      "seed":seed,"producer_params":params,
      "entity_a":a,"entity_b":b,"relations":[r1,r2],
      "results":results,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",default="0,1,2")
    ap.add_argument("--stages",default="100,1000,10000,100000")
    ap.add_argument("--out",default="evidence_content_planner_v0.json")
    a=ap.parse_args()
    stages=[int(x) for x in a.stages.split(",")]
    runs=[one_seed(int(s),stages) for s in a.seeds.split(",")]
    passed=all(
      row["complete_exact"]
      and row["required_value_present_before_delete"]
      and row["missing_exact"]
      and not row["deleted_value_leaked"]
      and row["retrieved_rows_complete"]==4
      and row["retrieved_rows_after_delete"]==3
      for run in runs for row in run["results"]
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps({
      "passed":passed,
      "summaries":[{
        "seed":run["seed"],"producer_params":run["producer_params"],
        "stages":[{
          "facts":r["facts"],"cold_bytes":r["cold_bytes"],
          "retrieved":r["retrieved_rows_complete"],
          "active_payload_bytes":r["active_payload_bytes"],
          "lookup_ms":r["lookup_ms_complete"],
          "exact":r["complete_exact"],"ablation_exact":r["missing_exact"],
          "leak":r["deleted_value_leaked"],
        } for r in run["results"]]
      } for run in runs]
    },indent=2))
