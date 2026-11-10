export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export interface JsonObject { [key: string]: JsonValue; }

export interface HoymilesReaderClientOptions {
  /** Base URL of the Reader API. Defaults to http://127.0.0.1:5001. */
  baseUrl?: string;
  /** Optional company-issued token sent as Authorization: Bearer <token>. */
  token?: string;
  /** Per-request timeout in milliseconds. Defaults to 5000. */
  timeoutMs?: number;
  /** Fetch-compatible implementation. Defaults to globalThis.fetch. */
  fetchImpl?: typeof fetch;
}

export interface HealthResponse extends JsonObject {
  status?: string;
  service?: string;
  version?: string;
  dtu?: string;
  meter_type?: string | null;
  meter_slave?: number | null;
  chint_slave?: number | null;
  last_update?: string | null;
}

export interface SolarSummary extends JsonObject {
  pv_power_w?: number | null;
  grid_power_w?: number | null;
  load_power_w?: number | null;
}

export interface SolarSnapshot extends JsonObject {
  status?: string;
  sampled_at?: string | null;
  dtu?: string | null;
  summary?: SolarSummary;
  microinverters?: JsonValue[];
  meter?: JsonObject;
  accessories?: JsonValue[];
  diagnostics?: JsonObject;
}

export class HoymilesApiError extends Error {
  status?: number;
  payload: unknown;
}
export class HoymilesConnectionError extends Error {
  cause?: unknown;
}
export class HoymilesTimeoutError extends HoymilesConnectionError {
  timeoutMs: number;
}

/** Read-only client for an already-running local Hoymiles DTU Reader. */
export class HoymilesReaderClient {
  constructor(options?: HoymilesReaderClientOptions);
  getHealth(): Promise<HealthResponse>;
  getSolar(): Promise<SolarSnapshot>;
  getMeter(): Promise<JsonObject>;
  getSummary(): Promise<SolarSummary>;
  getAccessories(): Promise<JsonValue[]>;
  getDiagnostics(): Promise<JsonObject>;
}
