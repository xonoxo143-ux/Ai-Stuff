import { createHmac, timingSafeEqual } from "node:crypto";

const STRIPE_API_BASE = process.env.STRIPE_API_BASE || "https://api.stripe.com";
const stripeSecretKey = process.env.STRIPE_SECRET_KEY || "";
const stripeWebhookSecret = process.env.STRIPE_WEBHOOK_SECRET || "";
const stripePaymentsEnabled = process.env.STRIPE_PAYMENTS_ENABLED === "true";
const stripeBillingEnabled = process.env.STRIPE_BILLING_ENABLED === "true";
const stripeConnectEnabled = process.env.STRIPE_CONNECT_ENABLED === "true";
const stripeCryptoOnrampEnabled = process.env.STRIPE_CRYPTO_ONRAMP_ENABLED === "true";
const stripeBillingPriceId = process.env.STRIPE_BILLING_PRICE_ID || "";
const stripeBillingSuccessUrl = process.env.STRIPE_BILLING_SUCCESS_URL || "";
const stripeBillingCancelUrl = process.env.STRIPE_BILLING_CANCEL_URL || "";
const stripeConnectReturnUrl = process.env.STRIPE_CONNECT_RETURN_URL || "";
const stripeConnectRefreshUrl = process.env.STRIPE_CONNECT_REFRESH_URL || "";
const stripeOnrampReturnUrl = process.env.STRIPE_CRYPTO_ONRAMP_RETURN_URL || "";

function encodeStripeForm(obj, prefix = "", out = new URLSearchParams()) {
  for (const [key, value] of Object.entries(obj || {})) {
    if (value === undefined || value === null) continue;
    const name = prefix ? \`\${prefix}[\${key}]\` : key;
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (item && typeof item === "object") {
          encodeStripeForm(item, \`\${name}[\${index}]\`, out);
        } else {
          out.append(\`\${name}[\${index}]\`, String(item));
        }
      });
    } else if (value && typeof value === "object") {
      encodeStripeForm(value, name, out);
    } else {
      out.append(name, String(value));
    }
  }
  return out;
}

async function stripeRequest(path, { method = "GET", body = null } = {}) {
  if (!stripeSecretKey) throw new Error("stripe_secret_key_missing");
  const headers = {
    authorization: \`Bearer \${stripeSecretKey}\`,
    accept: "application/json",
  };
  let requestBody;
  if (body !== null) {
    headers["content-type"] = "application/x-www-form-urlencoded";
    requestBody = encodeStripeForm(body).toString();
  }
  const response = await fetch(\`\${STRIPE_API_BASE}\${path}\`, {
    method,
    headers,
    body: requestBody,
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try {
    payload = raw ? JSON.parse(raw) : {};
  } catch {
    payload = { raw: raw.slice(0, 2000) };
  }
  if (!response.ok) {
    const detail =
      payload?.error?.message ||
      payload?.message ||
      payload?.error ||
      \`HTTP \${response.status}\`;
    const err = new Error(\`stripe_http_\${response.status}: \${String(detail).slice(0, 400)}\`);
    err.status = response.status;
    throw err;
  }
  return payload;
}

function verifyStripeSignature(rawBody, header, toleranceSeconds = 300) {
  if (!stripeWebhookSecret || typeof header !== "string") return false;
  const parts = header.split(",").map((x) => x.trim());
  const timestamp = parts.find((x) => x.startsWith("t="))?.slice(2);
  const signatures = parts
    .filter((x) => x.startsWith("v1="))
    .map((x) => x.slice(3));
  if (!timestamp || !signatures.length) return false;

  const ts = Number(timestamp);
  if (!Number.isFinite(ts)) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - ts) > toleranceSeconds) return false;

  const expected = createHmac("sha256", stripeWebhookSecret)
    .update(\`\${timestamp}.\`)
    .update(rawBody)
    .digest("hex");

  return signatures.some((sig) => {
    if (!/^[a-f0-9]{64}$/i.test(sig)) return false;
    const a = Buffer.from(expected, "hex");
    const b = Buffer.from(sig, "hex");
    return a.length === b.length && timingSafeEqual(a, b);
  });
}

export function createStripeAdapter({ rememberEvent }) {
  const state = {
    lastWebhookAt: null,
    lastWebhookType: null,
    lastError: null,
    lastPaymentLinkAt: null,
    lastPaymentLinkId: null,
    lastBillingCheckoutAt: null,
  };

  function summary() {
    return {
      mode: "runtime_adapter",
      configured: Boolean(stripeSecretKey),
      webhookConfigured: Boolean(stripeWebhookSecret),
      paymentsEnabled: stripePaymentsEnabled,
      billingEnabled: stripeBillingEnabled,
      connectEnabled: stripeConnectEnabled,
      cryptoOnrampEnabled: stripeCryptoOnrampEnabled,
      billingPriceConfigured: Boolean(stripeBillingPriceId),
      lastWebhookAt: state.lastWebhookAt,
      lastWebhookType: state.lastWebhookType,
      lastPaymentLinkAt: state.lastPaymentLinkAt,
      lastPaymentLinkId: state.lastPaymentLinkId,
      lastBillingCheckoutAt: state.lastBillingCheckoutAt,
      lastError: state.lastError,
    };
  }

  async function handle(req, res, url, { json, readBody, readJson, authorized }) {
    if (req.method === "GET" && url.pathname === "/integrations/stripe/status") {
      if (!authorized(req)) {
        json(res, 401, { error: "unauthorized" });
        return true;
      }
      json(res, 200, {
        ...summary(),
        placeholders: {
          secretKey: stripeSecretKey ? "configured" : "STRIPE_SECRET_KEY",
          webhookSecret: stripeWebhookSecret ? "configured" : "STRIPE_WEBHOOK_SECRET",
          billingPriceId: stripeBillingPriceId || "STRIPE_BILLING_PRICE_ID",
          billingSuccessUrl: stripeBillingSuccessUrl || "STRIPE_BILLING_SUCCESS_URL",
          billingCancelUrl: stripeBillingCancelUrl || "STRIPE_BILLING_CANCEL_URL",
          connectReturnUrl: stripeConnectReturnUrl || "STRIPE_CONNECT_RETURN_URL",
          connectRefreshUrl: stripeConnectRefreshUrl || "STRIPE_CONNECT_REFRESH_URL",
          cryptoOnrampReturnUrl:
            stripeOnrampReturnUrl || "STRIPE_CRYPTO_ONRAMP_RETURN_URL",
        },
      });
      return true;
    }

    if (req.method === "POST" && url.pathname === "/integrations/stripe/webhook") {
      try {
        const rawBody = await readBody(req, 262144);
        const signature = String(req.headers["stripe-signature"] || "");
        if (!verifyStripeSignature(rawBody, signature)) {
          json(res, 401, { error: "invalid_stripe_signature" });
          return true;
        }
        const event = JSON.parse(rawBody.toString("utf8"));
        const type = String(event?.type || "unknown").slice(0, 160);
        const object = event?.data?.object || {};
        state.lastWebhookAt = new Date().toISOString();
        state.lastWebhookType = type;
        state.lastError = null;

        if (
          type === "checkout.session.completed" ||
          type === "payment_intent.succeeded" ||
          type === "customer.subscription.updated" ||
          type === "customer.subscription.deleted" ||
          type === "invoice.paid"
        ) {
          rememberEvent({
            id: String(event?.id || "").slice(0, 240) || null,
            receivedAt: state.lastWebhookAt,
            type: \`stripe.\${type}\`,
            source: "stripe_webhook",
            externalId: String(object?.id || "").slice(0, 240) || null,
          });
        }

        json(res, 200, { received: true });
      } catch (err) {
        state.lastError = err instanceof Error ? err.message.slice(0, 400) : String(err);
        json(res, err?.message === "payload_too_large" ? 413 : 400, {
          error: "invalid_stripe_webhook",
        });
      }
      return true;
    }

    if (req.method === "POST" && url.pathname === "/integrations/stripe/payment-links") {
      if (!authorized(req)) {
        json(res, 401, { error: "unauthorized" });
        return true;
      }
      if (!stripePaymentsEnabled) {
        json(res, 503, { error: "stripe_payments_disabled" });
        return true;
      }
      if (!stripeSecretKey) {
        json(res, 503, { error: "stripe_secret_key_missing" });
        return true;
      }
      try {
        const body = await readJson(req, 16384);
        const amountCents = Math.round(Number(body?.amountCents));
        if (!Number.isFinite(amountCents) || amountCents < 50 || amountCents > 1_000_000) {
          json(res, 400, { error: "amount_cents_out_of_range", min: 50, max: 1_000_000 });
          return true;
        }
        const name = String(body?.name || "AI services").trim().slice(0, 120);
        const description = String(
          body?.description || "Coding, research, data, or automation services.",
        ).trim().slice(0, 500);

        const link = await stripeRequest("/v1/payment_links", {
          method: "POST",
          body: {
            line_items: [
              {
                price_data: {
                  currency: "usd",
                  unit_amount: amountCents,
                  product_data: { name, description },
                },
                quantity: 1,
              },
            ],
            submit_type: "pay",
            restrictions: {
              completed_sessions: { limit: body?.singleUse === false ? 999999 : 1 },
            },
            metadata: {
              purpose: "customer_service_payment",
              runtime: "continuity-agent-core",
            },
          },
        });

        state.lastPaymentLinkAt = new Date().toISOString();
        state.lastPaymentLinkId = link?.id || null;
        state.lastError = null;
        rememberEvent({
          id: link?.id || null,
          receivedAt: state.lastPaymentLinkAt,
          type: "stripe.payment_link.created",
          source: "stripe_runtime",
          externalId: link?.id || null,
        });
        json(res, 201, {
          id: link?.id || null,
          url: link?.url || null,
          active: link?.active ?? null,
        });
      } catch (err) {
        state.lastError = err instanceof Error ? err.message.slice(0, 400) : String(err);
        json(res, 502, { error: "stripe_payment_link_failed", detail: state.lastError });
      }
      return true;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/integrations/stripe/billing/checkout"
    ) {
      if (!authorized(req)) {
        json(res, 401, { error: "unauthorized" });
        return true;
      }
      if (!stripeBillingEnabled) {
        json(res, 503, { error: "stripe_billing_disabled" });
        return true;
      }
      if (!stripeSecretKey || !stripeBillingPriceId) {
        json(res, 503, { error: "stripe_billing_placeholders_not_filled" });
        return true;
      }
      if (!stripeBillingSuccessUrl || !stripeBillingCancelUrl) {
        json(res, 503, { error: "stripe_billing_return_urls_missing" });
        return true;
      }
      try {
        const body = await readJson(req, 8192);
        const session = await stripeRequest("/v1/checkout/sessions", {
          method: "POST",
          body: {
            mode: "subscription",
            line_items: [{ price: stripeBillingPriceId, quantity: 1 }],
            success_url: stripeBillingSuccessUrl,
            cancel_url: stripeBillingCancelUrl,
            customer_email:
              typeof body?.customerEmail === "string"
                ? body.customerEmail.slice(0, 320)
                : undefined,
            metadata: { purpose: "service_subscription" },
          },
        });
        state.lastBillingCheckoutAt = new Date().toISOString();
        state.lastError = null;
        json(res, 201, { id: session?.id || null, url: session?.url || null });
      } catch (err) {
        state.lastError = err instanceof Error ? err.message.slice(0, 400) : String(err);
        json(res, 502, { error: "stripe_billing_checkout_failed", detail: state.lastError });
      }
      return true;
    }

    if (req.method === "GET" && url.pathname === "/integrations/stripe/connect/status") {
      if (!authorized(req)) {
        json(res, 401, { error: "unauthorized" });
        return true;
      }
      json(res, 200, {
        enabled: stripeConnectEnabled,
        neededForMvp: false,
        reason:
          "Direct customer payments do not require Connect. Enable only if third-party merchants or recipients are onboarded later.",
        placeholders: {
          returnUrl: stripeConnectReturnUrl || "STRIPE_CONNECT_RETURN_URL",
          refreshUrl: stripeConnectRefreshUrl || "STRIPE_CONNECT_REFRESH_URL",
        },
      });
      return true;
    }

    if (req.method === "GET" && url.pathname === "/integrations/stripe/onramp/status") {
      if (!authorized(req)) {
        json(res, 401, { error: "unauthorized" });
        return true;
      }
      json(res, 200, {
        enabled: stripeCryptoOnrampEnabled,
        approvalRequired: true,
        targetNetwork: "base",
        targetAssets: ["ETH", "USDC"],
        returnUrl:
          stripeOnrampReturnUrl || "STRIPE_CRYPTO_ONRAMP_RETURN_URL",
        note:
          "Session creation stays disabled until Stripe approves Crypto Onramp and the feature flag is enabled.",
      });
      return true;
    }

    return false;
  }

  return { summary, handle };
}
