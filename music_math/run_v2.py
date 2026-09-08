#!/usr/bin/env python3
"""Alien-math music experiment v2.

Treats audio as a physical dynamical system. Conventional MIR/music-theory features are
intentionally excluded: no key, pitch-class/chroma, chords, beats, BPM, MFCCs, melody,
or genre inputs. Category labels are revealed only after fingerprints are complete.
"""
from __future__ import annotations
import csv, json, math, subprocess, urllib.request, itertools
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.io import wavfile
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, dendrogram
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from ripser import ripser
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'manifest_v2.json'; AUDIO=ROOT/'audio_v2'; OUT=ROOT/'results_v2'
AUDIO.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
SR=22050; MAX_DUR=30.0; FRAME=2048; HOP=1024; N_BANDS=24; K=16; EPS=1e-12
RNG=np.random.default_rng(20260908)

def run(cmd,capture=False):
    return subprocess.run(cmd,check=True,text=True,capture_output=capture)

def download_decode(item):
    src=AUDIO/f"{item['id']}.src"; wav=AUDIO/f"{item['id']}.wav"
    if not src.exists():
        print('DOWNLOAD',item['id'],item['title'],flush=True)
        urllib.request.urlretrieve(item['url'],src)
    if not wav.exists():
        try:
            p=run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(src)],True)
            dur=float(p.stdout.strip())
        except Exception:
            dur=MAX_DUR
        start=max(0.0,(dur-MAX_DUR)/2.0) if np.isfinite(dur) else 0.0
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',f'{start:.3f}','-i',str(src),
             '-t',str(MAX_DUR),'-ac','1','-ar',str(SR),str(wav)])
    sr,y=wavfile.read(wav)
    if y.ndim>1:y=y.mean(axis=1)
    if np.issubdtype(y.dtype,np.integer):
        info=np.iinfo(y.dtype);y=y.astype(np.float64)/max(abs(info.min),info.max)
    else:y=y.astype(np.float64)
    y-=y.mean();y/=np.max(np.abs(y))+EPS
    return y,float(len(y)/sr)

def spectral_physics(y):
    if len(y)<FRAME:y=np.pad(y,(0,FRAME-len(y)))
    n=1+(len(y)-FRAME)//HOP
    frames=np.lib.stride_tricks.as_strided(y,shape=(n,FRAME),strides=(y.strides[0]*HOP,y.strides[0])).copy()
    spec=np.abs(np.fft.rfft(frames*np.hanning(FRAME),axis=1))**2
    hz=np.fft.rfftfreq(FRAME,1/SR);edges=np.geomspace(35,SR/2,N_BANDS+1)
    b=np.zeros((n,N_BANDS))
    for i in range(N_BANDS):
        m=(hz>=edges[i])&(hz<edges[i+1])
        if m.any():b[:,i]=spec[:,m].sum(axis=1)
    rel=b/(b.sum(axis=1,keepdims=True)+EPS)
    rms=np.sqrt(np.mean(frames**2,axis=1));lr=np.log(rms+1e-8);lr-=np.median(lr)
    return np.c_[np.log(rel+1e-8),lr]

def phase_randomize(y):
    Y=np.fft.rfft(y);ph=RNG.uniform(0,2*np.pi,len(Y));ph[0]=np.angle(Y[0])
    if len(y)%2==0:ph[-1]=np.angle(Y[-1])
    z=np.fft.irfft(np.abs(Y)*np.exp(1j*ph),n=len(y));z-=z.mean();z/=np.max(np.abs(z))+EPS
    return z

def shannon(p):
    q=np.asarray(p,float);q=q[q>0]
    return float(-(q*np.log(q)).sum())

def jsd(p,q):
    p=np.asarray(p,float);q=np.asarray(q,float);p/=p.sum()+EPS;q/=q.sum()+EPS;m=(p+q)/2
    def kl(a,b):
        z=a>0;return float(np.sum(a[z]*np.log((a[z]+EPS)/(b[z]+EPS))))
    return .5*kl(p,m)+.5*kl(q,m)

def transition_model(s):
    C=np.zeros((K,K),float)
    for a,b in zip(s[:-1],s[1:]):C[a,b]+=1
    row=C.sum(1,keepdims=True);P=np.divide(C,row,out=np.zeros_like(C),where=row>0)
    p=np.bincount(s,minlength=K).astype(float);p/=p.sum()+EPS
    return C,P,p

def triplet_irreversibility(s):
    if len(s)<3:return 0.0
    c=np.zeros(K**3,float)
    for a,b,d in zip(s[:-2],s[1:-1],s[2:]):c[(int(a)*K+int(b))*K+int(d)]+=1
    c/=c.sum()+EPS;rev=np.empty_like(c)
    for a in range(K):
      for b in range(K):
       for d in range(K):rev[(a*K+b)*K+d]=c[(d*K+b)*K+a]
    return float(jsd(c,rev)/math.log(2))

PERM_INDEX={a:i for i,a in enumerate(itertools.permutations(range(5)))}
def permutation_entropy(x,m=5,tau=1):
    x=np.asarray(x,float);n=len(x)-(m-1)*tau
    if n<5:return 0.0,0.0
    counts=Counter(tuple(np.argsort(x[i:i+m*tau:tau],kind='stable')) for i in range(n))
    p=np.array(list(counts.values()),float);p/=p.sum();h=shannon(p)/math.log(math.factorial(m))
    M=math.factorial(m);full=np.zeros(M,float)
    for pat,v in counts.items():full[PERM_INDEX[pat]]=v/n
    u=np.ones(M)/M;j=jsd(full,u);delta=np.zeros(M);delta[0]=1;jmax=jsd(delta,u)
    return float(h),float(h*j/(jmax+EPS))

def hurst_rs(x):
    x=np.asarray(x,float);x=(x-x.mean())/(x.std()+EPS);vals=[]
    for n in [8,16,32,64,128]:
        if len(x)<2*n:continue
        rs=[]
        for i in range(0,len(x)-n+1,n):
            z=x[i:i+n];dev=z-z.mean();cum=np.cumsum(dev);R=cum.max()-cum.min();S=z.std()
            if S>EPS and R>0:rs.append(R/S)
        if rs:vals.append((math.log(n),math.log(np.mean(rs))))
    if len(vals)<2:return float('nan')
    return float(np.polyfit([a for a,b in vals],[b for a,b in vals],1)[0])

def time_asymmetry(x,tau):
    x=np.asarray(x,float);x=(x-x.mean())/(x.std()+EPS)
    if len(x)<=tau:return 0.0
    a=x[:-tau];b=x[tau:]
    return float(np.mean(a*a*b-a*b*b))

def line_lengths_bool(R,kind='diag'):
    lengths=[];n=R.shape[0]
    arrays=[np.diag(R,k=k) for k in range(-n+1,n) if k!=0] if kind=='diag' else [R[:,j] for j in range(n)]
    for arr in arrays:
        runlen=0
        for v in arr:
            if v:runlen+=1
            elif runlen:lengths.append(runlen);runlen=0
        if runlen:lengths.append(runlen)
    return lengths

def normalize_traj(coords,n):
    idx=np.linspace(0,len(coords)-1,min(n,len(coords))).astype(int);q=coords[idx,:3].copy()
    q-=q.mean(0);q/=np.sqrt(np.mean(np.sum(q*q,axis=1)))+EPS
    return q

def rqa(coords,eps):
    q=normalize_traj(coords,180);n=len(q);D=squareform(pdist(q));R=(D<eps);np.fill_diagonal(R,False)
    rec=float(R.sum());rr=rec/(n*(n-1)+EPS)
    dl=[v for v in line_lengths_bool(R,'diag') if v>=2];vl=[v for v in line_lengths_bool(R,'vert') if v>=2]
    return dict(rqa_recurrence_rate=float(rr),rqa_determinism=float(sum(dl)/(rec+EPS)),
                rqa_mean_diag=float(np.mean(dl) if dl else 0),rqa_max_diag=float(max(dl) if dl else 0),
                rqa_laminarity=float(sum(vl)/(rec+EPS)),rqa_trapping_time=float(np.mean(vl) if vl else 0))

def persistence(coords):
    q=normalize_traj(coords,120);dg=ripser(q,maxdim=1)['dgms'];h1=dg[1]
    life=(h1[:,1]-h1[:,0]) if len(h1) else np.array([]);life=life[np.isfinite(life)]
    if not len(life):return dict(topo_h1_count=0,topo_h1_sig_count=0,topo_h1_total=0.0,topo_h1_max=0.0,topo_h1_entropy=0.0)
    p=life/(life.sum()+EPS)
    return dict(topo_h1_count=int(len(life)),topo_h1_sig_count=int(np.sum(life>.15)),
                topo_h1_total=float(life.sum()),topo_h1_max=float(life.max()),topo_h1_entropy=float(shannon(p)))

def metrics(states,coords,rqa_eps,do_topology=True):
    C,P,p=transition_model(states);H=shannon(p);rowh=np.array([shannon(r) for r in P])
    flux=p[:,None]*P;eig=np.sort(np.abs(np.linalg.eigvals(P)))[::-1];occ=p[p>0];E=-np.log(occ+EPS);em=np.sum(occ*E)
    q=coords[:,:3];v=np.diff(q,axis=0);speed=np.linalg.norm(v,axis=1);disp=np.linalg.norm(q[-1]-q[0])
    if len(v)>1:
        den=np.linalg.norm(v[:-1],axis=1)*np.linalg.norm(v[1:],axis=1)+EPS
        ang=np.arccos(np.clip(np.sum(v[:-1]*v[1:],axis=1)/den,-1,1));acc=np.linalg.norm(np.diff(v,axis=0),axis=1)
    else:ang=np.array([0.]);acc=np.array([0.])
    pc1=q[:,0];pe,complexity=permutation_entropy(pc1)
    out=dict(entropy_norm=float(H/math.log(K)),effective_states=float(math.exp(H)),
      self_retention=float(np.sum(p*np.diag(P))),transition_entropy_norm=float(np.sum(p*rowh)/math.log(K)),
      detailed_balance_violation=float(.5*np.abs(flux-flux.T).sum()),metastability_slem=float(eig[1] if len(eig)>1 else 0),
      free_energy_range=float(E.max()-E.min() if len(E) else 0),heat_capacity=float(np.sum(occ*(E-em)**2) if len(E) else 0),
      triplet_irreversibility=triplet_irreversibility(states),permutation_entropy=pe,statistical_complexity=complexity,
      hurst_pc1=hurst_rs(pc1),time_asymmetry_tau1=time_asymmetry(pc1,1),time_asymmetry_tau5=time_asymmetry(pc1,5),
      speed_mean=float(speed.mean()),speed_cv=float(speed.std()/(speed.mean()+EPS)),
      acceleration_mean=float(acc.mean()),turn_angle_mean=float(ang.mean()),tortuosity=float(speed.sum()/(disp+EPS)))
    out.update(rqa(coords,rqa_eps))
    if do_topology:out.update(persistence(coords))
    return out,p,P

def global_rqa_epsilon(coords):
    ds=[]
    for q0 in coords.values():
        q=normalize_traj(q0,100);d=pdist(q);ds.append(d[np.linspace(0,len(d)-1,min(300,len(d))).astype(int)])
    return float(np.quantile(np.concatenate(ds),.10))

def null_orderings(states,coords,reps=10,block=20):
    n=len(states)
    for r in range(reps):
        order=RNG.permutation(n);yield 'shuffle',r,states[order],coords[order]
        blocks=[np.arange(i,min(i+block,n)) for i in range(0,n,block)];bo=RNG.permutation(len(blocks));order=np.concatenate([blocks[i] for i in bo])
        yield 'block_shuffle',r,states[order],coords[order]
    order=np.arange(n-1,-1,-1);yield 'reverse',0,states[order],coords[order]

def write_csv(path,rows):
    if not rows:return
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def eval_fingerprint(F,manifest,name):
    Fs=StandardScaler().fit_transform(F);D=squareform(pdist(Fs));cats=np.array([x['category'] for x in manifest]);N=len(cats)
    nn=[]
    for i,x in enumerate(manifest):
        z=D[i].copy();z[i]=np.inf;j=int(np.argmin(z));nn.append((i,j,float(D[i,j]),bool(cats[i]==cats[j])))
    chance=float(np.mean([(np.sum(cats==c)-1)/(N-1) for c in cats]))
    within=[];between=[]
    for i in range(N):
      for j in range(i+1,N):(within if cats[i]==cats[j] else between).append(D[i,j])
    ratio=float(np.mean(within)/np.mean(between));perm=[]
    for _ in range(2000):
        lab=RNG.permutation(cats);wi=[];be=[]
        for i in range(N):
          for j in range(i+1,N):(wi if lab[i]==lab[j] else be).append(D[i,j])
        perm.append(np.mean(wi)/np.mean(be))
    pval=float((1+np.sum(np.asarray(perm)<=ratio))/(len(perm)+1))
    try:sil=float(silhouette_score(D,cats,metric='precomputed'))
    except Exception:sil=float('nan')
    cl=AgglomerativeClustering(n_clusters=len(set(cats)),linkage='ward').fit_predict(Fs)
    ari=float(adjusted_rand_score(cats,cl));nmi=float(normalized_mutual_info_score(cats,cl))
    embp=PCA(min(8,Fs.shape[1]),random_state=20260908).fit(Fs);emb=embp.transform(Fs)
    result=dict(name=name,nearest_neighbor_same_category=float(np.mean([x[3] for x in nn])),chance_nn=chance,
                within_between_ratio=ratio,permutation_p_value=pval,silhouette_by_category=sil,
                ARI_8clusters=ari,NMI_8clusters=nmi)
    return result,Fs,D,nn,cl,embp,emb

def main():
    manifest=json.loads(MANIFEST.read_text());raw={};dur={};feat={}
    for x in manifest:
        y,d=download_decode(x);raw[x['id']]=y;dur[x['id']]=d;feat[x['id']]=spectral_physics(y)
    manifest=[x for x in manifest if dur[x['id']]>=5.0 and len(feat[x['id']])>=20]
    X=np.vstack([feat[x['id']] for x in manifest]);sc=StandardScaler().fit(X);Z=sc.transform(X)
    pc=PCA(8,random_state=20260908).fit(Z);Q=pc.transform(Z);km=KMeans(K,n_init=20,random_state=20260908).fit(Q)
    coords={};states={};pos=0
    for x in manifest:
        n=len(feat[x['id']]);q=Q[pos:pos+n];pos+=n;coords[x['id']]=q;states[x['id']]=km.predict(q)
    rqeps=global_rqa_epsilon(coords)

    rows=[];occupancies=[];eigparts=[];metric_names=None
    for x in manifest:
        m,p,P=metrics(states[x['id']],coords[x['id']],rqeps,True)
        if metric_names is None:metric_names=list(m)
        rows.append({'id':x['id'],'title':x['title'],'duration_s':dur[x['id']],**m})
        occupancies.append(p);vals=np.sort(np.abs(np.linalg.eigvals(P)))[::-1][:8]
        eigparts.append(np.pad(vals,(0,max(0,8-len(vals))))[:8].real)
    scalar=np.array([[r[k] for k in metric_names] for r in rows],float)
    for j in range(scalar.shape[1]):
        z=np.isfinite(scalar[:,j]);scalar[~z,j]=np.median(scalar[z,j]) if z.any() else 0
    network=np.c_[scalar,np.vstack(occupancies),np.vstack(eigparts)]
    es,Fs,Ds,nns,cls,pca_s,embs=eval_fingerprint(scalar,manifest,'scalar_phenotype')
    en,Fn,Dn,nnn,cln,pca_n,embn=eval_fingerprint(network,manifest,'reaction_network_phenotype')

    load=[]
    for k in range(min(5,len(pca_s.components_))):
        for j,name in enumerate(metric_names):load.append({'axis':k+1,'metric':name,'loading':float(pca_s.components_[k,j])})
    embed=[]
    for i,x in enumerate(manifest):
        embed.append({'id':x['id'],'category':x['category'],'cluster_blind':int(cls[i]),
                      **{f'axis{k+1}':float(embs[i,k]) for k in range(min(5,embs.shape[1]))}})
    nnrows=[]
    for tag,ns in [('scalar',nns),('network',nnn)]:
        for i,j,d,same in ns:nnrows.append({'fingerprint':tag,'id':manifest[i]['id'],'nearest_id':manifest[j]['id'],'distance':d,'same_category':same})

    null=[];nullkeys=['self_retention','transition_entropy_norm','metastability_slem','triplet_irreversibility',
      'permutation_entropy','statistical_complexity','hurst_pc1','time_asymmetry_tau1','time_asymmetry_tau5',
      'rqa_determinism','rqa_laminarity','rqa_mean_diag']
    row_by_id={r['id']:r for r in rows}
    for x in manifest:
        om,_,_=metrics(states[x['id']],coords[x['id']],rqeps,False)
        for kind,r,s,q in null_orderings(states[x['id']],coords[x['id']]):
            nm,_,_=metrics(s,q,rqeps,False)
            for key in nullkeys:null.append({'id':x['id'],'control':kind,'rep':r,'metric':key,'original':om[key],'control_value':nm[key],'delta':om[key]-nm[key]})
        yp=phase_randomize(raw[x['id']]);fp=spectral_physics(yp);qp=pc.transform(sc.transform(fp));sp=km.predict(qp);pm,_,_=metrics(sp,qp,rqeps,True)
        for key in nullkeys+['topo_h1_total','topo_h1_max','topo_h1_sig_count']:
            original=om[key] if key in om else row_by_id[x['id']][key]
            null.append({'id':x['id'],'control':'phase_randomized','rep':0,'metric':key,'original':original,'control_value':pm[key],'delta':original-pm[key]})

    summary=[]
    for control in sorted(set(r['control'] for r in null)):
      for key in sorted(set(r['metric'] for r in null if r['control']==control)):
        z=[r['delta'] for r in null if r['control']==control and r['metric']==key]
        summary.append({'control':control,'metric':key,'mean_delta':float(np.mean(z)),
                        'median_delta':float(np.median(z)),'positive_fraction':float(np.mean(np.array(z)>0)),'n':len(z)})

    write_csv(OUT/'track_metrics.csv',rows);write_csv(OUT/'axis_loadings.csv',load);write_csv(OUT/'track_embedding.csv',embed)
    write_csv(OUT/'nearest_neighbors.csv',nnrows);write_csv(OUT/'null_controls.csv',null);write_csv(OUT/'null_summary.csv',summary)
    with open(OUT/'scalar_distance_matrix.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['id']+[x['id'] for x in manifest])
        for i,x in enumerate(manifest):w.writerow([x['id']]+Ds[i].tolist())
    evaluation={'n_tracks':len(manifest),'category_counts':dict(Counter(x['category'] for x in manifest)),
                'representation':'24 physical log-spaced spectral-energy bands + relative energy; no conventional music features',
                'state_pca_variance':pc.explained_variance_ratio_.tolist(),'rqa_global_epsilon':rqeps,
                'scalar_evaluation':es,'network_evaluation':en}
    (OUT/'evaluation.json').write_text(json.dumps(evaluation,indent=2))

    fig,ax=plt.subplots(figsize=(9,7));ax.scatter(embs[:,0],embs[:,1],s=18)
    for i,x in enumerate(manifest):ax.text(embs[i,0],embs[i,1],x['id'],fontsize=6)
    ax.set_title('Alien-math scalar phenotype (blind IDs)');ax.set_xlabel('Alien axis 1');ax.set_ylabel('Alien axis 2')
    fig.tight_layout();fig.savefig(OUT/'alien_map_blind.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,7));cats=sorted(set(x['category'] for x in manifest))
    for c in cats:
        ii=[i for i,x in enumerate(manifest) if x['category']==c];ax.scatter(embs[ii,0],embs[ii,1],s=22,label=c)
    ax.legend(fontsize=7,ncol=2);ax.set_title('Same alien map after category labels are revealed')
    ax.set_xlabel('Alien axis 1');ax.set_ylabel('Alien axis 2');fig.tight_layout();fig.savefig(OUT/'alien_map_revealed.png',dpi=170);plt.close(fig)
    L=linkage(Fs,method='ward');fig,ax=plt.subplots(figsize=(14,6));dendrogram(L,labels=[x['id'] for x in manifest],leaf_font_size=6,ax=ax)
    ax.set_title('Blind Ward hierarchy of scalar alien phenotypes');fig.tight_layout();fig.savefig(OUT/'alien_dendrogram.png',dpi=170);plt.close(fig)

    axis_lines=[]
    for k in range(min(5,len(pca_s.components_))):
        order=np.argsort(np.abs(pca_s.components_[k]))[::-1][:6]
        axis_lines.append({'axis':k+1,'variance':float(pca_s.explained_variance_ratio_[k]),
                           'top':[(metric_names[j],float(pca_s.components_[k,j])) for j in order]})
    interesting=sorted(summary,key=lambda r:abs(r['median_delta']),reverse=True)[:20]
    result={'evaluation':evaluation,'alien_axes':axis_lines,'strongest_null_effects':interesting}
    (OUT/'headline.json').write_text(json.dumps(result,indent=2))
    report=['# Alien-Math Music Experiment — Run 2','',
      f"Analyzed **{len(manifest)}** tracks. Category labels were withheld until post-hoc evaluation.",'',
      '## Blind category recovery','',
      f"Scalar phenotype NN: **{es['nearest_neighbor_same_category']:.1%}** vs chance **{es['chance_nn']:.1%}**; permutation p={es['permutation_p_value']:.4g}.",
      f"Reaction-network phenotype NN: **{en['nearest_neighbor_same_category']:.1%}** vs chance **{en['chance_nn']:.1%}**; permutation p={en['permutation_p_value']:.4g}.",
      '','## Alien axes','']
    for a in axis_lines:report.append(f"- Axis {a['axis']} ({a['variance']:.1%} variance): "+', '.join(f"{n} ({v:+.2f})" for n,v in a['top']))
    report+=['','## Strong temporal-null effects','']
    for z in interesting[:12]:report.append(f"- {z['control']} / {z['metric']}: median original-control {z['median_delta']:+.4f} ({z['positive_fraction']:.0%} positive)")
    report+=['','Persistent homology is computed on the state-space point cloud and is intentionally not expected to change under simple temporal shuffling; RQA and order statistics are the temporal geometry tests.']
    (OUT/'REPORT.md').write_text('\n'.join(report)+'\n')
    print('===ALIEN_V2_HEADLINE===');print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
