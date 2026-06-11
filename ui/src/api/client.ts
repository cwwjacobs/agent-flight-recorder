import type { AfrEvent, Checkpoint, License, ReplayResult, Run, StateAt } from "./types";

const BASE = "/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listRuns: (params?: { status?: string; tag?: string }) => {
    const qs = new URLSearchParams({ limit: "200" });
    if (params?.status) qs.set("status", params.status);
    if (params?.tag) qs.set("tag", params.tag);
    return request<Run[]>(`/runs?${qs}`);
  },
  getRun: (runId: string) => request<Run>(`/runs/${runId}`),
  getEvents: (runId: string) =>
    request<AfrEvent[]>(`/runs/${runId}/events?limit=10000`),
  getCheckpoints: (runId: string) => request<Checkpoint[]>(`/runs/${runId}/checkpoints`),
  getStateAt: (runId: string, checkpointId: string) =>
    request<StateAt>(`/runs/${runId}/state-at/${checkpointId}`),
  replay: (runId: string, checkpointId: string, mode: string, approved = false) =>
    request<ReplayResult>(`/runs/${runId}/replay`, {
      method: "POST",
      body: JSON.stringify({ checkpoint_id: checkpointId, mode, approved }),
    }),
  // premium
  getLicense: () => request<License>(`/license`),
  forkRun: (runId: string, checkpointId: string, name?: string) =>
    request<Run>(`/runs/${runId}/fork`, {
      method: "POST",
      body: JSON.stringify({ checkpoint_id: checkpointId, name: name ?? null }),
    }),
  updateRun: (runId: string, patch: { name?: string; tags?: string[]; notes?: string }) =>
    request<Run>(`/runs/${runId}`, { method: "PATCH", body: JSON.stringify(patch) }),
};

export { ApiError };
