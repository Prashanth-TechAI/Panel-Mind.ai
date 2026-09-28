import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

/**
 * The account pages.
 *
 * Two things are being defended here, and both are about honesty rather than
 * layout:
 *
 *   * A "Verified" badge means a code sent to that contact came back correct.
 *     Nothing else earns it, and changing the contact takes it away.
 *   * No control claims something the server did not do. The WhatsApp switch
 *     is locked until the number is proved, and when it flips it reports
 *     whether a message actually went out.
 *
 * The DAF half checks the same principle from the other side: an uploaded PDF
 * is handed back byte for byte, never re-typed into our own fields.
 */

const API =
  process.env.E2E_API_URL ?? `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8100}`;

test.describe("profile", () => {
  test("verifies the second contact and only then unlocks WhatsApp", async ({ page }) => {
    await signIn(page);
    await page.goto("/me");

    // Signing in by email proves the email; the phone was typed in afterwards
    // and nobody has proved it.
    await expect(page.getByTestId("email-verified")).toBeVisible();
    await expect(page.getByTestId("phone-unverified")).toBeVisible();

    // A number nobody has proved they hold must not be messageable.
    await expect(page.getByTestId("whatsapp-toggle")).toBeDisabled();
    await expect(page.getByTestId("whatsapp-blocked")).toBeVisible();

    await page.getByTestId("verify-phone").click();
    await expect(page.getByTestId("verify-panel-phone")).toBeVisible();

    // The development code is filled in for the aspirant rather than printed
    // to a log they cannot see.
    await expect(page.getByTestId("code-phone")).toHaveValue(/^\d{6}$/);
    await page.getByTestId("confirm-phone").click();

    await expect(page.getByTestId("phone-verified")).toBeVisible();
    await expect(page.getByTestId("whatsapp-toggle")).toBeEnabled();
  });

  test("a wrong code does not verify anything", async ({ page }) => {
    await signIn(page);
    await page.goto("/me");

    await page.getByTestId("verify-phone").click();
    await page.getByTestId("code-phone").fill("000000");
    await page.getByTestId("confirm-phone").click();

    await expect(page.getByTestId("profile-error")).toBeVisible();
    await expect(page.getByTestId("phone-unverified")).toBeVisible();
  });

  test("the WhatsApp switch stores a real preference and says what it did", async ({ page }) => {
    await signIn(page);
    await page.goto("/me");

    await page.getByTestId("verify-phone").click();
    await page.getByTestId("confirm-phone").click();
    await expect(page.getByTestId("phone-verified")).toBeVisible();

    await page.getByTestId("whatsapp-toggle").click();
    await expect(page.getByTestId("whatsapp-toggle")).toHaveAttribute("aria-checked", "true");

    // It must never report a send that did not happen.
    const note = await page.getByTestId("whatsapp-note").innerText();
    expect(note).toMatch(/Confirmation sent|nothing has been sent/);

    // And the preference has to survive the page, not just the component.
    const token = await page.evaluate(() => localStorage.getItem("panelmind.token"));
    const profile = await page.request.get(`${API}/api/me/profile`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect((await profile.json()).user.whatsapp_opt_in).toBe(true);
  });

  test("awards are earned, not granted", async ({ page }) => {
    await signIn(page);
    await page.goto("/me");

    // A brand-new account has sat nothing, so it holds nothing.
    await expect(page.getByTestId("awards")).toBeVisible();
    const held = await page.locator('[data-testid^="award-"][data-held="true"]').count();
    expect(held).toBe(0);
  });

  test("a photograph is stored and served back", async ({ page }) => {
    await signIn(page);
    await page.goto("/me");

    await expect(page.getByTestId("avatar-initials")).toBeVisible();
    await page.getByTestId("avatar-file").setInputFiles({
      name: "photo.png",
      mimeType: "image/png",
      // A 1x1 PNG. The bytes only have to survive the round trip.
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      ),
    });

    await expect(page.getByTestId("avatar-image")).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("your DAF", () => {
  test("shows a typed form field by field, and exports it as a DAF-I", async ({ page }) => {
    await signIn(page);
    await page.getByTestId("daf-specimen").click();
    await page.getByTestId("daf-submit").click();
    await page.waitForURL("**/daf/review");

    await page.goto("/me/daf");
    await expect(page.getByTestId("daf-form-view")).toBeVisible();
    await expect(page.getByText("Preetam Kumar")).toBeVisible();

    // The export must be a real eight-page PDF, not a link to nowhere.
    const href = await page.getByTestId("daf-export").getAttribute("href");
    const pdf = await page.request.get(href!);
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toContain("application/pdf");

    const body = await pdf.body();
    expect(body.subarray(0, 5).toString()).toBe("%PDF-");
    expect(body.toString("latin1").match(/\/Type\s*\/Page[^s]/g)?.length).toBe(8);
  });

  test("says so plainly when no form has been given", async ({ page }) => {
    await signIn(page);
    await page.goto("/me/daf");
    await expect(page.getByTestId("daf-empty")).toBeVisible();
  });
});
