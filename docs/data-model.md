# Data model

One SQLite file (default `./afr.db`, override `AFR_DB_PATH`). WAL mode.
Schema versioned via `PRAGMA user_version` with idempotent migrations.

## Tables

### `runs`
| column | type | notes |
| --- | --- | --- |
| id | TEXT PK | uuid4 |
| name | TEXT | auto-named if omitted |
| status | TEXT | `running` → `completed` \| `failed` |
| metadata | TEXT | JSON |
| tags | TEXT | JSON array (premium writes; always present in responses) |
| notes | TEXT | free text (premium writes) |
| parent_run_id | TEXT | set on forked runs — the run it branched from |
| fork_checkpoint_id | TEXT | the checkpoint the fork branched at |
| created_at / ended_at | TEXT | ISO-8601 UTC |

`GET /runs` responses are additionally enriched per run with `last_error`
(latest error-event message) and `event_type_counts` (`{event_type: n}`) for
the dashboard; neither is a stored column.

### `events` — append-only
| column | type | notes |
| --- | --- | --- |
| seq | INTEGER PK AUTOINCREMENT | total order within the DB |
| id | TEXT UNIQUE | uuid4 |
| run_id | TEXT FK | |
| event_type | TEXT | one of the six types |
| name | TEXT | display name (tool name, label, level…) |
| payload | TEXT | JSON |
| created_at | TEXT | ISO-8601 UTC (client-suppliable) |

Indexes: `run_id`, `created_at`, `event_type`, `(run_id, created_at)`,
`(run_id, event_type)`. There is no UPDATE/DELETE path for events by design.

### `checkpoints`
| column | type | notes |
| --- | --- | --- |
| id | TEXT PK | uuid4 |
| run_id | TEXT FK | |
| event_id / event_seq | TEXT / INTEGER | the `checkpoint` event on the timeline |
| label | TEXT | |
| state | TEXT | JSON — authoritative state at checkpoint time |
| created_at | TEXT | |

## Event types

| type | conventional payload |
| --- | --- |
| `model_call` | `{model, provider, input, output, status, error?, duration_ms}` |
| `tool_call` | `{tool, args, result, status, error?, duration_ms}` |
| `state_snapshot` | `{state: {...}, mode: "replace"\|"merge"}` |
| `checkpoint` | `{checkpoint_id, label}` |
| `log` | `{level, message, data?}` |
| `error` | `{message, traceback?, data?}` |

## State folding

State at any point = fold of `state_snapshot` events in **seq** order (never
timestamps — immune to client clock skew):

- `replace` (default): snapshot becomes the state
- `merge`: deep merge (dicts recurse; lists/scalars replaced)

A checkpoint stores the folded state in the `checkpoints` table at creation
time. If explicit state is passed to the checkpoint call, it is *also*
appended as a `state_snapshot` event first, so the fold and the stored copy
never disagree. `GET .../state-at/{ckpt}?reconstruct=true` re-folds from
events and is asserted equal to the stored copy in the test suite.
