# Stripe integration scaffold

Status: scaffolded for the autonomous worker. No secret keys are stored in GitHub.

## MVP

The chosen MVP is direct Stripe payments through one-time Payment Links. This does **not** require Connect.

Runtime endpoints:

- \`GET /integrations/stripe/status\` — authenticated configuration/status view.
- \`POST /integrations/stripe/payment-links\` — authenticated creation of a bounded one-time customer payment link.
- \`POST /integrations/stripe/webhook\` — Stripe-signed webhook ingress.
- \`POST /integrations/stripe/billing/checkout\` — dormant subscription checkout scaffold.
- \`GET /integrations/stripe/connect/status\` — dormant Connect scaffold/status.
- \`GET /integrations/stripe/onramp/status\` — dormant Crypto Onramp scaffold/status.

## Feature flags

All write-capable Stripe routes are off until runtime secrets and feature flags are configured. See \`.env.stripe.example\`.

The runtime deliberately keeps Connect disabled for the MVP. Connect only becomes useful if this worker evolves into a platform that onboards third-party merchants/recipients.

Crypto Onramp is kept separate from ordinary customer payments. It must remain disabled until Stripe approves Crypto Onramp access.

## Placeholder policy

Placeholders belong in code/config only. Stripe's live legal/business profile must contain accurate information and must not use fake placeholder identity or business data.

## Operator seed funding

Do not use a live card charge merely to convert the account owner's card balance into cash/working capital. Stripe payments should represent bona fide customer goods/services. Operator seed funding should use an appropriate capital-contribution/onramp rail instead.
