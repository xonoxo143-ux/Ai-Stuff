#!/usr/bin/env python3
"""
Alien-math music experiment.
No chroma, key, chord, beat, tempo, MFCC, melody, or genre features are used.
Each frame is only a physical spectral-energy distribution plus relative amplitude.
"""
import csv, json, math, subprocess, urllib.request
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.io import wavfile
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, dendrogram
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
MAN=json.loads((ROOT/"manifest.json").read_text())
AUDIO=ROOT/"audio"; OUT=ROOT/"results"
AUDIO.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
SR=22050; DUR=30; FRAME=2048; HOP=1024; NB=24; K=12; EPS=1e-12
rng=np.random.default_rng(20260908)

def get_audio(x):
    src=AUDIO/f"{x['id']}.src"; wav=AUDIO/f"{x['id']}.wav"
    if not wav.exists():
        if not src.exists():
            print("DOWNLOAD",x["id"],x["title"],flush=True)
            urllib.request.urlretrieve(x["url"],src)
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(src),
                        "-t",str(DUR),"-ac","1","-ar",str(SR),str(wav)],check=True)
    sr,y=wavfile.read(wav)
    y=y.astype(float)
    if y.ndim>1:y=y.mean(1)
    if np.max(np.abs(y)): y/=np.max(np.abs(y))
    n=SR*DUR
    return np.pad(y,(0,max(0,n-len(y))))[:n]

def physics(y):
    n=1+(len(y)-FRAME)//HOP
    fr=np.lib.stride_tricks.as_strided(y,shape=(n,FRAME),
        strides=(y.strides[0]*HOP,y.strides[0])).copy()
    sp=np.abs(np.fft.rfft(fr*np.hanning(FRAME),axis=1))**2
    hz=np.fft.rfftfreq(FRAME,1/SR); edges=np.geomspace(35,SR/2,NB+1)
    B=np.zeros((n,NB))
    for b in range(NB):
        m=(hz>=edges[b])&(hz<edges[b+1])
        if m.any():B[:,b]=sp[:,m].sum(1)
    rel=B/(B.sum(1,keepdims=True)+EPS)
    rms=np.log(np.sqrt(np.mean(fr**2,1))+1e-8)
    rms-=np.median(rms)
    return np.c_[np.log(rel+1e-8),rms]

def trans(s):
    C=np.zeros((K,K))
    for a,b in zip(s[:-1],s[1:]):C[a,b]+=1
    row=C.sum(1,keepdims=True)
    P=np.divide(C,row,out=np.zeros_like(C),where=row>0)
    p=np.bincount(s,minlength=K).astype(float); p/=p.sum()
    return C,P,p

def H(p):
    q=p[p>0]; return float(-(q*np.log(q)).sum())

def topo(D,th):
    n=len(D); A=np.triu(D<th,1); E=int(A.sum())
    par=list(range(n))
    def f(a):
        while par[a]!=a:
            par[a]=par[par[a]]; a=par[a]
        return a
    for a,b in zip(*np.where(A)):
        a=f(int(a)); b=f(int(b))
        if a!=b:par[b]=a
    c=len({f(i) for i in range(n)})
    return c,max(0,E-n+c),E

def metrics(s,q,repscale):
    C,P,p=trans(s); h=H(p)
    flux=p[:,None]*P
    eig=np.sort(np.abs(np.linalg.eigvals(P)))[::-1]
    occ=p[p>0]; E=-np.log(occ+EPS); em=(occ*E).sum()
    v=np.diff(q[:,:3],axis=0); speed=np.linalg.norm(v,axis=1)
    disp=np.linalg.norm(q[-1,:3]-q[0,:3])
    if len(v)>1:
        den=np.linalg.norm(v[:-1],axis=1)*np.linalg.norm(v[1:],axis=1)+EPS
        ang=np.arccos(np.clip((v[:-1]*v[1:]).sum(1)/den,-1,1))
        turn=float(ang.mean()); acc=float(np.linalg.norm(np.diff(v,axis=0),axis=1).mean())
    else:turn=acc=0.
    idx=np.linspace(0,len(q)-1,min(100,len(q))).astype(int); D=squareform(pdist(q[idx,:3]))
    curve=[]
    for m in [.55,.75,1,1.25,1.5]:
        b0,b1,e=topo(D,m*repscale); curve.append([m,b0,b1,e])
    win=max(8,round(4*SR/HOP)); step=max(1,round(.5*SR/HOP)); lh=[]
    for i in range(0,max(1,len(s)-win+1),step):
        z=np.bincount(s[i:i+win],minlength=K).astype(float);z/=max(1,z.sum())
        lh.append(H(z)/math.log(K))
    dh=np.abs(np.diff(lh)); med=np.median(dh) if len(dh) else 0
    mad=np.median(np.abs(dh-med))+EPS if len(dh) else 1
    return {
      "entropy_norm":h/math.log(K),"effective_states":math.exp(h),
      "self_retention":float((p*np.diag(P)).sum()),
      "transition_entropy_norm":float(sum(p[i]*H(P[i]) for i in range(K))/math.log(K)),
      "irreversibility":float(.5*np.abs(flux-flux.T).sum()),
      "metastability_slem":float(eig[1] if len(eig)>1 else 0),
      "free_energy_range":float(E.max()-E.min() if len(E) else 0),
      "heat_capacity":float((occ*(E-em)**2).sum() if len(E) else 0),
      "speed_mean":float(speed.mean()),"speed_cv":float(speed.std()/(speed.mean()+EPS)),
      "acceleration_mean":acc,"turn_angle_mean":turn,
      "tortuosity":float(speed.sum()/(disp+EPS)),
      "phase_jump_count":int(np.sum(dh>med+3*mad)) if len(dh) else 0,
      "topology_beta0_mean":float(np.mean([z[1] for z in curve])),
      "topology_cycle_rank_mean":float(np.mean([z[2] for z in curve])),
      "occupancy":p.tolist(),"transition_matrix":P.tolist(),"topology_curve":curve
    }

# Representation is fitted blind: MAN[i]["genre"] is not read in this section.
raw={x["id"]:get_audio(x) for x in MAN}
feat={i:physics(y) for i,y in raw.items()}
X=np.vstack([feat[x["id"]] for x in MAN])
sc=StandardScaler().fit(X); Z=sc.transform(X)
pc=PCA(6,random_state=20260908).fit(Z); Q=pc.transform(Z)
km=KMeans(K,n_init=30,random_state=20260908).fit(Q)
coords={}; states={}; pos=0
for x in MAN:
    n=len(feat[x["id"]]); q=Q[pos:pos+n]; pos+=n
    coords[x["id"]]=q; states[x["id"]]=km.predict(q)
sub=Q[np.linspace(0,len(Q)-1,min(1500,len(Q))).astype(int),:3]
repscale=float(np.quantile(pdist(sub),.10))

rows=[]; fps=[]; topology=[]
scalar_keys=None
for x in MAN:
    m=metrics(states[x["id"]],coords[x["id"]],repscale)
    if scalar_keys is None:scalar_keys=[k for k,v in m.items() if np.isscalar(v)]
    row={"id":x["id"],"title":x["title"],**{k:m[k] for k in scalar_keys}}
    rows.append(row)
    fps.append(np.r_[[m[k] for k in scalar_keys],m["occupancy"],np.array(m["transition_matrix"]).ravel()])
    for scale,b0,b1,e in m["topology_curve"]:
        topology.append({"id":x["id"],"scale_multiplier":scale,"beta0":b0,"cycle_rank":b1,"edges":e})

F=np.vstack(fps); sd=F.std(0); keep=sd>1e-9
Fs=(F[:,keep]-F[:,keep].mean(0))/sd[keep]
D=squareform(pdist(Fs))

# Only now reveal held-out genre labels for evaluation.
labels=[x["genre"] for x in MAN]
nn=[]
for i,x in enumerate(MAN):
    z=D[i].copy();z[i]=np.inf;j=int(np.argmin(z))
    nn.append({"id":x["id"],"nearest_id":MAN[j]["id"],"distance":float(D[i,j]),
               "same_genre":labels[i]==labels[j]})
within=[];between=[]
for i in range(len(MAN)):
    for j in range(i+1,len(MAN)):
        (within if labels[i]==labels[j] else between).append(D[i,j])
ratio=float(np.mean(within)/np.mean(between))
perm=[]
la=np.array(labels)
for _ in range(5000):
    l=rng.permutation(la);wi=[];be=[]
    for i in range(len(MAN)):
        for j in range(i+1,len(MAN)):
            (wi if l[i]==l[j] else be).append(D[i,j])
    perm.append(np.mean(wi)/np.mean(be))
pval=float((1+np.sum(np.array(perm)<=ratio))/(len(perm)+1))

# Temporal nulls: destroy order while holding the state inventory fixed.
null=[]
for x in MAN:
    s=states[x["id"]]; om=metrics(s,coords[x["id"]],repscale)
    for typ in ["shuffle","block_shuffle","reverse"]:
      R=30 if typ!="reverse" else 1
      for r in range(R):
        if typ=="shuffle":
            t=s.copy();rng.shuffle(t)
        elif typ=="block_shuffle":
            blocks=[s[i:i+20] for i in range(0,len(s),20)]
            order=rng.permutation(len(blocks));t=np.concatenate([blocks[i] for i in order])
        else:t=s[::-1].copy()
        nm=metrics(t,coords[x["id"]],repscale)
        for key in ["self_retention","transition_entropy_norm","irreversibility","metastability_slem","phase_jump_count"]:
            null.append({"id":x["id"],"control":typ,"rep":r,"metric":key,
                         "original":om[key],"control_value":nm[key],"delta":om[key]-nm[key]})

def csvout(name,data):
    with open(OUT/name,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
csvout("track_metrics.csv",rows);csvout("nearest_neighbors.csv",nn)
csvout("topology_curves.csv",topology);csvout("null_controls.csv",null)
with open(OUT/"distance_matrix.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow(["id"]+[x["id"] for x in MAN])
    for i,x in enumerate(MAN):w.writerow([x["id"]]+D[i].tolist())

ev={
 "n_tracks":len(MAN),"genres":sorted(set(labels)),"tracks_per_genre":dict(Counter(labels)),
 "nearest_neighbor_same_genre_accuracy":float(np.mean([z["same_genre"] for z in nn])),
 "random_nn_baseline":1/(len(MAN)-1),"within_mean_distance":float(np.mean(within)),
 "between_mean_distance":float(np.mean(between)),"within_between_ratio":ratio,
 "permutation_p_value":pval,"pca_explained_variance":pc.explained_variance_ratio_.tolist(),
 "recurrence_epsilon":repscale,
 "representation":"24 log-spaced physical spectral-energy bands + relative frame energy; no conventional musical features"
}
(OUT/"evaluation.json").write_text(json.dumps(ev,indent=2))

L=linkage(Fs,method="ward");fig,ax=plt.subplots(figsize=(10,5))
dendrogram(L,labels=[x["id"] for x in MAN],ax=ax)
ax.set_title("Blind clustering: alien-math fingerprints");ax.set_ylabel("Ward distance")
fig.tight_layout();fig.savefig(OUT/"blind_dendrogram.png",dpi=160);plt.close(fig)
emb=PCA(2,random_state=1).fit_transform(Fs);fig,ax=plt.subplots(figsize=(7,6));ax.scatter(emb[:,0],emb[:,1])
for i,x in enumerate(MAN):ax.text(emb[i,0],emb[i,1],x["id"])
ax.set_title("Blind song fingerprints");fig.tight_layout();fig.savefig(OUT/"fingerprint_map.png",dpi=160);plt.close(fig)

report=["# Alien-Math Music Experiment — Run 1","",
"This run deliberately excluded conventional music-theory features and held genre labels out until scoring.","",
f"- Tracks: **{len(MAN)}** across **{len(set(labels))}** genres",
f"- Blind nearest-neighbor same-genre accuracy: **{ev['nearest_neighbor_same_genre_accuracy']:.1%}** (chance {ev['random_nn_baseline']:.1%})",
f"- Within/between fingerprint-distance ratio: **{ratio:.3f}** (lower means held-out genre pairs are closer)",
f"- Permutation p-value: **{pval:.4f}","","## Blind nearest neighbors",""]
for z in nn:report.append(f"- {z['id']} → {z['nearest_id']} — {z['distance']:.3f} — "+("same genre" if z["same_genre"] else "different genre"))
report+=["","## Mathematical lenses","",
"Reaction kinetics: global Markov states, occupancy, metastability, flux irreversibility and transition entropy.",
"Flow geometry: path speed, acceleration, turning and tortuosity through PCA state space.",
"Statistical mechanics: state entropy, effective state count, free-energy spread and heat-capacity analogue.",
"Topology: recurrence-graph connected components (β0) and cycle rank across five spatial scales."]
(OUT/"REPORT.md").write_text("\n".join(report)+"\n")

print("===ALIEN_MATH_RESULT===")
print(json.dumps(ev,sort_keys=True))
print("===NEAREST_NEIGHBORS===")
print(json.dumps(nn,sort_keys=True))
print("===TRACK_METRICS===")
print(json.dumps(rows,sort_keys=True))
