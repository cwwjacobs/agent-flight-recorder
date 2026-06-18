# Kimi smoke test

`scripts/smoke-kimi-package.sh` exercises the full Kimi Code capture and
packaging flow without spending real Kimi credits.

## What the smoke test proves

The script:

1. Starts an isolated AFR backend on a throwaway database.
2. Replaces the Kimi Code binary with a tiny fake that prints a fixed message
   and exits cleanly.
3. Runs the real `scripts/afr-kimi-harness`, which records a run, adds a
   `kimi_output_tail` event, and builds a clean share package.
4. Verifies the `kimi_output_tail` event is present.
5. Runs `scripts/afr-add-kimi-output` a second time and confirms it is
   idempotent: it exits 0 and does **not** create a duplicate event.
6. Verifies the clean tarball contains exactly the expected four entries:
   `kimi-clean-<prefix>/`, `kimi-trace-<prefix>.json`, `receipt.json`, and
   `terminal-transcript.txt`.
7. Validates `receipt.json` fields, including `raw_transcript_is_sensitive: true`.
8. Confirms failed runs and stale transcript folders are excluded from the
   package.
9. Confirms the supported Kimi Code flow does not reference a `kimi-cli` path.

## No real credits are spent

The smoke test never invokes the real Kimi Code binary. It uses a fake binary
and a local backend, so no API calls or Kimi credits are consumed. You can run
it repeatedly and safely in CI.

## Why a smoke run may not appear in the main AFR database

`smoke-kimi-package.sh` sets `AFR_ROOT` to a temporary directory and starts its
own backend with `AFR_DB_PATH` pointing at a temp SQLite file. Because the smoke
backend is isolated, the smoke run is stored only in that temporary database.
It does **not** mix with runs recorded by a persistent local backend on the
real project database (`afr.db` in the repo root).

To inspect a smoke run while the test is running, you would need to query the
smoke backend URL printed by the script. Once the script exits, the temp
directory and its database are removed.

## Packaging a real completed run

After you have run Kimi Code through AFR and the run status is `completed`:

```bash
# Add the output-tail event if it is missing (idempotent; safe to rerun)
scripts/afr-add-kimi-output <run-id-or-prefix>

# Build the clean share package
scripts/afr-package-latest-kimi <run-id-or-prefix>
```

The package is written to `share/kimi-clean-<prefix>.tar.gz` and contains only
 the export JSON, the terminal transcript, and a receipt with checksums and
provenance.
