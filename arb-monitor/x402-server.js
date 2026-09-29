import express from "express";
import { paymentMiddleware, x402ResourceServer } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";

const PORT = Number(process.env.PORT || 3000);
const PUBLIC_ORIGIN = process.env.PUBLIC_ORIGIN || "https://browser-worker-v2-production.up.railway.app";
const CONTACT_EMAIL = process.env.CONTACT_EMAIL || "oldcraft541@agentmail.to";
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

const paidResourceConfig = {
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
};

const paidRoutes = {
  "GET /api/scan": paidResourceConfig,
  "GET /api/btc-kalshi-polymarket-arbitrage": paidResourceConfig,
};

app.use(paymentMiddleware(paidRoutes, resourceServer));

const paidScanHandler = async (req, res) => {
  try {
    const upstream = await fetch(SOURCE_URL, {
      headers: { "user-agent": "SELF-ROOT-x402/0.2" },
      signal: AbortSignal.timeout(8000),
    });
    const text = await upstream.text();
    res.status(upstream.status);
    res.set("cache-control", "no-store");

    const requestId =
      typeof req.query.request_id === "string"
        ? req.query.request_id.slice(0, 64)
        : null;

    if ((upstream.headers.get("content-type") || "").includes("application/json")) {
      try {
        const payload = JSON.parse(text);
        if (requestId) payload.requestId = requestId;
        return res.json(payload);
      } catch {}
    }

    res.set("content-type", upstream.headers.get("content-type") || "text/plain");
    res.send(text);
  } catch (err) {
    res.status(502).json({ ok: false, error: "upstream_unavailable" });
  }
};

app.get("/api/scan", paidScanHandler);
app.get("/api/btc-kalshi-polymarket-arbitrage", paidScanHandler);

app.get("/openapi.json", (_req, res) => {
  res.json({
    openapi: "3.1.0",
    info: {
      title: "SELF-ROOT BTC Arb Monitor x402 API",
      version: "0.2.0",
      description: "Pay-per-call market-data API for matched Kalshi and Polymarket US BTC 15-minute BRTI contracts. x402 v2, Base mainnet USDC.",
      "x-guidance": "Use GET /api/btc-kalshi-polymarket-arbitrage when you need the current fee-adjusted cross-venue comparison for matching Kalshi and Polymarket US 15-minute BTC BRTI contracts. The endpoint costs $0.01 USDC via x402 on Base and returns market data only; it never executes trades.",
      contact: { email: CONTACT_EMAIL }
    },
    servers: [{ url: PUBLIC_ORIGIN }],
    paths: {
      "/api/btc-kalshi-polymarket-arbitrage": {
        get: {
          operationId: "paidBtcArbScan",
          summary: "Buy the current BTC cross-venue market scan",
          description: "Returns matched contract metadata, displayed book depth, estimated fees, and the best observed two-leg cross-venue route. Quotes can change before execution.",
          tags: ["Prediction markets", "Market data", "Arbitrage research"],
          parameters: [
            {
              name: "request_id",
              in: "query",
              required: false,
              description: "Optional client correlation identifier, echoed as requestId in the JSON response.",
              schema: { type: "string", minLength: 1, maxLength: 64 }
            }
          ],
          "x-payment-info": {
            price: { mode: "fixed", currency: "USD", amount: "0.010000" },
            protocols: [{ x402: {} }]
          },
          responses: {
            "200": {
              description: "Paid current market scan",
              content: { "application/json": { schema: { type: "object" } } }
            },
            "402": { description: "Payment Required" },
            "502": { description: "Upstream market monitor unavailable" }
          }
        }
      },
      "/health": {
        get: {
          operationId: "health",
          summary: "Free health check",
          security: [],
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

app.get("/.well-known/x402", (_req, res) => {
  res.json({
    version: 1,
    resources: [PUBLIC_ORIGIN + "/api/btc-kalshi-polymarket-arbitrage"],
    instructions: "Machine-payable BTC 15-minute Kalshi vs Polymarket US BRTI market-data scan. See /openapi.json for pricing and schema."
  });
});

app.get("/llms.txt", (_req, res) => {
  res.type("text/plain").send([
    "# SELF-ROOT BTC Arb Monitor x402 API",
    "",
    "Machine-payable market-data API for matching Kalshi and Polymarket US 15-minute BTC BRTI contracts.",
    "",
    "## Endpoints",
    "- GET /api/btc-kalshi-polymarket-arbitrage — $0.01 USDC via x402 on Base mainnet; current fee-adjusted cross-venue scan",
    "- GET /api/scan — backward-compatible paid alias",
    "- GET /openapi.json — machine-readable OpenAPI 3.1 discovery document",
    "- GET /.well-known/x402 — x402 discovery compatibility document",
    "- GET /health — free liveness check",
    "",
    "The API never places trades and does not promise quote persistence or profit.",
    "Contact: " + CONTACT_EMAIL
  ].join("\n"));
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
