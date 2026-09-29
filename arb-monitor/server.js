import http from "node:http";
import { URL } from "node:url";

const PORT = Number(process.env.PORT || 3000);
const PAYMENT_LINK = process.env.PAYMENT_LINK || "https://buy.stripe.com/28E00c9XOdPFfCp4IxefC03";
const CONTACT_EMAIL = process.env.CONTACT_EMAIL || "oldcraft541@agentmail.to";
const TARGET_CONTRACTS = 4;
const CACHE_MS = 2500;

let cache = { at: 0, value: null };

function money(n) {
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 10000) / 10000;
}

async function getJson(url, timeoutMs = 6500) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      headers: { "user-agent": "SELF-ROOT-Arb-Monitor/0.1" },
      signal: ctl.signal,
    });
    if (!r.ok) {
      const err = new Error(`HTTP ${r.status}`);
      err.status = r.status;
      throw err;
    }
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}

function kalshiQuote(book) {
  const ob = book?.orderbook_fp;
  const yes = ob?.yes_dollars || [];
  const no = ob?.no_dollars || [];
  if (!yes.length || !no.length) return null;

  const bestYesBid = yes.reduce((a, x) => (+x[0] > +a[0] ? x : a));
  const bestNoBid = no.reduce((a, x) => (+x[0] > +a[0] ? x : a));
  const yesBid = +bestYesBid[0];
  const noBid = +bestNoBid[0];

  return {
    yesBid,
    yesAsk: 1 - noBid,
    yesAskQty: +bestNoBid[1],
    noBid,
    noAsk: 1 - yesBid,
    noAskQty: +bestYesBid[1],
  };
}

function polyQuote(book) {
  const md = book?.marketData;
  const bids = md?.bids || [];
  const offers = md?.offers || [];
  if (!bids.length || !offers.length) return null;

  const bestBid = bids.reduce((a, x) => (+x.px.value > +a.px.value ? x : a));
  const bestAsk = offers.reduce((a, x) => (+x.px.value < +a.px.value ? x : a));
  const yesBid = +bestBid.px.value;
  const yesAsk = +bestAsk.px.value;

  return {
    yesBid,
    yesAsk,
    yesAskQty: +bestAsk.qty,
    noBid: 1 - yesAsk,
    noAsk: 1 - yesBid,
    noAskQty: +bestBid.qty,
  };
}

function kalshiFee(count, p) {
  return Math.ceil((0.07 * count * p * (1 - p)) * 100 - 1e-12) / 100;
}

function polyFee(count, p) {
  return Math.round((0.0695 * count * p * (1 - p)) * 100) / 100;
}

function route(name, kPrice, kQty, pPrice, pQty) {
  const count = Math.min(TARGET_CONTRACTS, Math.floor(kQty), Math.floor(pQty));
  if (count < 1) {
    return { name, executable: false, reason: "insufficient displayed size" };
  }

  const gross = count * (1 - kPrice - pPrice);
  const fees = kalshiFee(count, kPrice) + polyFee(count, pPrice);
  const net = gross - fees;

  return {
    name,
    executable: true,
    contracts: count,
    kalshiPrice: money(kPrice),
    polymarketPrice: money(pPrice),
    combinedCostPerPair: money(kPrice + pPrice),
    gross: money(gross),
    estimatedFees: money(fees),
    estimatedNet: money(net),
    positiveAfterFees: net > 0,
  };
}

async function scan() {
  if (cache.value && Date.now() - cache.at < CACHE_MS) return cache.value;

  const kalshiMarkets = await getJson(
    "https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open&limit=5"
  );
  const km = kalshiMarkets?.markets?.[0];
  if (!km) throw new Error("No open Kalshi BTC 15m market");

  const polySearch = await getJson(
    "https://gateway.polymarket.us/v1/search?query=BTC%20Up%20or%20Down%2015%20min&limit=5&status=MARKET_STATUS_OPEN"
  );
  const events = polySearch?.events || [];
  const pm = events
    .flatMap(e => e.markets || [])
    .find(m =>
      m?.assetPriceTerms?.horizon === "15m" &&
      m?.assetPriceTerms?.indexSymbol === "BRTI" &&
      m?.assetPriceTerms?.windowStart &&
      m?.assetPriceTerms?.windowEnd
    );

  if (!pm) throw new Error("No open Polymarket US BTC 15m market metadata");

  const sameWindow =
    new Date(km.open_time).toISOString() === new Date(pm.assetPriceTerms.windowStart).toISOString() &&
    new Date(km.close_time).toISOString() === new Date(pm.assetPriceTerms.windowEnd).toISOString();

  const sameBenchmark = Math.abs(
    Number(km.floor_strike) - Number(pm.assetPriceTerms.priceToBeat?.value)
  ) < 0.011;

  const [kb, pb] = await Promise.allSettled([
    getJson(`https://external-api.kalshi.com/trade-api/v2/markets/${encodeURIComponent(km.ticker)}/orderbook?depth=10`),
    getJson(`https://gateway.polymarket.us/v1/markets/${encodeURIComponent(pm.slug)}/book`),
  ]);

  const kq = kb.status === "fulfilled" ? kalshiQuote(kb.value) : null;
  const pq = pb.status === "fulfilled" ? polyQuote(pb.value) : null;

  const base = {
    observedAt: new Date().toISOString(),
    sameWindow,
    sameBenchmark,
    kalshi: {
      ticker: km.ticker,
      windowStart: km.open_time,
      windowEnd: km.close_time,
      priceToBeat: Number(km.floor_strike),
      bookAvailable: Boolean(kq),
      quote: kq,
    },
    polymarketUS: {
      slug: pm.slug,
      windowStart: pm.assetPriceTerms.windowStart,
      windowEnd: pm.assetPriceTerms.windowEnd,
      priceToBeat: Number(pm.assetPriceTerms.priceToBeat?.value),
      bookAvailable: Boolean(pq),
      quote: pq,
      bookError: pb.status === "rejected" ? String(pb.reason?.message || pb.reason) : null,
    },
    targetContracts: TARGET_CONTRACTS,
    disclaimer: "Market-data monitor only. Fee calculations are estimates; quotes can disappear before execution."
  };

  if (sameWindow && sameBenchmark && kq && pq) {
    base.routes = [
      route("Kalshi YES + Polymarket US NO", kq.yesAsk, kq.yesAskQty, pq.noAsk, pq.noAskQty),
      route("Kalshi NO + Polymarket US YES", kq.noAsk, kq.noAskQty, pq.yesAsk, pq.yesAskQty),
    ];
    base.best = [...base.routes]
      .filter(x => x.executable)
      .sort((a, b) => (b.estimatedNet ?? -999) - (a.estimatedNet ?? -999))[0] || null;
  } else {
    base.routes = [];
    base.best = null;
  }

  cache = { at: Date.now(), value: base };
  return base;
}

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SELF-ROOT BTC Arb Monitor</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#111;background:#f6f7f8}
body{margin:0}.wrap{max-width:860px;margin:auto;padding:32px 18px 56px}
.card{background:#fff;border:1px solid #ddd;border-radius:18px;padding:20px;margin:14px 0;box-shadow:0 6px 24px #0000000a}
h1{font-size:2rem;margin:.1em 0}.muted{color:#666}.good{color:#087a43;font-weight:700}.bad{color:#9b2c2c;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.kpi{font-size:1.7rem;font-weight:800}.btn{display:inline-block;background:#111;color:#fff;text-decoration:none;padding:13px 18px;border-radius:12px;font-weight:700}
code{background:#f1f3f5;padding:2px 6px;border-radius:6px}.tiny{font-size:.85rem}
</style>
</head>
<body><main class="wrap">
<div class="card">
<div class="muted">SELF-ROOT experimental market monitor</div>
<h1>BTC 15-minute cross-venue arb monitor</h1>
<p>Compares matching Kalshi and Polymarket US BRTI contracts, checks displayed depth, estimates taker fees, and flags only positive fee-adjusted spreads.</p>
<p><a class="btn" href="${PAYMENT_LINK}">Founder access — $15</a></p>
<p class="tiny muted">Founder access includes priority email alerts and the private alert feed as it rolls out. After checkout, reply to <b>${CONTACT_EMAIL}</b> from the receipt email for activation.</p>
</div>
<div class="grid">
<div class="card"><div class="muted">Status</div><div id="status" class="kpi">Loading…</div></div>
<div class="card"><div class="muted">Best est. net / 4 contracts</div><div id="edge" class="kpi">—</div></div>
<div class="card"><div class="muted">Matched contract</div><div id="match" class="kpi">—</div></div>
</div>
<div class="card"><h2>Live preview</h2><div id="details" class="muted">Fetching both venues…</div></div>
<div class="card tiny muted">
This page is market-data research, not investment advice or a promise of profit. Quotes can disappear, books can be unavailable, and fee/settlement behavior can change. No trade is executed by this page.
</div>
</main>
<script>
const fmt=x=>Number.isFinite(x)?'$'+x.toFixed(4):'—';
async function tick(){
  try{
    const r=await fetch('/api/scan',{cache:'no-store'});
    const d=await r.json();
    const ready=d.sameWindow&&d.sameBenchmark&&d.kalshi.bookAvailable&&d.polymarketUS.bookAvailable;
    document.querySelector('#status').textContent=ready?'Watching':'Waiting';
    document.querySelector('#status').className='kpi '+(ready?'good':'');
    document.querySelector('#match').textContent=d.sameWindow&&d.sameBenchmark?'Exact':'Not matched';
    document.querySelector('#match').className='kpi '+(d.sameWindow&&d.sameBenchmark?'good':'bad');
    const best=d.best;
    document.querySelector('#edge').textContent=best?fmt(best.estimatedNet):'—';
    document.querySelector('#edge').className='kpi '+(best?.positiveAfterFees?'good':'');
    const rows=(d.routes||[]).map(x=>`<p><b>${x.name}</b><br>combined cost: ${fmt(x.combinedCostPerPair)} · est. fees: ${fmt(x.estimatedFees)} · est. net: <span class="${x.positiveAfterFees?'good':''}">${fmt(x.estimatedNet)}</span></p>`).join('');
    document.querySelector('#details').innerHTML =
      `Kalshi: <code>${d.kalshi.ticker}</code><br>Polymarket US: <code>${d.polymarketUS.slug}</code><br>Observed: ${new Date(d.observedAt).toLocaleTimeString()}<hr>`+
      (rows||`One or both books are not currently available. The monitor will keep retrying.`);
  }catch(e){
    document.querySelector('#status').textContent='Retrying';
    document.querySelector('#details').textContent=String(e);
  }
}
tick(); setInterval(tick,5000);
</script>
</body></html>`;

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  res.setHeader("x-content-type-options", "nosniff");
  if (u.pathname === "/health") {
    res.writeHead(200, {"content-type":"application/json"});
    return res.end(JSON.stringify({ok:true, service:"self-root-arb-monitor"}));
  }
  if (u.pathname === "/api/scan") {
    try {
      const out = await scan();
      res.writeHead(200, {"content-type":"application/json","cache-control":"no-store"});
      return res.end(JSON.stringify(out));
    } catch (e) {
      res.writeHead(503, {"content-type":"application/json","cache-control":"no-store"});
      return res.end(JSON.stringify({ok:false,error:String(e.message||e),observedAt:new Date().toISOString()}));
    }
  }
  if (u.pathname === "/" || u.pathname === "/index.html") {
    res.writeHead(200, {"content-type":"text/html; charset=utf-8","cache-control":"no-store"});
    return res.end(html);
  }
  res.writeHead(404, {"content-type":"text/plain"});
  res.end("Not found");
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({event:"listening",port:PORT}));
});
