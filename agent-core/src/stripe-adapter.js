import { createCipheriv, createDecipheriv, createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const STRIPE_API_BASE = process.env.STRIPE_API_BASE || "https://api.stripe.com";
const stripeSecretKey = process.env.STRIPE_SECRET_KEY || "";
const stripeWebhookSecret = process.env.STRIPE_WEBHOOK_SECRET || "";
const stripePaymentsEnabled = process.env.STRIPE_PAYMENTS_ENABLED === "true";
const stripeBillingEnabled = process.env.STRIPE_BILLING_ENABLED === "true";
const stripeConnectEnabled = process.env.STRIPE_CONNECT_ENABLED === "true";
const stripeCryptoOnrampEnabled = process.env.STRIPE_CRYPTO_ONRAMP_ENABLED === "true";
const stripeBillingPriceId = process.env.STRIPE_BILLING_PRICE_ID || "";
const stripeServiceProductId = process.env.STRIPE_SERVICE_PRODUCT_ID || "";
const stripePriceQuickTask = process.env.STRIPE_PRICE_QUICK_TASK || "";
const stripePriceStandardTask = process.env.STRIPE_PRICE_STANDARD_TASK || "";
const stripePriceDeepTask = process.env.STRIPE_PRICE_DEEP_TASK || "";
const stripePriceRetainer = process.env.STRIPE_PRICE_RETAINER || "";
const stripePaymentLinkQuickTask = process.env.STRIPE_PAYMENT_LINK_QUICK_TASK || "";
const stripePaymentLinkStandardTask = process.env.STRIPE_PAYMENT_LINK_STANDARD_TASK || "";
const stripePaymentLinkDeepTask = process.env.STRIPE_PAYMENT_LINK_DEEP_TASK || "";
const stripeBillingPortalConfigurationId =
  process.env.STRIPE_BILLING_PORTAL_CONFIGURATION_ID || "";
const stripeBillingPortalLoginUrl =
  process.env.STRIPE_BILLING_PORTAL_LOGIN_URL || "";
const stripeBillingSuccessUrl = process.env.STRIPE_BILLING_SUCCESS_URL || "";
const stripeBillingCancelUrl = process.env.STRIPE_BILLING_CANCEL_URL || "";
const stripeConnectReturnUrl = process.env.STRIPE_CONNECT_RETURN_URL || "";
const stripeConnectRefreshUrl = process.env.STRIPE_CONNECT_REFRESH_URL || "";
const stripeOnrampReturnUrl = process.env.STRIPE_CRYPTO_ONRAMP_RETURN_URL || "";
const stripeProfileSyncEnabled = process.env.STRIPE_PROFILE_SYNC === "true";
const stripeBusinessUrl = process.env.STRIPE_BUSINESS_URL || "";
const stripeSupportUrl = process.env.STRIPE_SUPPORT_URL || stripeBusinessUrl;
const stripeSupportEmail = process.env.STRIPE_SUPPORT_EMAIL || "";
const stripeProductDescription =
  process.env.STRIPE_PRODUCT_DESCRIPTION ||
  "Small AI services business providing bounded coding, GitHub repository audits, web research, data analysis, and automation tasks.";
const stripeStatementDescriptor =
  process.env.STRIPE_STATEMENT_DESCRIPTOR || "FRESH STRONG";

const runtimeSecret =
  process.env.RUNTIME_EVENT_TOKEN || process.env.BROWSER_WORKER_TOKEN || "";
const stripeDashboardEmail =
  process.env.STRIPE_DASHBOARD_EMAIL || process.env.AGENT_EMAIL || "";
const stripeDashboardPasswordTemp =
  process.env.STRIPE_DASHBOARD_PASSWORD_TEMP || "";
const stripeBrowserBootstrapEnabled =
  process.env.STRIPE_BROWSER_BOOTSTRAP_ENABLED === "true";
const stripeBrowserProfileSyncEnabled =
  process.env.STRIPE_BROWSER_PROFILE_SYNC_ENABLED === "true";
const stripeBrowserBackupUrl =
  process.env.STRIPE_BROWSER_SESSION_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/stripe-browser-session.enc.json";
const playwrightModulePath =
  process.env.PLAYWRIGHT_MODULE_PATH ||
  "/tmp/stripe-browser/node_modules/playwright";

function encodeStripeForm(obj, prefix = "", out = new URLSearchParams()) {
  for (const [key, value] of Object.entries(obj || {})) {
    if (value === undefined || value === null) continue;
    const name = prefix ? `${prefix}[${key}]` : key;
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (item && typeof item === "object") {
          encodeStripeForm(item, `${name}[${index}]`, out);
        } else {
          out.append(`${name}[${index}]`, String(item));
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
    authorization: `Bearer ${stripeSecretKey}`,
    accept: "application/json",
  };
  let requestBody;
  if (body !== null) {
    headers["content-type"] = "application/x-www-form-urlencoded";
    requestBody = encodeStripeForm(body).toString();
  }
  const response = await fetch(`${STRIPE_API_BASE}${path}`, {
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
      `HTTP ${response.status}`;
    const err = new Error(`stripe_http_${response.status}: ${String(detail).slice(0, 400)}`);
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
    .update(`${timestamp}.`)
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
    profileSyncAt: null,
    profileSyncStatus: stripeProfileSyncEnabled ? "pending" : "disabled",
    browserSessionStatus: "not_started",
    browserSessionSource: null,
    browserSessionLastCheckedAt: null,
    browserSessionLastError: null,
    browserProfileSyncStatus: stripeBrowserProfileSyncEnabled ? "pending" : "disabled",
  };
  let browserStorageState = null;

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
      serviceProductConfigured: Boolean(stripeServiceProductId),
      pricing: {
        quickTask: {
          usd: 5,
          priceId: stripePriceQuickTask || null,
          paymentLink: stripePaymentLinkQuickTask || null,
        },
        standardTask: {
          usd: 15,
          priceId: stripePriceStandardTask || null,
          paymentLink: stripePaymentLinkStandardTask || null,
        },
        deepTask: {
          usd: 40,
          priceId: stripePriceDeepTask || null,
          paymentLink: stripePaymentLinkDeepTask || null,
        },
        retainer: {
          usdMonthly: 29,
          priceId: stripePriceRetainer || stripeBillingPriceId || null,
          publicPaymentLink: null,
        },
      },
      customerPortal: {
        configurationId: stripeBillingPortalConfigurationId || null,
        loginUrl: stripeBillingPortalLoginUrl || null,
      },
      lastWebhookAt: state.lastWebhookAt,
      lastWebhookType: state.lastWebhookType,
      lastPaymentLinkAt: state.lastPaymentLinkAt,
      lastPaymentLinkId: state.lastPaymentLinkId,
      lastBillingCheckoutAt: state.lastBillingCheckoutAt,
      profileSyncAt: state.profileSyncAt,
      profileSyncStatus: state.profileSyncStatus,
      browserSession: {
        status: state.browserSessionStatus,
        source: state.browserSessionSource,
        lastCheckedAt: state.browserSessionLastCheckedAt,
        lastError: state.browserSessionLastError,
        backupConfigured: Boolean(stripeBrowserBackupUrl),
        bootstrapEnabled: stripeBrowserBootstrapEnabled,
        temporaryPasswordPresent: Boolean(stripeDashboardPasswordTemp),
        profileSyncStatus: state.browserProfileSyncStatus,
      },
      lastError: state.lastError,
    };
  }

  function encryptBrowserSession(value) {
    if (!runtimeSecret) throw new Error("stripe_browser_encryption_key_unavailable");
    const plaintext = Buffer.from(JSON.stringify(value), "utf8");
    const salt = randomBytes(16);
    const iv = randomBytes(12);
    const key = scryptSync(runtimeSecret, salt, 32);
    const cipher = createCipheriv("aes-256-gcm", key, iv);
    const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
    const tag = cipher.getAuthTag();
    return {
      version: 1,
      cipher: "aes-256-gcm",
      kdf: "scrypt",
      salt_b64: salt.toString("base64"),
      iv_b64: iv.toString("base64"),
      tag_b64: tag.toString("base64"),
      ciphertext_b64: ciphertext.toString("base64"),
      email: stripeDashboardEmail || null,
      created_at: new Date().toISOString(),
    };
  }

  function decryptBrowserSession(backup) {
    if (!runtimeSecret) throw new Error("stripe_browser_decryption_key_unavailable");
    if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
      throw new Error("unsupported_stripe_browser_backup");
    }
    const key = scryptSync(
      runtimeSecret,
      Buffer.from(backup.salt_b64, "base64"),
      32,
    );
    const decipher = createDecipheriv(
      "aes-256-gcm",
      key,
      Buffer.from(backup.iv_b64, "base64"),
    );
    decipher.setAuthTag(Buffer.from(backup.tag_b64, "base64"));
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(backup.ciphertext_b64, "base64")),
      decipher.final(),
    ]);
    return JSON.parse(plaintext.toString("utf8"));
  }

  function loadPlaywright() {
    try {
      return require(playwrightModulePath);
    } catch (err) {
      throw new Error(
        `stripe_browser_playwright_unavailable: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }

  async function withStripeBrowser(storageState, work) {
    const { chromium } = loadPlaywright();
    const browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    try {
      const context = await browser.newContext(
        storageState ? { storageState } : {},
      );
      const page = await context.newPage();
      return await work({ browser, context, page });
    } finally {
      await browser.close().catch(() => {});
    }
  }

  function dashboardLooksAuthenticated(page) {
    const u = page.url();
    return (
      u.startsWith("https://dashboard.stripe.com/") &&
      !u.includes("/login") &&
      !u.includes("/register")
    );
  }

  async function restoreBrowserSession() {
    state.browserSessionStatus = "restoring";
    state.browserSessionLastError = null;
    try {
      const response = await fetch(stripeBrowserBackupUrl, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(15_000),
      });
      if (response.status === 404) {
        state.browserSessionStatus = "backup_missing";
        return false;
      }
      if (!response.ok) {
        throw new Error(`stripe_browser_backup_http_${response.status}`);
      }
      const backup = await response.json();
      const restored = decryptBrowserSession(backup);
      const storageState = restored?.storageState || restored;
      const valid = await withStripeBrowser(storageState, async ({ page }) => {
        await page.goto("https://dashboard.stripe.com/settings/public", {
          waitUntil: "domcontentloaded",
          timeout: 45_000,
        });
        await page.waitForTimeout(1500);
        return dashboardLooksAuthenticated(page);
      });
      state.browserSessionLastCheckedAt = new Date().toISOString();
      if (!valid) {
        state.browserSessionStatus = "expired";
        state.browserSessionSource = "encrypted_git_backup";
        return false;
      }
      browserStorageState = storageState;
      state.browserSessionStatus = "ready";
      state.browserSessionSource = "encrypted_git_backup";
      return true;
    } catch (err) {
      state.browserSessionStatus = "restore_error";
      state.browserSessionLastError =
        err instanceof Error ? err.message.slice(0, 500) : String(err);
      return false;
    }
  }

  async function bootstrapBrowserSession() {
    if (!stripeBrowserBootstrapEnabled) {
      state.browserSessionStatus = "bootstrap_disabled";
      return false;
    }
    if (!stripeDashboardEmail || !stripeDashboardPasswordTemp) {
      state.browserSessionStatus = "awaiting_credentials";
      return false;
    }

    state.browserSessionStatus = "logging_in";
    state.browserSessionLastError = null;
    try {
      const result = await withStripeBrowser(null, async ({ context, page }) => {
        await page.goto("https://dashboard.stripe.com/login", {
          waitUntil: "domcontentloaded",
          timeout: 45_000,
        });

        const email = page.locator(
          'input[type="email"], input[name="email"], input[autocomplete="username"]',
        ).first();

        await email.waitFor({ state: "visible", timeout: 20_000 });
        await email.fill(stripeDashboardEmail);

        const passwordMethod = page
          .getByRole("button", { name: /^password$/i })
          .first();
        if (await passwordMethod.isVisible().catch(() => false)) {
          await passwordMethod.click();
          await page.waitForTimeout(700);
        }

        const password = page.locator(
          'input[type="password"], input[name="password"], input[autocomplete="current-password"]',
        ).first();
        await password.waitFor({ state: "visible", timeout: 20_000 });

        // Stripe's React login form can expose a visible password field while
        // Playwright's normal actionability checks still stall. Use the normal
        // fill path first, then fall back to the native value setter so the
        // user does not need a keyboard in the remote browser.
        let passwordEntered = false;
        try {
          await password.fill(stripeDashboardPasswordTemp, { timeout: 5_000 });
          passwordEntered = true;
        } catch {
          await password.evaluate((el, value) => {
            const proto = HTMLInputElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
            if (descriptor?.set) descriptor.set.call(el, value);
            else el.value = value;
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            el.focus();
          }, stripeDashboardPasswordTemp);
          passwordEntered = await password
            .inputValue()
            .then((value) => value.length > 0)
            .catch(() => false);
        }
        if (!passwordEntered) throw new Error("stripe_password_injection_failed");

        let submitted = false;
        try {
          submitted = await password.evaluate((el) => {
            const form = el.closest("form");
            if (!form) return false;
            if (typeof form.requestSubmit === "function") form.requestSubmit();
            else form.submit();
            return true;
          });
        } catch {}
        if (!submitted) {
          await password.press("Enter", { timeout: 5_000 }).catch(async () => {
            await page.keyboard.press("Enter");
          });
        }
        await page.waitForTimeout(6000);

        const bodyText = (
          await page.locator("body").innerText({ timeout: 10_000 }).catch(() => "")
        ).toLowerCase();
        const url = page.url();

        if (!dashboardLooksAuthenticated(page)) {
          let reason = "login_not_completed";
          if (
            bodyText.includes("captcha") ||
            bodyText.includes("verify you are human") ||
            bodyText.includes("security challenge")
          ) {
            reason = "captcha_or_security_challenge";
          } else if (
            bodyText.includes("two-step") ||
            bodyText.includes("verification code") ||
            bodyText.includes("two-factor") ||
            bodyText.includes("passkey")
          ) {
            reason = "second_factor_required";
          } else if (bodyText.includes("incorrect") || bodyText.includes("invalid")) {
            reason = "credentials_rejected";
          }
          const headings = await page
            .locator("h1, h2, h3")
            .allInnerTexts()
            .catch(() => []);
          const buttons = await page
            .locator("button, [role='button']")
            .allInnerTexts()
            .catch(() => []);
          const links = await page
            .locator("a")
            .allInnerTexts()
            .catch(() => []);
          return {
            ok: false,
            reason,
            urlClass: url.includes("/login") ? "login" : "other",
            headings: headings.map((x) => String(x).trim()).filter(Boolean).slice(0, 20),
            buttons: buttons.map((x) => String(x).trim()).filter(Boolean).slice(0, 30),
            links: links.map((x) => String(x).trim()).filter(Boolean).slice(0, 30),
          };
        }

        const storageState = await context.storageState();
        return { ok: true, storageState };
      });

      state.browserSessionLastCheckedAt = new Date().toISOString();
      if (!result.ok) {
        state.browserSessionStatus = "human_verification_required";
        state.browserSessionLastError = result.reason;
        console.log(
          JSON.stringify({
            event: "stripe.browser_challenge",
            reason: result.reason,
            urlClass: result.urlClass,
            headings: result.headings || [],
            buttons: result.buttons || [],
            links: result.links || [],
          }),
        );
        return false;
      }

      browserStorageState = result.storageState;
      state.browserSessionStatus = "ready";
      state.browserSessionSource = "fresh_login";
      const encrypted = encryptBrowserSession({
        storageState: result.storageState,
        email: stripeDashboardEmail,
        createdAt: new Date().toISOString(),
      });
      console.log(
        JSON.stringify({
          event: "stripe.browser_session_backup",
          note: "Encrypted browser session only; plaintext password is not emitted.",
          backup: encrypted,
        }),
      );
      return true;
    } catch (err) {
      state.browserSessionStatus = "bootstrap_error";
      state.browserSessionLastError =
        err instanceof Error ? err.message.slice(0, 500) : String(err);
      return false;
    }
  }

  async function inspectPublicProfileFields() {
    if (!browserStorageState) {
      return { ok: false, error: "stripe_browser_session_not_ready" };
    }
    try {
      const result = await withStripeBrowser(
        browserStorageState,
        async ({ page }) => {
          await page.goto("https://dashboard.stripe.com/settings/public", {
            waitUntil: "domcontentloaded",
            timeout: 45_000,
          });
          await page.waitForTimeout(2000);
          if (!dashboardLooksAuthenticated(page)) {
            return { ok: false, error: "stripe_browser_session_expired" };
          }
          const fields = await page.locator("input, textarea, select").evaluateAll((els) =>
            els.slice(0, 100).map((el) => ({
              tag: el.tagName.toLowerCase(),
              type: el.getAttribute("type"),
              name: el.getAttribute("name"),
              id: el.id || null,
              ariaLabel: el.getAttribute("aria-label"),
              placeholder: el.getAttribute("placeholder"),
            })),
          );
          const labels = await page.locator("label").evaluateAll((els) =>
            els.slice(0, 100).map((el) => (el.textContent || "").trim()).filter(Boolean),
          );
          return { ok: true, fields, labels };
        },
      );
      if (result.ok) {
        console.log(
          JSON.stringify({
            event: "stripe.public_profile_fields",
            fields: result.fields,
            labels: result.labels,
          }),
        );
      }
      return result;
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message.slice(0, 500) : String(err),
      };
    }
  }

  async function ensureBrowserSession() {
    const restored = await restoreBrowserSession();
    if (!restored) {
      await bootstrapBrowserSession();
    }
    if (state.browserSessionStatus === "ready" && stripeBrowserProfileSyncEnabled) {
      state.browserProfileSyncStatus = "inspecting";
      const inspected = await inspectPublicProfileFields();
      state.browserProfileSyncStatus = inspected.ok ? "inspection_emitted" : "inspection_error";
      if (!inspected.ok) state.browserSessionLastError = inspected.error || null;
    }
    return state.browserSessionStatus === "ready";
  }

  async function syncProfile() {
    if (!stripeProfileSyncEnabled) return { skipped: true, reason: "disabled" };
    if (!stripeSecretKey) {
      state.profileSyncStatus = "blocked_missing_secret";
      return { skipped: true, reason: "stripe_secret_key_missing" };
    }
    if (!stripeBusinessUrl || !stripeSupportUrl || !stripeSupportEmail) {
      state.profileSyncStatus = "blocked_missing_profile_values";
      return { skipped: true, reason: "stripe_profile_values_missing" };
    }
    try {
      const account = await stripeRequest("/v1/account", {
        method: "POST",
        body: {
          business_profile: {
            url: stripeBusinessUrl,
            product_description: stripeProductDescription,
            support_url: stripeSupportUrl,
            support_email: stripeSupportEmail,
          },
          settings: {
            payments: {
              statement_descriptor: stripeStatementDescriptor,
            },
          },
        },
      });
      state.profileSyncAt = new Date().toISOString();
      state.profileSyncStatus = "completed";
      state.lastError = null;
      return {
        updated: true,
        accountId: account?.id || null,
        businessUrl: account?.business_profile?.url || null,
        supportUrl: account?.business_profile?.support_url || null,
        supportEmail: account?.business_profile?.support_email || null,
        statementDescriptor: account?.settings?.payments?.statement_descriptor || null,
      };
    } catch (err) {
      state.profileSyncStatus = "error";
      state.lastError = err instanceof Error ? err.message.slice(0, 400) : String(err);
      return { updated: false, error: state.lastError };
    }
  }

  function html(res, status, title, body) {
    res.writeHead(status, {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    });
    res.end(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><style>body{font-family:system-ui,sans-serif;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.55}h1{font-size:1.8rem}code{background:#eee;padding:.15rem .35rem;border-radius:4px}</style></head><body><h1>${title}</h1>${body}</body></html>`);
  }

  async function handle(req, res, url, { json, readBody, readJson, authorized }) {
    if (req.method === "GET" && url.pathname === "/stripe/business") {
      html(
        res,
        200,
        "Fresh and Strong — AI task services",
        "<p>Fresh and Strong provides small, bounded AI-assisted services including coding, GitHub repository audits, web research, data analysis, and automation tasks.</p><p>Work is accepted only when scope, deliverables, and payment terms are clear. We do not request customer passwords, private keys, or unauthorized system access.</p><p>Support: <a href=\"mailto:oldcraft541@agentmail.to\">oldcraft541@agentmail.to</a></p>",
      );
      return true;
    }

    if (req.method === "GET" && url.pathname === "/stripe/success") {
      html(res, 200, "Payment received", "<p>Your payment was received. Keep your Stripe confirmation for your records.</p>");
      return true;
    }

    if (req.method === "GET" && url.pathname === "/stripe/cancel") {
      html(res, 200, "Payment canceled", "<p>No payment was completed. You can return to the original task or checkout when ready.</p>");
      return true;
    }

    if (req.method === "GET" && url.pathname === "/stripe/connect/return") {
      html(res, 200, "Stripe Connect return", "<p>Connect onboarding returned to the worker. Connect remains disabled unless the platform feature is intentionally enabled.</p>");
      return true;
    }

    if (req.method === "GET" && url.pathname === "/stripe/connect/refresh") {
      html(res, 200, "Stripe Connect refresh", "<p>Connect onboarding can be restarted from the worker when that feature is enabled.</p>");
      return true;
    }

    if (req.method === "GET" && url.pathname === "/stripe/onramp/return") {
      html(res, 200, "Crypto onramp return", "<p>The Stripe Crypto Onramp flow returned to the worker. Onramp remains disabled until Stripe approves access.</p>");
      return true;
    }

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
          type === "checkout.session.async_payment_succeeded" ||
          type === "checkout.session.async_payment_failed" ||
          type === "payment_intent.succeeded" ||
          type === "payment_intent.payment_failed" ||
          type === "customer.subscription.created" ||
          type === "customer.subscription.updated" ||
          type === "customer.subscription.deleted" ||
          type === "invoice.paid" ||
          type === "invoice.payment_failed" ||
          type === "refund.created" ||
          type === "refund.failed" ||
          type === "charge.dispute.created" ||
          type === "charge.dispute.closed"
        ) {
          rememberEvent({
            id: String(event?.id || "").slice(0, 240) || null,
            receivedAt: state.lastWebhookAt,
            type: `stripe.${type}`,
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

  return {
    summary,
    handle,
    syncProfile,
    ensureBrowserSession,
    restoreBrowserSession,
    bootstrapBrowserSession,
    inspectPublicProfileFields,
  };
}
