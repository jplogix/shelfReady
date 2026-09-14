import { expect, test } from "@playwright/test";

const API = process.env.E2E_API_URL || process.env.INTERNAL_API_URL || "http://localhost:8000";
const TOKEN = process.env.SHELFREADY_API_TOKEN || process.env.E2E_API_TOKEN || "dev-token-change-me";

async function waitForJob(jobId: string) {
  for (let i = 0; i < 60; i++) {
    const res = await fetch(`${API}/api/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    });
    const job = await res.json();
    if (["completed", "awaiting_decisions", "failed"].includes(job.status)) return job;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("job timeout");
}

test.describe("ShelfReady vertical slice", () => {
  test("sample → process → decisions → publish → cart → no duplicate", async ({ page }) => {
    await page.goto("/workspace");
    await expect(page.getByText("ShelfReady").first()).toBeVisible();
    await expect(page.getByText(/replay|live agent/i).first()).toBeVisible();

    await page.getByRole("button", { name: /Show dev batches/i }).click();
    await page.getByRole("button", { name: /Load stress-test catalog/i }).click();
    await page.waitForURL(/\/batches\//);
    const batchUrl = page.url();
    const batchId = batchUrl.split("/batches/")[1].split(/[?#]/)[0];

    await page.getByRole("button", { name: /Run processing/i }).click();
    // Poll job via API (worker must be running)
    const jobsRes = await fetch(`${API}/api/batches/${batchId}/jobs`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    });
    const jobs = await jobsRes.json();
    expect(jobs.length).toBeGreaterThan(0);
    await waitForJob(jobs[0].id);

    await page.reload();
    await expect(page.getByText(/awaiting_decisions|completed|processing/i).first()).toBeVisible();

    await page.getByRole("link", { name: /Decision inbox/i }).click();
    await expect(page.getByRole("heading", { name: /Decision inbox/i })).toBeVisible();

    // Resolve first pending with keyboard-friendly controls
    const approve = page.getByRole("button", { name: "Approve" }).first();
    if (await approve.isVisible()) {
      await approve.focus();
      await approve.press("Enter");
    }

    // Edit a missing price if present
    const editInput = page.getByLabel(/Edit value/i).first();
    if (await editInput.count()) {
      await editInput.fill("29.00");
      const save = page.getByRole("button", { name: /Save edit/i }).first();
      if (await save.isEnabled()) await save.click();
    }

    // Approve remaining publications (best-effort)
    for (let i = 0; i < 15; i++) {
      const btn = page.getByRole("button", { name: "Approve" }).first();
      if (!(await btn.count()) || !(await btn.isVisible())) break;
      await btn.click();
      await page.waitForTimeout(300);
    }

    await page.goto(`/batches/${batchId}`);
    await page.getByRole("button", { name: /Publish eligible/i }).click();
    const jobs2 = await (await fetch(`${API}/api/batches/${batchId}/jobs`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })).json();
    const pub = jobs2.find((j: { job_type: string }) => j.job_type === "publish") || jobs2[0];
    await waitForJob(pub.id);

    await page.goto("/store");
    await expect(page.getByText(/Demo storefront/i)).toBeVisible();

    const productLink = page.locator('a[href^="/store/products/"]').first();
    if (await productLink.count()) {
      await productLink.click();
      const add = page.getByRole("button", { name: /Add to cart/i });
      if (await add.isEnabled()) {
        await add.click();
        await expect(page.getByText(/Added to cart/i)).toBeVisible();
      }
    }

    // Republish idempotency
    const before = await (await fetch(`${API}/api/store/products`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })).json();
    await page.goto(`/batches/${batchId}`);
    await page.getByRole("button", { name: /Publish eligible/i }).click();
    const jobs3 = await (await fetch(`${API}/api/batches/${batchId}/jobs`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })).json();
    await waitForJob(jobs3[0].id);
    const after = await (await fetch(`${API}/api/store/products`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })).json();
    const slugsBefore = new Set(before.map((p: { slug: string }) => p.slug));
    const slugsAfter = after.map((p: { slug: string }) => p.slug);
    expect(new Set(slugsAfter).size).toBe(slugsAfter.length);
    for (const id of slugsBefore) {
      expect(slugsAfter.filter((x: string) => x === id).length).toBeLessThanOrEqual(1);
    }
  });
});
