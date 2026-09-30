import argparse,hashlib,itertools,json,os,random,sqlite3,string,tempfile,time
from collections import Counter

REAL=[
 ("set",("set","the","<ATTR>","for","<name>","to","<value>",".")),
 ("set",("store","<value>","as","the","<ATTR>","for","<name>",".")),
 ("set",("for","<name>",",","set","the","<ATTR>","to","<value>",".")),
 ("set",("<name>","'s","<ATTR>","is","<value>",".")),
 ("ask",("what","is","the","<ATTR>","for","<name>","?")),
 ("ask",("tell","me","the","<ATTR>","for","<name>",".")),
 ("ask",("for","<name>",",","what","is","the","<ATTR>","?")),
 ("ask",("give","me","<name>","'s","<ATTR>",".")),
 ("set",("archive","<value>","beneath","<name>","'s","<ATTR>",".")),
 ("ask",("fetch","the","<ATTR>","registered","for","<name>","?")),
]
WRAPS=[("please",","),("for","reference",","),("right","now",","),("in","this","case",",")]
ATTRS=("color","pet","place")
COMMON=["the","for","to","is","me","set","what","give","store","tell","with","from","at","on","in","of","as","record","fetch","archive","registered","beneath","please","now","reference","case","under","show","find","keep","lookup","remember","state","value","item","field","entry","return"]

def codeword(i):
    a=string.ascii_lowercase; out=""
    n=i+1
    while n:
        n,r=divmod(n-1,26); out=a[r]+out
    return "z"+out

RARE=[codeword(i) for i in range(4096)]
PLACE={"<name>","<value>","<ATTR>"}
PUN={".",",","?","'s"}

def literals(pattern):
    return sorted(set(x for x in pattern if x not in PLACE and x not in PUN))

def sig(tup):
    s="\x1f".join(sorted(tup))
    return hashlib.blake2b(s.encode(),digest_size=10).hexdigest()

def pattern_sigs(pattern,k=4):
    ls=literals(pattern)
    combos=list(itertools.combinations(ls,3))
    if not combos:
        combos=list(itertools.combinations(ls,2))
    scored=sorted((hashlib.blake2b(("|".join(c)).encode(),digest_size=8).digest(),sig(c)) for c in combos)
    return [x[1] for x in scored[:k]]

def query_sigs(tokens):
    ls=sorted(set(x for x in tokens if x not in PUN))
    out=set()
    for r in (3,2):
        for c in itertools.combinations(ls,r): out.add(sig(c))
    return list(out)

def distractor(rng):
    # Structurally plausible: common language plus arbitrary learned lexical anchors.
    L=rng.randint(7,11)
    words=rng.sample(COMMON,4)+rng.sample(RARE,3)
    rng.shuffle(words)
    p=[]
    inserts=rng.sample(range(L),2)
    wi=0
    for i in range(L):
        if i==inserts[0]:p.append("<name>")
        elif i==inserts[1]:p.append(rng.choice(["<value>","<ATTR>"]))
        else:
            p.append(words[wi%len(words)]); wi+=1
    p.append(rng.choice([".","?"]))
    return tuple(p)

def render(pattern,rng,wrapped=True):
    name=codeword(rng.randrange(50000,90000))
    value=codeword(rng.randrange(90001,130000))
    attr=rng.choice(ATTRS)
    t=[name if x=="<name>" else value if x=="<value>" else attr if x=="<ATTR>" else x for x in pattern]
    if wrapped and rng.random()<0.5:
        w=rng.choice(WRAPS); t=list(w)+t
    return t

def strip_wrap(tokens):
    t=list(tokens)
    while True:
        hit=None
        for w in WRAPS:
            if tuple(t[:len(w)])==w:hit=w;break
        if not hit:return t
        t=t[len(hit):]

def match(p,tokens):
    if len(p)!=len(tokens):return False
    for a,b in zip(p,tokens):
        if a in ("<name>","<value>"):
            if not b.isalpha():return False
        elif a=="<ATTR>":
            if b not in ATTRS:return False
        elif a!=b:return False
    return True

class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=OFF")
        self.db.execute("CREATE TABLE construction(id INTEGER PRIMARY KEY, mode TEXT, pattern TEXT)")
        self.db.execute("CREATE TABLE posting(sig TEXT, cid INTEGER)")
        self.db.execute("CREATE INDEX posting_sig ON posting(sig)")
        self.db.commit()

    def add_many(self,items):
        c=[]; p=[]
        cur=self.db.cursor()
        for mode,pat in items:
            cur.execute("INSERT INTO construction(mode,pattern) VALUES(?,?)",(mode,json.dumps(pat,separators=(',',':'))))
            cid=cur.lastrowid
            for s in pattern_sigs(pat): p.append((s,cid))
        cur.executemany("INSERT INTO posting(sig,cid) VALUES(?,?)",p)
        self.db.commit()

    def retrieve(self,tokens,limit=64):
        core=strip_wrap(tokens); qs=query_sigs(core)
        if not qs:return None,{"postings":0,"candidates":0,"bytes":0}
        counts=Counter(); returned=0
        CH=300
        for i in range(0,len(qs),CH):
            q=qs[i:i+CH]
            rows=self.db.execute("SELECT sig,cid FROM posting WHERE sig IN (%s)"%(",".join("?"*len(q))),q).fetchall()
            returned+=len(rows)
            for s,cid in rows:counts[cid]+=1
        # At least two independent signatures unless only one candidate exists.
        ranked=[cid for cid,n in counts.most_common() if n>=2][:limit]
        if not ranked and counts: ranked=[counts.most_common(1)[0][0]]
        if not ranked:return None,{"postings":returned,"candidates":0,"bytes":0}
        rows=[]
        for i in range(0,len(ranked),CH):
            q=ranked[i:i+CH]
            rows+=self.db.execute("SELECT id,mode,pattern FROM construction WHERE id IN (%s)"%(",".join("?"*len(q))),q).fetchall()
        loaded=sum(len(x[2]) for x in rows)
        hits=[]
        for cid,mode,js in rows:
            pat=tuple(json.loads(js))
            if match(pat,core):hits.append((cid,mode,pat))
        return (hits[0] if len(hits)==1 else None),{"postings":returned,"candidates":len(rows),"bytes":loaded}

    def all_patterns(self):
        return [(r[0],r[1],tuple(json.loads(r[2]))) for r in self.db.execute("SELECT id,mode,pattern FROM construction")]

def run(seed,stages,queries):
    rng=random.Random(seed)
    with tempfile.TemporaryDirectory() as td:
        path=os.path.join(td,"grammar.sqlite"); s=Store(path)
        # Real constructions first; their ids are 1..len(REAL).
        s.add_many(REAL)
        current=len(REAL); results=[]
        for target in stages:
            if target<current:continue
            batch=[]
            seen=set(p for _,p in REAL)
            while current+len(batch)<target:
                p=distractor(rng)
                if p in seen:continue
                seen.add(p); batch.append(("junk",p))
                if len(batch)>=5000:
                    s.add_many(batch); current+=len(batch); batch=[]; seen=set()
            if batch:s.add_many(batch); current+=len(batch)
            # query only true constructions; random wrappers/args.
            mets=[]; good=0; lat=[]
            for _ in range(queries):
                ridx=rng.randrange(len(REAL)); mode,pat=REAL[ridx]; q=render(pat,rng,True)
                t=time.perf_counter(); hit,m=s.retrieve(q); lat.append((time.perf_counter()-t)*1000)
                good+=bool(hit and hit[1]==mode and hit[2]==pat); mets.append(m)
            # Small sample of true global-scan work count; do not time 100k scans repeatedly.
            fsize=os.path.getsize(path)
            results.append({
              "constructions":target,
              "cold_bytes":fsize,
              "accuracy":good/queries,
              "mean_postings_returned":sum(m["postings"] for m in mets)/queries,
              "p95_postings_returned":sorted(m["postings"] for m in mets)[int(.95*(queries-1))],
              "mean_candidates_loaded":sum(m["candidates"] for m in mets)/queries,
              "p95_candidates_loaded":sorted(m["candidates"] for m in mets)[int(.95*(queries-1))],
              "mean_pattern_bytes_loaded":sum(m["bytes"] for m in mets)/queries,
              "median_lookup_ms":sorted(lat)[len(lat)//2],
              "p95_lookup_ms":sorted(lat)[int(.95*(queries-1))],
              "naive_patterns_examined_per_query":target
            })
        return {"seed":seed,"results":results}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--stages",default="10,1000,10000,100000");ap.add_argument("--queries",type=int,default=500);ap.add_argument("--out",default="construction_scale_v2.json");a=ap.parse_args()
    stages=[int(x) for x in a.stages.split(",")]
    t=time.time(); runs=[run(int(x),stages,a.queries) for x in a.seeds.split(",")]
    out={"wall_seconds":time.time()-t,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
