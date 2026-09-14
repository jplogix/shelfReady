import { expect, test } from "@playwright/test";

test.describe("ShelfReady Seiko storefront", () => {
  test("featured product → cart quantity → removal → preparation evidence", async ({ page }) => {
    await page.goto("/store");
    await expect(page.getByRole("heading", { name: "Seiko demonstration collection" })).toBeVisible();
    await expect(page.getByText(/not affiliated with, sponsored by, or endorsed by Seiko/i)).toBeVisible();

    const hero = page.getByRole("link", { name: /Seiko 5 Sports SRPD55/i }).first();
    await expect(hero).toBeVisible();
    await hero.click();

    await expect(page.getByRole("heading", { name: /Seiko 5 Sports SRPD55/i })).toBeVisible();
    await expect(page.getByText("USD 229.00")).toBeVisible();
    await expect(page.getByText(/merchant demo price/i)).toBeVisible();
    await expect(page.getByText(/In stock \(12\)/i)).toBeVisible();
    const productImage = page.locator("img").first();
    await expect(productImage).toBeVisible();
    await expect.poll(() => productImage.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);

    await page.getByRole("button", { name: /Add Seiko 5 Sports SRPD55 to cart/i }).click();
    await expect(page.getByRole("status")).toHaveText("Added to cart");
    await page.getByRole("link", { name: "View cart" }).click();

    await expect(page.getByRole("heading", { name: "Cart" })).toBeVisible();
    await expect(page.getByText("Demo cart—no payment or checkout.", { exact: false })).toBeVisible();
    const quantity = page.getByLabel("Quantity");
    await quantity.fill("2");
    await expect(page.getByText(/Subtotal \(2 items\): USD 458.00/)).toBeVisible();
    await page.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByText(/Cart is empty/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Continue shopping" })).toBeVisible();

    await page.goto("/store");
    await page.getByRole("link", { name: /Seiko 5 Sports SRPD55/i }).first().click();
    await page.getByRole("link", { name: "See how this listing was prepared" }).click();
    await expect(page.getByRole("heading", { name: "See how this listing was prepared" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Original supplier row" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Accepted corrections" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Supporting evidence" })).toBeVisible();
    await expect(page.getByText(/Added a product photo/i)).toBeVisible();
  });
});
