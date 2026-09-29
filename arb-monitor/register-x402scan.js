const origin =
  process.env.PUBLIC_ORIGIN ||
  "https://browser-worker-v2-production.up.railway.app";

const endpoint =
  "https://www.x402scan.com/api/trpc/public.resources.registerFromOrigin";

try {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trpc-source": "self-root-launch",
    },
    body: JSON.stringify({ json: { origin } }),
    signal: AbortSignal.timeout(30000),
  });

  const body = await response.text();
  console.log(
    JSON.stringify({
      event: "x402scan-register",
      status: response.status,
      body: body.slice(0, 8000),
    })
  );
} catch (error) {
  console.log(
    JSON.stringify({
      event: "x402scan-register-error",
      error: String(error),
    })
  );
}
