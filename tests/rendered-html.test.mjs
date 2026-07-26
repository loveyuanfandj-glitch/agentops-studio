import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}


// Validates that the production worker server-renders the dashboard shell and product metadata.
test("server-renders the AgentOps dashboard", async () => {
  const response = await render();
  const html = await response.text();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.match(html, /AgentOps Studio/);
  assert.match(html, /See what every agent is doing/);
  assert.match(html, /Operations overview/);
});


// Guards the portfolio's core claims by checking that live API fallback and reliability views remain.
test("keeps the live orchestration and guardrail surfaces", async () => {
  const dashboard = await readFile(
    new URL("app/agent-ops-dashboard.tsx", projectRoot),
    "utf8",
  );
  assert.match(dashboard, /NEXT_PUBLIC_API_URL/);
  assert.match(dashboard, /get_revenue_summary/);
  assert.match(dashboard, /Repeated call detection/);
  assert.match(dashboard, /Deterministic demo mode/);
});
