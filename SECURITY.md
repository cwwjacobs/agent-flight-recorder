# Security

## Deployment model — read this first

Agent Flight Recorder is a **local, self-hosted devtool**. It records the
most sensitive data your agent touches: prompts, tool arguments, results,
and state. Treat the database accordingly.

- **Default posture:** no auth, bound to `127.0.0.1` only (docker-compose
  publishes `127.0.0.1:8700`). Anyone who can reach the port can read every
  recorded payload — so don't let anyone reach the port.
- **Exposing it on a network:** set `AFR_API_TOKEN=<long random string>`
  (`Authorization: Bearer` or `X-AFR-Token` auth on every API route) **and**
  front it with TLS (reverse proxy). Set `AFR_CORS_ORIGINS` explicitly.
  Consider `AFR_DEMO_SEED_ENABLED=false`.
- **Secrets at rest:** default redaction is always on — key-based (`api_key`,
  `authorization`, `password`, `secret`, `access_token`, …) plus best-effort
  scrubbing of common secret shapes in free text (`sk-…`, `AKIA…`, JWTs, PEM
  keys, `Bearer …`, credentials in URLs). Best-effort is not a guarantee —
  don't log secrets into prompts.
- **Replay safety:** the server never executes user code. Replay execution
  happens in *your* process via your resume handler — use `ctx.call_tool`
  so side-effecting tools stay mocked/blocked per the plan.

## Reporting a vulnerability

For sensitive reports, use GitHub's **Report a vulnerability** form on the
repository's Security tab. It creates a private advisory visible only to the
maintainer and invited collaborators.

Use a public GitHub issue with the `security` label only for non-sensitive
hardening questions. There is no bug bounty, but reports are read and fixed.
