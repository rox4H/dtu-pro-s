import test from "node:test";
import assert from "node:assert/strict";
import {
  HoymilesApiError,
  HoymilesConnectionError,
  HoymilesReaderClient,
  HoymilesTimeoutError,
} from "../src/index.js";

function jsonResponse(body, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  };
}

test("defaults to local API and parses health response", async () => {
  let called;
  const client = new HoymilesReaderClient({
    fetchImpl: async (url, init) => {
      called = { url, init };
      return jsonResponse({ status: "online", service: "hoymiles-dtu-reader", version: "2.0.0" });
    },
  });

  const health = await client.getHealth();
  assert.equal(health.status, "online");
  assert.equal(called.url, "http://127.0.0.1:5001/api/health");
  assert.equal(called.init.method, "GET");
  assert.equal(called.init.headers.Accept, "application/json");
  assert.equal(called.init.headers.Authorization, undefined);
});

test("does not attach authentication headers", async () => {
  let called;
  const client = new HoymilesReaderClient({
    fetchImpl: async (url, init) => {
      called = { url, init };
      return jsonResponse({ pv_power_w: 300 });
    },
  });
  await client.getSummary();
  assert.equal(called.url, "http://127.0.0.1:5001/api/solar/summary");
  assert.deepEqual(called.init.headers, { Accept: "application/json" });
});

test("sends a configured token as a bearer authorization header", async () => {
  let called;
  const client = new HoymilesReaderClient({
    token: "  company-issued-token  ",
    fetchImpl: async (url, init) => {
      called = { url, init };
      return jsonResponse({ status: "online" });
    },
  });
  await client.getHealth();
  assert.equal(called.init.headers.Authorization, "Bearer company-issued-token");
});


test("maps each read-only method to its documented endpoint", async () => {
  const urls = [];
  const client = new HoymilesReaderClient({
    fetchImpl: async (url) => {
      urls.push(url);
      return jsonResponse({});
    },
  });
  await client.getHealth();
  await client.getSolar();
  await client.getMeter();
  await client.getSummary();
  await client.getAccessories();
  await client.getDiagnostics();

  assert.deepEqual(urls.map((url) => new URL(url).pathname), [
    "/api/health",
    "/api/solar",
    "/api/solar/meter",
    "/api/solar/summary",
    "/api/solar/accessories",
    "/api/solar/diagnostics",
  ]);
});

test("surfaces HTTP errors including status and error field", async () => {
  const client = new HoymilesReaderClient({
    fetchImpl: async () => jsonResponse({ error: "unauthorized" }, { status: 401 }),
  });
  await assert.rejects(client.getSolar(), (error) => {
    assert.ok(error instanceof HoymilesApiError);
    assert.equal(error.status, 401);
    assert.equal(error.message, "unauthorized");
    return true;
  });
});

test("wraps connection failures", async () => {
  const client = new HoymilesReaderClient({
    fetchImpl: async () => { throw new Error("offline"); },
  });
  await assert.rejects(client.getSolar(), (error) => {
    assert.ok(error instanceof HoymilesConnectionError);
    assert.match(error.message, /Could not connect/);
    return true;
  });
});

test("raises a dedicated timeout error", async () => {
  const client = new HoymilesReaderClient({
    timeoutMs: 5,
    fetchImpl: (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }),
  });
  await assert.rejects(client.getSolar(), (error) => {
    assert.ok(error instanceof HoymilesTimeoutError);
    assert.equal(error.timeoutMs, 5);
    return true;
  });
});

test("rejects invalid base URLs and timeouts", () => {
  assert.throws(() => new HoymilesReaderClient({ baseUrl: "ftp://example.com" }), TypeError);
  assert.throws(() => new HoymilesReaderClient({ baseUrl: "http://user:pass@example.com" }), TypeError);
  assert.throws(() => new HoymilesReaderClient({ timeoutMs: 0 }), TypeError);
});
