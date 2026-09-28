import { test, expect } from "@playwright/test";
import { signIn, signInThroughUi } from "./helpers";

/**
 * The board room, end to end.
 *
 * These run against the real Python control plane and real speech providers.
 * A dead key or an exhausted quota fails the build here rather than surfacing
 * to an aspirant mid-interview.
 */

const MEMBERS = [
  { id: "M0", name: "Chairman" },
  { id: "M1", name: "Prof. Iyer" },
  { id: "M2", name: "Shri Rathore" },
  { id: "M3", name: "Dr. Menon" },
  { id: "M4", name: "Dr. Kaur" },
];

test.describe("landing", () => {
  test("opens on the stakes, not on a feature list", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: /two hundred marks are decided/i }),
    ).toBeVisible();
    await expect(page.getByTestId("cta-daf")).toBeVisible();
  });

  test("never introduces the board before the room does", async ({ page }) => {
    // Naming the members here would let an aspirant rehearse for whoever is
    // about to speak, which removes the pressure this product exists to
    // reproduce. The landing page deliberately does not do it.
    await page.goto("/");
    const body = await page.locator("body").innerText();
    for (const member of MEMBERS.slice(1)) {
      expect(body, `landing page names ${member.name}`).not.toContain(member.name);
    }
  });

  test("never names the services behind the product", async ({ page }) => {
    await page.goto("/");
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const vendor of ["deepgram", "elevenlabs", "openrouter", "groq", "livekit"]) {
      expect(body, `UI leaks the vendor name "${vendor}"`).not.toContain(vendor);
    }
  });

  test("routes to the DAF intake", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("cta-daf").click();
    await expect(page).toHaveURL(/\/daf$/);
  });
});

test.describe("sign in", () => {
  test("takes a new aspirant from an identifier to a prepared form", async ({ page }) => {
    await signInThroughUi(page);
    await expect(page.getByTestId("profile-button")).toBeVisible();
  });
});

test.describe("DAF intake", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("accepts a form and carries it to the review step", async ({ page }) => {
    await page.getByTestId("daf-specimen").click();
    await page.getByTestId("daf-submit").click();

    // Both ways in — typed or uploaded — land on the same review page.
    await expect(page).toHaveURL(/\/daf\/review$/);
    await expect(page.getByTestId("confirm-read")).toBeVisible();

    // The aspirant's own answers survived the hop.
    const body = await page.locator("main").innerText();
    expect(body).toContain("Mathematics");
    expect(body).toContain("Rajasthan");

    // Convening is gated until they say they have checked the form.
    await expect(page.getByTestId("convene")).toBeDisabled();
  });

  test("rejects a form the board could not interview from", async ({ page }) => {
    // Hobbies left blank: the board always probes them, so it must not pass.
    await page.getByTestId("daf-specimen").click();
    await page.getByRole("textbox", { name: /hobbies/i }).fill("");
    await page.getByTestId("daf-submit").click();

    // Native validation blocks submission — the review step is never reached.
    await expect(page).toHaveURL(/\/daf$/);
  });
});

test.describe("resilience", () => {
  test("states the outage plainly when the control plane is down", async ({ page }) => {
    // The DAF submit is a browser-side call, so it is genuinely interceptable.
    // (The landing page fetches during SSR and cannot be routed from here.)
    await signIn(page);
    await page.getByTestId("daf-specimen").click();
    // Blocked only now — the sign-in above needs the API to reach the form.
    await page.route("**/api/daf", (route) => route.abort());

    await page.getByTestId("daf-submit").click();

    const error = page.getByTestId("daf-error");
    await expect(error).toBeVisible();
    await expect(error).toContainText(/could not reach|failed/i);

    // The form survives the failure with the candidate's answers intact.
    await expect(page.getByRole("textbox", { name: /full name/i })).toHaveValue(
      "Preetam Kumar",
    );
  });

  test("has no horizontal overflow on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, "page scrolls sideways on mobile").toBe(false);
  });
});
