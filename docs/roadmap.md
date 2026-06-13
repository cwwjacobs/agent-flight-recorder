# Roadmap

Where AFR is headed, in order. Self-hosted, SQLite-backed, replay-first —
those stay.

## v0.3 — LangChain / LangGraph adapter ✅ (in this release)

`afr.integrations.langchain.AFRCallbackHandler`: one-line adoption for the
largest agent-framework ecosystem. See [integrations.md](integrations.md).

## v0.4 — more framework adapters

- **OpenAI Agents SDK** adapter (trace processor → AFR events)
- **CrewAI** adapter (task/tool callbacks → AFR events)

Both follow the LangChain adapter's pattern: optional dependency extra,
import-safe module, duck-typed and version-defensive, tool policies stamped
at record time so replay plans work out of the box.

## Later — OpenAI-compatible proxy mode

A proxy endpoint you can point any OpenAI-compatible client at
(`base_url=http://127.0.0.1:8700/proxy/v1`) to capture model calls from apps
you don't control.

Deliberately deferred: a proxy only sees **model traffic**. It cannot record
tool calls, state snapshots, or checkpoints unless the app cooperates — which
means no replay-from-checkpoint, i.e. none of the parts of AFR that the
incumbents don't already do. It's a useful capture-only mode, not the
adoption path, so it ships after the adapters that give the full story.

## Later — hosted / team mode

Shared instance, auth beyond a single bearer token, retention policies,
multi-writer storage. The current single-process + SQLite design is a
deliberate ceiling for the self-hosted devtool; team mode is where that
changes (and where the premium boundary becomes a real product).
