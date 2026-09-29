import express from "express";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";

const PORT = Number(process.env.PORT || 3000);
const PAY_TO = process.env.PAY_TO;
const PRICE = process.env.PRICE_USD || "$0.01";
const SOURCE_URL = process.env.SOURCE_URL || "https://browser-worker-production-c691.up.railway.app/api/scan";
const FACILITATOR_URL = process.env.FACILITATOR_URL || "https://facilitator.heurist.xyz";
const NETWORK = "eip155:8453";

if (!PAY_TO || !/^0x[a-fA-F0-9]{40}$/.test(PAY_TO)) {
  throw new Error("PAY_TO must be a valid EVM payout address");
}

const app = express();
app.disable("x-powered-by");

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    service: "self-root-btc-arb-x402",
    network: NETWORK,
    price: PRICE,
  });
});

app.get("/", (_req, res) => {
  res.type("text/plain").send([
    "SELF-ROOT BTC Arb Monitor — x402 API",
    "",
    "GET /api/scan costs " + PRICE + " USDC over x402 on Base.",
    "GET /openapi.json describes the API.",
    "GET /health is free.",
    "",
    "The underlying monitor compares matching Kalshi and Polymarket US 15-minute BTC BRTI contracts.",
    "Market-data research only; no trade execution or profit guarantee."
  ].join("\n"));
});

const facilitator = new HTTPFacilitatorClient({ url: FACILITATOR_URL });
const resourceServer = new x402ResourceServer(facilitator)
  .register(NETWORK, new ExactEvmScheme());
await resourceServer.initialize();

const paidRoutes = {
  "GET /api/scan": {
    accepts: [
      {
        scheme: "exact",
        price: PRICE,
        network: NETWORK,
        payTo: PAY_TO,
      }
    ],
    description: "Fee-adjusted live comparison of matching Kalshi and Polymarket US BTC 15-minute BRTI books.",
    mimeType: "application/json",
  }
};

app.use(paymentMiddleware(paidRoutes, resourceServer));

app.get("/api/scan", async (_req, res) => {
  try {
    const upstream = await fetch(SOURCE_URL, {
      headers: { "user-agent": "SELF-ROOT-x402/0.1" },
      signal: AbortSignal.timeout(8000),
    });
    const text = await upstream.text();
    res.status(upstream.status);
    res.set("content-type", upstream.headers.get("content-type") || "application/json");
    res.set("cache-control", "no-store");
    res.send(text);
  } catch (err) {
    res.status(502).json({ ok: false, error: "upstream_unavailable" });
  }
});

app.get("/openapi.json", (_req, res) => {
  const base = "https://browser-worker-v2-production.up.railway.app";
  res.json({
    openapi: "3.1.0",
    info: {
      title: "SELF-ROOT BTC Arb Monitor x402 API",
      version: "0.1.0",
      description: "Pay-per-call market-data API for matched Kalshi and Polymarket US BTC 15-minute BRTI contracts. x402 v2, Base mainnet USDC."
    },
    servers: [{ url: base }],
    paths: {
      "/api/scan": {
        get: {
          operationId: "paidBtcArbScan",
          summary: "Buy the current BTC cross-venue market scan",
          description: "Costs " + PRICE + " USDC via x402 on Base. Unpaid requests return HTTP 402 with PAYMENT-REQUIRED.",
          responses: {
            "200": {
              description: "Paid current market scan",
              content: { "application/json": { schema: { type: "object" } } }
            },
            "402": { description: "x402 payment required" },
            "502": { description: "Upstream market monitor unavailable" }
          }
        }
      },
      "/health": {
        get: {
          operationId: "health",
          summary: "Free health check",
          responses: { "200": { description: "Healthy" } }
        }
      }
    },
    "x-self-root": {
      payment: {
        protocol: "x402",
        version: 2,
        network: NETWORK,
        price: PRICE,
        currency: "USDC"
      }
    }
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({
    event: "listening",
    service: "self-root-btc-arb-x402",
    port: PORT,
    network: NETWORK,
    price: PRICE,
    facilitator: FACILITATOR_URL
  }));
});
