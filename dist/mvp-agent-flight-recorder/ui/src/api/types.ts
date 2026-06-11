export type EventType =
  | "model_call"
  | "tool_call"
  | "state_snapshot"
  | "checkpoint"
  | "log"
  | "error";

export interface Run {
  id: string;
  name: string;
  status: "running" | "completed" | "failed" | string;
  metadata: Record<string, unknown>;
  created_at: string;
  ended_at: string | null;
  events_count: number;
  checkpoints_count: number;
}

export interface AfrEvent {
  seq: number;
  id: string;
  run_id: string;
  event_type: EventType | string;
  name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Checkpoint {
  id: string;
  run_id: string;
  event_id: string;
  event_seq: number;
  label: string | null;
  created_at: string;
  state?: Record<string, unknown> | null;
}

export interface StateAt {
  run_id: string;
  checkpoint: Checkpoint;
  state: Record<string, unknown>;
  source: "checkpoint_table" | "reconstructed";
}

export interface ReplayResult {
  run_id: string;
  checkpoint_id: string;
  label: string | null;
  mode: string;
  state: Record<string, unknown>;
  status: string;
  message: string;
  replay_event_id: string;
}
