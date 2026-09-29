const endpoint = "https://402index.io/api/v1/register";
const payload = {
  url: "https://browser-worker-v2-production.up.railway.app/api/btc-kalshi-polymarket-arbitrage",
  name: "SELF-ROOT BTC Kalshi Polymarket Arb Scan",
  protocol: "x402",
  http_method: "GET",
  description: "Fee-adjusted live comparison of exact-settlement 15-minute BTC BRTI contracts on Kalshi and Polymarket US. Returns matched contract metadata, displayed book depth, estimated fees, and opposing-leg cross-venue routes. Market data only; no trade execution.",
  price_usd: 0.01,
  payment_asset: "USDC",
  payment_network: "Base",
  category: "prediction-markets/arbitrage",
  provider: "SELF-ROOT",
  contact_email: "oldcraft541@agentmail.to"
};

try {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {"content-type":"application/json","user-agent":"SELF-ROOT/0.1"},
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(30000)
  });
  const body = await response.text();
  console.log(JSON.stringify({
    event: "402index-register",
    status: response.status,
    body: body.slice(0, 12000)
  }));
} catch (error) {
  console.log(JSON.stringify({event:"402index-register-error",error:String(error)}));
}
