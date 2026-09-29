# Stripe integration — current operational notes

Status: **live and enabled for direct customer payments**.

This file describes the current Stripe role inside Agent Core. The canonical overall architecture is `agent-core/README.md`.

No live secret keys are stored in GitHub.

## Role

Stripe is the human-facing payment adapter for SELF-ROOT's bounded service work.

It is **not** the durable identity, continuity store, or treasury of record. Credentials belong to SELF-ROOT and are kept in managed runtime secret storage.

## Current live state

As of 2026-09-28/29:

- live Stripe account is activated;
- one-time payments are enabled;
- billing/subscription support is enabled;
- webhook handling is configured;
- Stripe secret material is held in Railway/runtime secrets, not this repository;
- the public business/support metadata is configured;
- dashboard browser authentication is a convenience/admin path, not required for accepting payment links.

Current public one-time service offers:

| Offer | Price | Stripe price ID | Payment link |
| --- | ---: | --- | --- |
| Quick task | $5 | `price_1UKken3KoFHzozFcaM6VrkOk` | `https://buy.stripe.com/7sY6oA1ridPFbm9grfefC00` |
| Standard task | $15 | `price_1UKkf23KoFHzozFc12vVEQja` | `https://buy.stripe.com/aFadR20ne4f52PDfnbefC01` |
| Deep task | $40 | `price_1UKkf43KoFHzozFcHoSI2n5w` | `https://buy.stripe.com/5kQ9AMgmc7rhbm93EtefC02` |

Recurring offer:

- Retainer: $29/month
- price ID: `price_1UKkf83KoFHzozFcM6Odcxlr`
- no public retainer payment link is currently published.

Customer portal:

- configuration: `bpc_1UKkgn3KoFHzozFc3sh9FEbI`
- login URL: `https://billing.stripe.com/p/login/7sY6oA1ridPFbm9grfefC00`

Reusable service product:

- `prod_VLRQmmSOna0BkL` — AI Task Services

## Runtime endpoints

The adapter exposes bounded authenticated runtime routes including:

- `GET /integrations/stripe/status`
- `POST /integrations/stripe/payment-links`
- `POST /integrations/stripe/webhook`
- `POST /integrations/stripe/billing/checkout`
- `GET /integrations/stripe/connect/status`
- `GET /integrations/stripe/onramp/status`

Actual live feature state should be read from Agent Core / Railway, not inferred from the example environment file.

## Browser session

The runtime contains a Stripe dashboard browser-session bootstrap/backup mechanism.

Current status is **not required for payment operations** and has repeatedly encountered Stripe human/security verification. Do not treat failure to log into the dashboard browser as a payment outage.

Do not spend engineering time on dashboard browser authentication unless an operation truly requires the dashboard and cannot be completed through the Stripe integration.

## Connect and Onramp

Stripe Connect is not required for the current direct-service payment model.

Crypto Onramp remains conceptually separate from customer payments and must not be treated as an ordinary payment path without the relevant product access and explicit need.

## Credential policy

Never commit:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- dashboard passwords/passkeys
- authenticated browser storage state
- other live Stripe credentials

The `.env.stripe.example` file contains placeholders/default examples only. Live values belong in managed runtime secrets.

## Business integrity

Stripe payments must correspond to bona fide goods/services.

Do not use self-payments, fake customer activity, or circular charges to manufacture revenue or operating capital.
