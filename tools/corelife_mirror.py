#!/usr/bin/env python3
# CoreLife mirror workflow trigger
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote

import requests
from bs4 import BeautifulSoup

DEFAULT_ROOT = "https://corelifesim.com/"
COMMON = [
    "/manifest.webmanifest", "/manifest.json",
    "/service-worker.js", "/sw.js", "/favicon.ico", "/robots.txt"
]

ASSET_RE = re.compile(
    r'''(?:"|')((?:https?:)?//[^"'<>\\\s]+|/[^"'<>\\\s]+?\.(?:js|mjs|css|json|webmanifest|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf|mp3|wav|ogg|mp4|webm)(?:\?[^"'<>\\\s]*)?)(?:"|')''',
    re.I
)
CSS_RE = re.compile(r'''url\(\s*(['"]?)(.*?)\1\s*\)''', re.I)
IMPORT_RE = re.compile(
    r'''(?:import\s*(?:[^'"]*?\sfrom\s*)?|import\s*\()\s*['"]([^'"]+)['"]''',
    re.I
)

def clean(u):
    return urldefrag(u)[0].strip()

def same_origin(u, origin):
    p = urlparse(u)
    return (p.scheme, p.netloc) == (origin.scheme, origin.netloc)

def local_path(url, out):
    p = urlparse(url)
    path = unquote(p.path or "/")
    if path.endswith("/"):
        path += "index.html"
    dest = out / (path.lstrip("/") or "index.html")
    if p.query:
        h = hashlib.sha1(p.query.encode()).hexdigest()[:10]
        dest = dest.with_name(dest.stem + "__q_" + h + dest.suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest

def refs(url, body, ctype):
    out = set()
    text = body.decode("utf-8", errors="ignore")
    low = ctype.lower()
    path = urlparse(url).path.lower()

    if "html" in low or path in ("", "/"):
        soup = BeautifulSoup(text, "html.parser")
        for tag, attr in [
            ("script","src"), ("link","href"), ("img","src"), ("source","src"),
            ("video","src"), ("audio","src"), ("iframe","src"), ("object","data")
        ]:
            for el in soup.find_all(tag):
                v = el.get(attr)
                if v:
                    out.add(urljoin(url, v))
        for el in soup.find_all(attrs={"srcset": True}):
            for item in el.get("srcset", "").split(","):
                v = item.strip().split(" ")[0]
                if v:
                    out.add(urljoin(url, v))

    if "css" in low or path.endswith(".css"):
        for _, v in CSS_RE.findall(text):
            if v and not v.startswith("data:"):
                out.add(urljoin(url, v))

    if "javascript" in low or "json" in low or path.endswith((".js",".mjs",".json",".webmanifest")):
        for v in IMPORT_RE.findall(text):
            if v.startswith((".", "/", "http://", "https://", "//")):
                out.add(urljoin(url, v))
        for v in ASSET_RE.findall(text):
            out.add(urljoin(url, v))

    return {clean(x) for x in out if x and not x.startswith(("data:","blob:","mailto:","javascript:"))}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_ROOT)
    ap.add_argument("--out", default="corelife_mirror")
    ap.add_argument("--max-files", type=int, default=10000)
    args = ap.parse_args()

    start = clean(args.url)
    origin = urlparse(start)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 CoreLifeMirror/1.0", "Accept":"*/*"})

    q = deque([start] + [urljoin(start, p) for p in COMMON])
    seen, report = set(), []

    while q and len(seen) < args.max_files:
        url = clean(q.popleft())
        if url in seen or not same_origin(url, origin):
            continue
        seen.add(url)
        try:
            r = s.get(url, timeout=30, allow_redirects=True)
            row = {
                "url": url, "final_url": clean(r.url), "status": r.status_code,
                "content_type": r.headers.get("content-type","")
            }
            report.append(row)
            print(f"[{r.status_code}] {url}")
            if r.status_code != 200:
                continue
            dest = local_path(clean(r.url), out)
            dest.write_bytes(r.content)
            row["path"] = str(dest.relative_to(out))
            row["bytes"] = len(r.content)
            for ref in refs(clean(r.url), r.content, row["content_type"]):
                if same_origin(ref, origin) and ref not in seen:
                    q.append(ref)
            time.sleep(0.02)
        except Exception as e:
            report.append({"url":url,"error":repr(e)})
            print(f"[ERR] {url}: {e}", file=sys.stderr)

    (out / "_mirror_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "_source_url.txt").write_text(start + "\n", encoding="utf-8")
    print("Saved", sum(1 for x in report if x.get("status")==200), "resources")

if __name__ == "__main__":
    main()
