import { expect, test } from "@playwright/test";

test.describe("ShelfReady Seiko preparation", () => {
  test("supplier rows → preparation → recommended fixes", async ({ page }) => {
    await page.goto("/");
    const primaryCta = page.getByRole("link", { name: "Browse published products" });
    await expect(primaryCta).toBeVisible();
    const colors = await primaryCta.evaluate((element) => ({
      button: getComputedStyle(element).backgroundColor,
      page: getComputedStyle(document.body).backgroundColor,
    }));
    expect(colors.button).not.toBe(colors.page);

    await page.goto("/workspace");
    await page.getByRole("button", { name: "Try Seiko demonstration" }).click();

    await expect(page.getByRole("heading", { name: /Seiko demonstration/ })).toBeVisible();
    await expect(page.getByText("USD 229.00").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Prepare products" })).toBeVisible();

    await page.getByRole("button", { name: "Prepare products" }).click();
    await expect(page.getByRole("button", { name: "Preparing products…" })).toBeDisabled();
    const applyFixes = page.getByRole("button", { name: "Apply recommended fixes" });
    await expect(applyFixes).toBeVisible({ timeout: 120_000 });

    await applyFixes.click();
    await expect(page.getByText(/Applied \d+ evidence-backed fixes/)).toBeVisible();
    await expect(page.getByText(/3 products are ready to publish; 4 decisions across 2 products/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Review and publish (3)" })).toBeVisible();
    const reviewIssues = page.getByRole("link", { name: "Review 4 remaining issues" });
    await expect(reviewIssues).toBeVisible();
    await reviewIssues.click();
    await expect(page.getByText("Product workspace")).toBeVisible();
    await expect(page.getByRole("button", { name: "Evidence & decisions" })).toHaveClass(/border-charcoal/);
    const transformation = page.getByRole("link", { name: "View full transformation" });
    await expect(transformation).toBeVisible();
    await transformation.click();
    await expect(page.getByText("Product workbench")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Original supplier record" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Proposed listing" })).toBeVisible();
  });
});
