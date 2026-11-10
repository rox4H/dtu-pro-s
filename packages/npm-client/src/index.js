/**
 * Minimal read-only client for the Hoymiles DTU Reader local JSON API.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:5001";
const DEFAULT_TIMEOUT_MS = 5000;

export class HoymilesApiError extends Error {
  constructor(message, { status, payload = null } = {}) {
    super(message);
    this.name = "HoymilesApiError";
    this.status = status;
    this.payload = payload;
  }
}

export class HoymilesConnectionError extends Error {
  constructor(message, { cause } = {}) {
    super(message);
    this.name = "HoymilesConnectionError";
    if (cause !== undefined) this.cause = cause;
  }
}

export class HoymilesTimeoutError extends HoymilesConnectionError {
  constructor(timeoutMs) {
    super(`Hoymiles Reader API did not respond within ${timeoutMs} ms.`);
    this.name = "HoymilesTimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

function normalizeBaseUrl(value) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError("baseUrl must be a non-empty HTTP(S) URL.");
  }
  let parsed;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new TypeError("baseUrl must be a valid HTTP(S) URL.");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new TypeError("baseUrl must use http:// or https://.");
  }
  if (parsed.username || parsed.password) {
    throw new TypeError("Do not put credentials in baseUrl.");
  }
  if (parsed.search || parsed.hash) {
    throw new TypeError("baseUrl must not include a query string or fragment.");
  }
  return parsed.href.replace(/\/+$/, "");
}

function normalizeToken(value) {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string") {
    throw new TypeError("token must be a string when provided.");
  }
  return value.trim() || null;
}

function extractMessage(payload, fallback) {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const message = payload.error ?? payload.message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

export class HoymilesReaderClient {
  #baseUrl;
  #token;
  #timeoutMs;
  #fetch;

  constructor({
    baseUrl = DEFAULT_BASE_URL,
    token,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    fetchImpl = globalThis.fetch,
  } = {}) {
    this.#baseUrl = normalizeBaseUrl(baseUrl);
    this.#token = normalizeToken(token);
    if (!Number.isFinite(timeoutMs) || timeoutMs < 1) {
      throw new TypeError("timeoutMs must be a positive number.");
    }
    if (typeof fetchImpl !== "function") {
      throw new TypeError("fetchImpl must be a fetch-compatible function (Node.js 22+ provides fetch).");
    }
    this.#timeoutMs = Math.floor(timeoutMs);
    this.#fetch = fetchImpl;
  }

  async #get(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.#timeoutMs);
    let response;
    let text = "";
    try {
      response = await this.#fetch(`${this.#baseUrl}${path}`, {
        method: "GET",
        headers: {
          Accept: "application/json",
          ...(this.#token ? { Authorization: `Bearer ${this.#token}` } : {}),
        },
        signal: controller.signal,
      });
      text = await response.text();
    } catch (cause) {
      if (controller.signal.aborted) throw new HoymilesTimeoutError(this.#timeoutMs);
      throw new HoymilesConnectionError(
        "Could not connect to the Hoymiles Reader API. Check that the Python service is running and the URL is correct.",
        { cause },
      );
    } finally {
      clearTimeout(timeout);
    }

    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        if (response.ok) {
          throw new HoymilesApiError("The Reader API returned invalid JSON.", { status: response.status });
        }
        payload = text;
      }
    }
    if (!response.ok) {
      throw new HoymilesApiError(
        extractMessage(payload, `Hoymiles Reader API returned HTTP ${response.status}.`),
        { status: response.status, payload },
      );
    }
    if (payload === null || typeof payload !== "object") {
      throw new HoymilesApiError("The Reader API response was empty or was not a JSON object.", {
        status: response.status,
        payload,
      });
    }
    return payload;
  }

  getHealth() { return this.#get("/api/health"); }
  getSolar() { return this.#get("/api/solar"); }
  getMeter() { return this.#get("/api/solar/meter"); }
  getSummary() { return this.#get("/api/solar/summary"); }
  getAccessories() { return this.#get("/api/solar/accessories"); }
  getDiagnostics() { return this.#get("/api/solar/diagnostics"); }
}
