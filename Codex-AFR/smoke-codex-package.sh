#!/usr/bin/env bash
# Smoke test for the Codex AFR harness + output capture + clean packaging.
# Uses a fake Codex binary and a throwaway backend DB so no OpenAI credits are
# spent and no real AFR state is polluted.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFR_BIN="${AFR_BIN:-$REPO_ROOT/.venv/bin/afr}"
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"

TMP_DIR="$(mktemp -d)"
SERVER_PID=""
PORT=""
FAILURES=0

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  FAILURES=$((FAILURES + 1))
}

PORT="$($PYTHON -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
API_URL="http://127.0.0.1:$PORT"

# Sentinel secrets that must never leak into a shareable package.
SECRET_OPENAI_KEY="sk-smoke-test-key-12345678901234567890"
SECRET_BEARER="smoke-bearer-token-1234567890abcdef"
SECRET_COOKIE="smoke-session-secret-12345"
SECRET_AUTH_PATH="/home/smoke/.codex/auth.json"
SECRET_PRIVATE_KEY="b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW"

# Fake Codex binary: prints output (including sentinel secrets) and exits cleanly.
FAKE_CODEX="$TMP_DIR/fake-codex"
cat > "$FAKE_CODEX" <<EOF
#!/usr/bin/env bash
echo "Fake Codex output for smoke test."
echo "Task complete."
echo "OPENAI_API_KEY=$SECRET_OPENAI_KEY"
echo "Authorization: Bearer $SECRET_BEARER"
echo "Cookie: session=$SECRET_COOKIE"
echo "Auth path: $SECRET_AUTH_PATH"
echo "-----BEGIN OPENSSH PRIVATE KEY-----"
echo "$SECRET_PRIVATE_KEY"
echo "-----END OPENSSH PRIVATE KEY-----"
exit 0
EOF
chmod +x "$FAKE_CODEX"

# Fake failing Codex binary to prove failed runs are excluded from packaging.
FAKE_CODEX_FAIL="$TMP_DIR/fake-codex-fail"
cat > "$FAKE_CODEX_FAIL" <<'EOF'
#!/usr/bin/env bash
echo "Fake Codex failure."
exit 1
EOF
chmod +x "$FAKE_CODEX_FAIL"

# Start an isolated AFR backend with a temp DB.
AFR_DB_PATH="$TMP_DIR/afr.db" \
  "$PYTHON" -m app --host 127.0.0.1 --port "$PORT" > "$TMP_DIR/server.log" 2>&1 &
SERVER_PID=$!
cd "$REPO_ROOT" || exit 1

for _ in $(seq 1 30); do
  if curl -sf "$API_URL/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

if ! curl -sf "$API_URL/health" >/dev/null; then
  fail "AFR backend failed to start on port $PORT"
  cat "$TMP_DIR/server.log" >&2 || true
  exit 1
fi

echo "AFR backend ready at $API_URL"

# Run the harness with the fake Codex binary in the temp AFR_ROOT.
AFR_ROOT="$TMP_DIR" \
AFR_API_URL="$API_URL" \
AFR_BIN="$AFR_BIN" \
CODEX_BIN="$FAKE_CODEX" \
"$REPO_ROOT/Codex-AFR/codexafr-harness" > "$TMP_DIR/harness.log" 2>&1
HARNESS_RC=$?

if [[ $HARNESS_RC -ne 0 ]]; then
  fail "Harness exited with code $HARNESS_RC"
  cat "$TMP_DIR/harness.log" >&2 || true
  exit 1
fi

run_id=""
if [[ -f "$TMP_DIR/harness.log" ]]; then
  run_id="$(grep -m1 '^AFR run: ' "$TMP_DIR/harness.log" | awk '{print $3}' || true)"
fi

if [[ -z "$run_id" ]]; then
  fail "Could not parse AFR run id from harness output"
  cat "$TMP_DIR/harness.log" >&2 || true
  exit 1
fi

prefix="${run_id%%-*}"
echo "Created completed run: $run_id (prefix $prefix)"

# Create a failed run to prove packaging excludes failed runs.
(
  cd "$TMP_DIR" || exit 1
  AFR_ROOT="$TMP_DIR" \
  AFR_API_URL="$API_URL" \
  AFR_BIN="$AFR_BIN" \
  CODEX_BIN="$FAKE_CODEX_FAIL" \
  "$REPO_ROOT/Codex-AFR/codexafr" --smoke-fail-arg > "$TMP_DIR/fail-run.log" 2>&1 || true
)
failed_run_id=""
if [[ -f "$TMP_DIR/fail-run.log" ]]; then
  failed_run_id="$(grep -m1 '^AFR run: ' "$TMP_DIR/fail-run.log" | awk '{print $3}' || true)"
fi
if [[ -n "$failed_run_id" ]]; then
  echo "Created failed run (should be excluded): $failed_run_id"
fi

# Add an unrelated stale transcript folder to prove it is excluded from packages.
mkdir -p "$TMP_DIR/.afr/codex/00000000-0000-0000-0000-000000000000"
echo "stale unrelated transcript" > "$TMP_DIR/.afr/codex/00000000-0000-0000-0000-000000000000/terminal-transcript.txt"

# Verify the output-tail event was recorded.
if ! "$AFR_BIN" -A "$API_URL" --json events "$run_id" 2>/dev/null \
    | grep -q '"name": "codex_output_tail"'; then
  fail "codex_output_tail event missing for run $run_id"
fi

# Verify idempotence: running the output-tail helper a second time must not
# create a duplicate event.
AFR_ROOT="$TMP_DIR" \
AFR_API_URL="$API_URL" \
AFR_BIN="$AFR_BIN" \
"$REPO_ROOT/Codex-AFR/afr-add-codex-output" "$run_id" > "$TMP_DIR/second-tail.log" 2>&1
SECOND_TAIL_RC=$?
if [[ $SECOND_TAIL_RC -ne 0 ]]; then
  fail "Second afr-add-codex-output call exited with code $SECOND_TAIL_RC"
  cat "$TMP_DIR/second-tail.log" >&2 || true
fi
if ! grep -qi "already has a codex_output_tail event" "$TMP_DIR/second-tail.log" 2>/dev/null; then
  fail "Second afr-add-codex-output did not report idempotent skip"
fi

# Count codex_output_tail events; there must be exactly one.
output_tail_count="$("$AFR_BIN" -A "$API_URL" --json events --type log "$run_id" 2>/dev/null \
  | grep -c '"name": "codex_output_tail"' || true)"
if [[ "$output_tail_count" != "1" ]]; then
  fail "Expected exactly one codex_output_tail event, found $output_tail_count"
fi

# Verify the clean package tarball was created.
TAR_PATH="$TMP_DIR/share/codex-clean-$prefix.tar.gz"
if [[ ! -f "$TAR_PATH" ]]; then
  fail "Clean package tarball not found: $TAR_PATH"
  cat "$TMP_DIR/harness.log" >&2 || true
  exit 1
fi

# Default package must NOT include the raw terminal transcript.
TAR_LIST="$(tar -tzf "$TAR_PATH" | sort)"
if echo "$TAR_LIST" | grep -q "terminal-transcript\.txt"; then
  fail "Default tarball unexpectedly contains raw terminal-transcript.txt"
fi

# Verify the default tarball contains exactly the expected entries.
EXPECTED_ENTRIES="codex-clean-$prefix/
codex-clean-$prefix/codex-trace-$prefix.json
codex-clean-$prefix/receipt.json"
ENTRIES_DIFF="$(echo "$TAR_LIST" | diff - <(echo "$EXPECTED_ENTRIES" | sort) || true)"
if [[ -n "$ENTRIES_DIFF" ]]; then
  fail "Tarball contents do not match expected entries"
  echo "$ENTRIES_DIFF" >&2
fi

if echo "$TAR_LIST" | grep -q "00000000-0000-0000-0000-000000000000"; then
  fail "Tarball contains unrelated stale transcript folder"
fi
if echo "$TAR_LIST" | grep -q "\.afr/codex"; then
  fail "Tarball contains raw .afr/codex path"
fi

# Extract and validate receipt.json.
RECEIPT_JSON="$(tar -xOzf "$TAR_PATH" "codex-clean-$prefix/receipt.json" 2>/dev/null || true)"
if [[ -z "$RECEIPT_JSON" ]]; then
  fail "receipt.json missing from tarball or could not be extracted"
fi

receipt_has_field() {
  local field="$1"
  echo "$RECEIPT_JSON" | grep -q "\"$field\":"
}

for field in run_id export_path package_path package_sha256 raw_transcript_is_sensitive raw_transcript_included redacted; do
  if ! receipt_has_field "$field"; then
    fail "receipt.json missing required field: $field"
  fi
done

if ! echo "$RECEIPT_JSON" | grep -q '"raw_transcript_is_sensitive": true'; then
  fail "receipt.json does not set raw_transcript_is_sensitive=true"
fi

if ! echo "$RECEIPT_JSON" | grep -q '"raw_transcript_included": false'; then
  fail "receipt.json does not set raw_transcript_included=false by default"
fi

if ! echo "$RECEIPT_JSON" | grep -q '"redacted": true'; then
  fail "receipt.json does not mark package as redacted"
fi

if [[ "$(echo "$RECEIPT_JSON" | grep -c '"run_id":')" -ne 1 ]]; then
  fail "receipt.json run_id field is not unique"
fi
receipt_run_id="$(echo "$RECEIPT_JSON" | grep '"run_id":' | head -1 | sed -E 's/.*"run_id": *"([^"]+)".*/\1/')"
if [[ "$receipt_run_id" != "$run_id" ]]; then
  fail "receipt.json run_id ($receipt_run_id) does not match packaged run ($run_id)"
fi

# Verify the exported trace references codex metadata.
EXPORT_JSON="$(tar -xOzf "$TAR_PATH" "codex-clean-$prefix/codex-trace-$prefix.json" 2>/dev/null || true)"
if [[ -z "$EXPORT_JSON" ]]; then
  fail "Could not extract exported trace for codex metadata check"
fi
if ! echo "$EXPORT_JSON" | grep -qi '"agent": *"codex"'; then
  fail "Exported trace does not reference agent=codex"
fi

# The default package must contain no sentinel secrets.
TAR_TEXT="$(tar -xOzf "$TAR_PATH" 2>/dev/null || true)"
for sentinel in "$SECRET_OPENAI_KEY" "$SECRET_BEARER" "$SECRET_COOKIE" "$SECRET_AUTH_PATH" "$SECRET_PRIVATE_KEY"; do
  if echo "$TAR_TEXT" | grep -qF "$sentinel"; then
    fail "Sanitized tarball leaked sentinel secret: $sentinel"
  fi
done

# Now build an opt-in package that includes the redacted transcript.
OPTIN_TAR_PATH="$TMP_DIR/share/codex-clean-$prefix-raw.tar.gz"
AFR_ROOT="$TMP_DIR" \
AFR_API_URL="$API_URL" \
AFR_BIN="$AFR_BIN" \
"$REPO_ROOT/Codex-AFR/afr-package-latest-codex" --include-raw-transcript "$run_id" > "$TMP_DIR/optin-package.log" 2>&1
OPTIN_RC=$?
if [[ $OPTIN_RC -ne 0 ]]; then
  fail "Opt-in package build exited with code $OPTIN_RC"
  cat "$TMP_DIR/optin-package.log" >&2 || true
fi

OPTIN_TAR_LIST="$(tar -tzf "$OPTIN_TAR_PATH" 2>/dev/null | sort || true)"
if ! echo "$OPTIN_TAR_LIST" | grep -q "terminal-transcript\.txt"; then
  fail "Opt-in tarball does not contain terminal-transcript.txt"
fi

OPTIN_TAR_TEXT="$(tar -xOzf "$OPTIN_TAR_PATH" 2>/dev/null || true)"
for sentinel in "$SECRET_OPENAI_KEY" "$SECRET_BEARER" "$SECRET_COOKIE" "$SECRET_AUTH_PATH" "$SECRET_PRIVATE_KEY"; do
  if echo "$OPTIN_TAR_TEXT" | grep -qF "$sentinel"; then
    fail "Opt-in redacted tarball leaked sentinel secret: $sentinel"
  fi
done

OPTIN_RECEIPT_JSON="$(tar -xOzf "$OPTIN_TAR_PATH" "codex-clean-$prefix-raw/receipt.json" 2>/dev/null || true)"
if ! echo "$OPTIN_RECEIPT_JSON" | grep -q '"raw_transcript_included": true'; then
  fail "Opt-in receipt.json does not set raw_transcript_included=true"
fi

# Verify the receipt notes the transcript is sensitive.
if ! echo "$RECEIPT_JSON" | grep -qi "sensitive"; then
  fail "receipt does not note that the raw transcript is sensitive"
fi

if [[ $FAILURES -gt 0 ]]; then
  echo "FAIL ($FAILURES failure(s))"
  exit 1
fi

echo "PASS"
exit 0
