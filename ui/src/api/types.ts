export type EventType =
  | "model_call"
  | "tool_call"
  | "state_snapshot"
  | "checkpoint"
  | "log"
  | "error";

export interface ForkRef {
  id: string;
  name: string;
  status: string;
  fork_checkpoint_id: string | null;
  created_at: string;
}

export interface Run {
  id: string;
  name: string;
  status: "running" | "completed" | "failed" | string;
  metadata: Record<string, unknown>;
  created_at: string;
  ended_at: string | null;
  events_count: number;
  checkpoints_count: number;
  // run-list enrichment (GET /runs only)
  last_error?: string | null;
  event_type_counts?: Record<string, number>;
  // tags/notes/fork lineage
  tags: string[];
  notes: string;
  parent_run_id: string | null;
  fork_checkpoint_id: string | null;
  forks?: ForkRef[] | null;
}

export interface License {
  experimental_enabled: boolean;
  features: Record<string, boolean>;
  hint: string | null;
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

export interface DemoSeedResult {
  run: Run;
  checkpoints: { safe: Checkpoint; failure: Checkpoint };
  replay: ReplayResult;
  ui_url: string;
}

export interface ToolPlanEntry {
  policy: string;
  action: "allow" | "mock" | "skip" | "block" | string;
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
  // advanced replay policy engine
  tool_plan: Record<string, ToolPlanEntry>;
  mock_results: Record<string, unknown>;
  policy_notes: string | null;
}
