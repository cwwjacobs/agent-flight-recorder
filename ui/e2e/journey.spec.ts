import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

/**
 * Browser smoke journey over a seeded >10k-event run:
 *   run list → run detail → paginated timeline → checkpoint state →
 *   replay plan → export.
 *
 * Export has no UI surface (the UI api client has no export method; the
 * backend has no export endpoint — the SDK/CLI composes bundles from the
 * paginated read endpoints). The export leg therefore runs through the
 * repo's real export implementation (`afr export`, the CLI) against the
 * same live server this journey drives in the browser.
 */

const seed = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "e2e", ".seed.json"), "utf-8"),
) as {
  run_id: string;
  run_name: string;
  total_events: number;
  checkpoints: { id: string; label: string; event_seq: number }[];
  tools: string[];
  last_progress: number;
};

test("run → paginated timeline → checkpoint → replay plan → export", async ({
  page,
  baseURL,
}) => {
  expect(seed.total_events).toBeGreaterThan(10_000);

  // -- run: the seeded run is listed with its full event count --------------
  await page.goto("/");
  const row = page.getByRole("row").filter({ hasText: seed.run_name });
  await expect(row).toBeVisible();
  await expect(row.locator(".chip").first()).toHaveText(String(seed.total_events));
  await row.click();

  // -- paginated timeline: the UI pages through >10k events (10k/page) ------
  const timelineHead = page.locator(".panel-head", { hasText: "Timeline" });
  await expect(timelineHead.locator(".microlabel")).toHaveText(
    `${seed.total_events} events`,
  );
  // Both ends of the merged multi-page timeline actually render.
  await expect(page.getByText("#001", { exact: true })).toBeVisible();
  const lastSeq = page.getByText(`#${seed.total_events}`, { exact: true });
  await lastSeq.scrollIntoViewIfNeeded();
  await expect(lastSeq).toBeVisible();
  // A mid-run event from beyond the first 10k API page is present too.
  await expect(
    page.locator(".tl-name", { hasText: "tick-10299" }),
  ).toBeVisible();

  // -- checkpoint: browse checkpoints, inspect stored state -----------------
  const finalCheckpoint = seed.checkpoints.find((c) => c.label === "final");
  expect(finalCheckpoint).toBeTruthy();
  await expect(page.locator(".ckpt-row")).toHaveCount(seed.checkpoints.length);
  await page.locator("#ckpt-select").selectOption(finalCheckpoint!.id);
  const statePanel = page.locator(".panel-ticks", { hasText: "State @ Checkpoint" });
  await expect(statePanel).toContainText("source: stored with the checkpoint");
  await expect(statePanel.locator(".jt-key", { hasText: "progress" })).toBeVisible();
  await expect(
    statePanel.locator(".jt-number", { hasText: String(seed.last_progress) }),
  ).toBeVisible();

  // -- replay plan: ready ticket with a per-tool safety plan ----------------
  await page.locator("#replay-ckpt").selectOption(finalCheckpoint!.id);
  await page.locator("#replay-mode").selectOption("mock_tools");
  await page.getByRole("button", { name: "▶ Prepare replay plan" }).click();
  const result = page.locator(".replay-result");
  await expect(result).toContainText("status: ready");
  await expect(result).toContainText("mode: mock_tools");
  for (const tool of seed.tools) {
    await expect(page.locator(".plan-table")).toContainText(tool);
  }
  await expect(page.locator(".plan-action").first()).toHaveText("mock");

  // -- export: repo's real export path against the same live server ---------
  const repoRoot = path.resolve(process.cwd(), "..");
  const cli = process.env.AFR_CLI ?? path.join(repoRoot, ".venv", "bin", "afr");
  if (!fs.existsSync(cli)) {
    throw new Error(
      `afr CLI not found at ${cli} — run make install first (or set AFR_CLI)`,
    );
  }
  const outFile = path.join(process.cwd(), "e2e", ".export.json");
  execFileSync(cli, ["-A", String(baseURL), "export", seed.run_id, "-o", outFile], {
    stdio: "pipe",
  });
  const bundle = JSON.parse(fs.readFileSync(outFile, "utf-8"));
  expect(bundle.format).toBe("afr.export.v1");
  expect(bundle.run.id).toBe(seed.run_id);
  // The replay-plan leg above appended one replay_requested log event.
  expect(bundle.events).toHaveLength(seed.total_events + 1);
  expect(bundle.events[0].seq).toBe(1);
  expect(bundle.events[bundle.events.length - 1].name).toBe("replay_requested");
  expect(bundle.checkpoints.map((c: { id: string }) => c.id).sort()).toEqual(
    seed.checkpoints.map((c) => c.id).sort(),
  );
});
