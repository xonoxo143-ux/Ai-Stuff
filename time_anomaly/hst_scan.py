#!/usr/bin/env python3
"""
First-pass HST time-domain anomaly scan for MACS J1149.5+2223.

Calibration target:
  pre-Frontier/CLASH WFC3-IR F160W
  vs Frontier Fields epoch-1 WFC3-IR F160W

The script discovers public STScI HLSP FITS mosaics, downloads a science image
from each epoch, reprojects them to a common WCS, makes a robust difference
image, detects significant residual islands, and writes candidate tables/plots.
"""
from __future__ import annotations
import json, math, os, re, sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy.nddata import Cutout2D
import astropy.units as u
from scipy.ndimage import gaussian_filter, label, find_objects
from reproject import reproject_interp

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(os.environ.get("HST_OUT", "hst_time_anomaly_output"))
DATA = OUT / "data"
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

BASES = {
    "pre_clash": "https://archive.stsci.edu/pub/hlsp/frontier/macs1149/images/hst/clash/",
    "ff_epoch1": "https://archive.stsci.edu/pub/hlsp/frontier/macs1149/images/hst/v1.0-epoch1/",
}
REFSDAL = SkyCoord("11h49m35.08s", "+22d24m10.94s", frame="icrs")

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 HST-Time-Anomaly/0.1"})

def directory_links(url: str):
    r = S.get(url, timeout=45)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("?") or href.startswith("#") or href in ("../", "./"):
            continue
        full = urljoin(url, href)
        if urlparse(full).netloc != urlparse(url).netloc:
            continue
        out.append(full)
    return sorted(set(out))

def crawl(url: str, depth=2):
    q=[(url,0)]
    seen=set()
    files=[]
    while q:
        cur,d=q.pop(0)
        if cur in seen: continue
        seen.add(cur)
        try:
            links=directory_links(cur)
        except Exception as e:
            print("crawl error",cur,repr(e))
            continue
        for x in links:
            low=x.lower()
            if low.endswith((".fits",".fits.gz",".fz")):
                files.append(x)
            elif x.endswith("/") and d < depth and x.startswith(url):
                q.append((x,d+1))
    return sorted(set(files))

def science_score(url: str):
    n=Path(urlparse(url).path).name.lower()
    if "f160w" not in n:
        return -10_000
    bad=("wht","weight","rms","err","ctx","seg","catalog","psf","ivar","exp","mask")
    if any(b in n for b in bad):
        return -5000
    score=0
    if "wfc3" in n: score+=100
    # Match the CLASH reference grid: prefer 30 mas products on both sides.
    if "30mas" in n: score+=60
    if "60mas" in n: score+=30
    if "65mas" in n: score+=25
    if "hffpar" in n: score-=80
    if "bkgdcor" in n: score-=10
    if "_drz" in n or "_drc" in n: score+=30
    if "sci" in n: score+=15
    if n.endswith(".fits"): score+=5
    return score

def choose_science(files):
    ranked=sorted(((science_score(x),x) for x in files), reverse=True)
    good=[x for s,x in ranked if s>0]
    if not good:
        raise RuntimeError("No plausible F160W science mosaic found")
    return good[0], ranked[:20]

def download(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size>0:
        return
    with S.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total=int(r.headers.get("content-length","0"))
        print(f"Downloading {url} ({total/1e6:.1f} MB if known)")
        with open(dest,"wb") as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)

def first_image_hdu(path: Path):
    hdul=fits.open(path, memmap=True)
    for hdu in hdul:
        if getattr(hdu,"data",None) is not None and np.ndim(hdu.data)==2:
            arr=np.asarray(hdu.data, dtype=np.float32)
            w=WCS(hdu.header)
            return hdul, arr, w, hdu.header
    hdul.close()
    raise RuntimeError(f"No 2D image HDU in {path}")

def robust_median_sigma(x):
    v=x[np.isfinite(x)]
    if len(v)==0: return 0.0,1.0
    med=np.median(v)
    mad=np.median(np.abs(v-med))
    sig=1.4826*mad
    return float(med), float(sig if sig>0 else np.std(v) or 1.0)

def normalize_pair(pre, post, mask):
    # Fit post ~= a*pre + b robustly from middle-intensity overlap pixels.
    x=pre[mask].astype(np.float64)
    y=post[mask].astype(np.float64)
    if len(x)>1_000_000:
        rng=np.random.default_rng(12345)
        idx=rng.choice(len(x),1_000_000,replace=False)
        x,y=x[idx],y[idx]
    finite=np.isfinite(x)&np.isfinite(y)
    x,y=x[finite],y[finite]
    if len(x)<1000: return pre,1.0,0.0
    lo,hi=np.percentile(x,[5,99])
    m=(x>lo)&(x<hi)
    x,y=x[m],y[m]
    # iterative least squares clipping
    a,b=1.0,float(np.median(y)-np.median(x))
    for _ in range(4):
        A=np.vstack([x,np.ones_like(x)]).T
        a,b=np.linalg.lstsq(A,y,rcond=None)[0]
        res=y-(a*x+b)
        med,sig=robust_median_sigma(res)
        keep=np.abs(res-med)<4*sig
        x,y=x[keep],y[keep]
        if len(x)<1000: break
    return pre*a+b,float(a),float(b)

def cutout(arr,wcs,coord,size_arcsec=24):
    x,y=wcs.world_to_pixel(coord)
    x=float(np.asarray(x).squeeze())
    y=float(np.asarray(y).squeeze())
    # estimate pix scale from celestial WCS
    try:
        scale=np.mean(np.abs(wcs.proj_plane_pixel_scales()))*3600
    except Exception:
        scale=0.06
    r=max(20,int((size_arcsec/2)/scale))
    xi,yi=int(round(x)),int(round(y))
    y0,y1=max(0,yi-r),min(arr.shape[0],yi+r+1)
    x0,x1=max(0,xi-r),min(arr.shape[1],xi+r+1)
    return arr[y0:y1,x0:x1], (x0,x1,y0,y1)

def stretch(a):
    v=a[np.isfinite(a)]
    if len(v)==0: return (0,1)
    return tuple(np.percentile(v,[2,99.5]))

def main():
    manifest={}
    for name,base in BASES.items():
        print("\nDiscovering",name,base)
        files=crawl(base,depth=2)
        chosen,ranked=choose_science(files)
        manifest[name]={"base":base,"all_fits":files,"chosen":chosen,
                        "top_ranked":[{"score":s,"url":u} for s,u in ranked]}
        print("Chosen:",chosen)
    (OUT/"discovery.json").write_text(json.dumps(manifest,indent=2))

    paths={}
    for name,meta in manifest.items():
        ext=".fits.gz" if meta["chosen"].lower().endswith(".fits.gz") else ".fits"
        p=DATA/f"{name}_f160w{ext}"
        download(meta["chosen"],p)
        paths[name]=p

    h1,pre,wpre,head1=first_image_hdu(paths["pre_clash"])
    h2,post,wpost,head2=first_image_hdu(paths["ff_epoch1"])
    print("full pre shape",pre.shape,"full post shape",post.shape)

    # Work at native 30 mas resolution, but crop around the calibration lens
    # before reprojection so a standard GitHub runner never holds two
    # ~100-million-pixel reprojection workspaces in memory.
    roi_arcsec=float(os.environ.get("HST_ROI_ARCSEC","90"))
    pre_cut=Cutout2D(pre, REFSDAL, (roi_arcsec*u.arcsec, roi_arcsec*u.arcsec),
                     wcs=wpre, mode="partial", fill_value=np.nan, copy=True)
    post_cut=Cutout2D(post, REFSDAL, (roi_arcsec*u.arcsec, roi_arcsec*u.arcsec),
                      wcs=wpost, mode="partial", fill_value=np.nan, copy=True)
    pre=np.asarray(pre_cut.data,dtype=np.float32)
    post=np.asarray(post_cut.data,dtype=np.float32)
    wpre=pre_cut.wcs
    wpost=post_cut.wcs
    print("ROI arcsec",roi_arcsec,"pre shape",pre.shape,"post shape",post.shape)

    # Reproject old image onto Frontier Fields epoch-1 ROI grid.
    if pre.shape==post.shape:
        # Even identical shape does not guarantee identical WCS; compare sample world coords.
        same=False
        try:
            p=np.array([[0,0],[post.shape[1]/2,post.shape[0]/2],[post.shape[1]-1,post.shape[0]-1]])
            sky_pre=wpre.pixel_to_world(p[:,0],p[:,1])
            sky_post=wpost.pixel_to_world(p[:,0],p[:,1])
            sep=sky_pre.separation(sky_post).arcsec
            same=bool(np.nanmax(sep)<0.01)
        except Exception:
            same=False
    else:
        same=False
    if same:
        pre_r=pre.copy()
        footprint=np.isfinite(pre_r).astype(np.float32)
    else:
        pre_r,footprint=reproject_interp((pre,wpre), wpost, shape_out=post.shape, order="bilinear")
        pre_r=pre_r.astype(np.float32)
        footprint=footprint.astype(np.float32)

    overlap=np.isfinite(pre_r)&np.isfinite(post)&(footprint>0.85)
    # Mask a modest border where resampling is fragile.
    border=20
    overlap[:border,:]=False; overlap[-border:,:]=False
    overlap[:,:border]=False; overlap[:,-border:]=False

    pre_n,a,b=normalize_pair(pre_r,post,overlap)
    print("photometric affine scale",a,"offset",b)

    # Slight common smoothing suppresses subpixel drizzle/PSF mismatches.
    fill_pre=np.where(np.isfinite(pre_n),pre_n,0)
    fill_post=np.where(np.isfinite(post),post,0)
    pre_s=gaussian_filter(fill_pre,0.7)
    post_s=gaussian_filter(fill_post,0.7)
    diff=post_s-pre_s
    diff[~overlap]=np.nan

    med,sig=robust_median_sigma(diff[overlap])
    # iterative clip background estimate
    bg=overlap.copy()
    for _ in range(4):
        med,sig=robust_median_sigma(diff[bg])
        bg=overlap & (np.abs(diff-med)<4*sig)
    z=(diff-med)/sig
    z[~overlap]=np.nan
    print("difference background median/sigma",med,sig)

    # Detect positive or negative residual islands.
    det=np.isfinite(z)&(np.abs(z)>=7.0)
    lab,n=label(det)
    objs=find_objects(lab)
    rows=[]
    for i,sl in enumerate(objs, start=1):
        if sl is None: continue
        pix=(lab[sl]==i)
        area=int(pix.sum())
        if area<4 or area>2500: continue
        zz=z[sl][pix]
        yy,xx=np.where(pix)
        ys=yy+sl[0].start
        xs=xx+sl[1].start
        weights=np.abs(zz)
        cx=float(np.average(xs,weights=weights))
        cy=float(np.average(ys,weights=weights))
        try:
            sky=wpost.pixel_to_world(cx,cy)
            ra=float(sky.ra.deg); dec=float(sky.dec.deg)
            dref=float(sky.separation(REFSDAL).arcsec)
        except Exception:
            ra=dec=dref=float("nan")
        rows.append({
            "label":i,"x":cx,"y":cy,"ra_deg":ra,"dec_deg":dec,
            "area_px":area,"peak_abs_sigma":float(np.max(np.abs(zz))),
            "signed_peak_sigma":float(zz[np.argmax(np.abs(zz))]),
            "sum_abs_sigma":float(np.sum(np.abs(zz))),
            "distance_to_refsdal_arcsec":dref,
        })
    df=pd.DataFrame(rows)
    if len(df):
        df=df.sort_values(["peak_abs_sigma","sum_abs_sigma"],ascending=False).reset_index(drop=True)
    df.to_csv(OUT/"candidates.csv",index=False)
    nearby = df[df["distance_to_refsdal_arcsec"] <= 15].copy() if len(df) else df.copy()
    if len(nearby):
        nearby = nearby.sort_values(["distance_to_refsdal_arcsec","peak_abs_sigma"], ascending=[True,False])
    nearby.to_csv(OUT/"refsdal_nearby_candidates.csv", index=False)
    print("candidates",len(df))
    print("candidates within 15 arcsec of published Refsdal position",len(nearby))
    if len(nearby):
        print(nearby.head(30).to_string(index=False))
    elif len(df):
        print(df.head(20).to_string(index=False))

    # Known Refsdal cutout diagnostic
    cp,_=cutout(pre_n,wpost,REFSDAL,26)
    cq,_=cutout(post,wpost,REFSDAL,26)
    cd,_=cutout(diff,wpost,REFSDAL,26)
    fig,axs=plt.subplots(1,3,figsize=(12,4))
    for ax,a0,title in zip(axs,[cp,cq,cd],["Pre-Frontier / CLASH F160W","Frontier Fields epoch 1 F160W","Difference"]):
        lo,hi=stretch(a0)
        ax.imshow(a0,origin="lower",cmap="gray",vmin=lo,vmax=hi)
        ax.set_title(title)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("MACS J1149 — cutout centered on published SN Refsdal position")
    fig.tight_layout()
    fig.savefig(OUT/"refsdal_cutout.png",dpi=180)
    plt.close(fig)

    # Difference overview, downsample for plotting if huge.
    step=max(1,int(max(diff.shape)/1800))
    view=z[::step,::step]
    lim=np.nanpercentile(np.abs(view[np.isfinite(view)]),99.5) if np.isfinite(view).any() else 10
    lim=min(max(lim,5),30)
    fig,ax=plt.subplots(figsize=(8,8))
    ax.imshow(view,origin="lower",cmap="coolwarm",vmin=-lim,vmax=lim)
    ax.set_title(f"F160W temporal difference significance (downsample {step}×)")
    ax.set_xlabel("x"); ax.set_ylabel("y")
    fig.tight_layout()
    fig.savefig(OUT/"difference_significance.png",dpi=160)
    plt.close(fig)

    # Candidate montage.
    if len(df):
        top=df.head(16)
        fig,axs=plt.subplots(4,4,figsize=(12,12))
        for ax,(_,r) in zip(axs.flat,top.iterrows()):
            x,y=int(round(r.x)),int(round(r.y)); rad=28
            y0,y1=max(0,y-rad),min(z.shape[0],y+rad+1)
            x0,x1=max(0,x-rad),min(z.shape[1],x+rad+1)
            c=z[y0:y1,x0:x1]
            ax.imshow(c,origin="lower",cmap="coolwarm",vmin=-15,vmax=15)
            ax.set_title(f"#{int(r.label)} {r.peak_abs_sigma:.1f}σ\n{r.distance_to_refsdal_arcsec:.1f}\" from Refsdal",fontsize=8)
            ax.set_xticks([]); ax.set_yticks([])
        for ax in axs.flat[len(top):]: ax.axis("off")
        fig.tight_layout()
        fig.savefig(OUT/"top_candidates.png",dpi=180)
        plt.close(fig)

    summary={
        "target":"MACS J1149.5+2223",
        "filter":"HST WFC3/IR F160W",
        "pre_url":manifest["pre_clash"]["chosen"],
        "post_url":manifest["ff_epoch1"]["chosen"],
        "roi_arcsec":roi_arcsec,
        "post_shape":list(post.shape),
        "photometric_scale_a":a,
        "photometric_offset_b":b,
        "difference_median":med,
        "difference_sigma":sig,
        "threshold_sigma":7.0,
        "candidate_count":int(len(df)),
        "refsdal_nearby_candidate_count":int(len(nearby)),
        "nearest_refsdal_candidate": (
            nearby.iloc[0].to_dict() if len(nearby)
            else (df.sort_values("distance_to_refsdal_arcsec").iloc[0].to_dict() if len(df) else None)
        ),
        "published_refsdal_ra_deg":float(REFSDAL.ra.deg),
        "published_refsdal_dec_deg":float(REFSDAL.dec.deg),
    }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
    h1.close(); h2.close()

if __name__=="__main__":
    main()
