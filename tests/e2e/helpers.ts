import { type Page } from "@playwright/test";

const API =
  process.env.E2E_API_URL ?? `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8100}`;

/** Distinct per call: parallel workers must not collide on one identity. */
function unique(): string {
  return `${Date.now()}${Math.floor(Math.random() * 1e6)}`;
}

/**
 * Put a signed-in account into the browser.
 *
 * Goes through the real OTP endpoints — so the auth flow is genuinely
 * exercised — then injects the resulting session directly. Driving the
 * three-step form for every test that merely needs a signed-in user made the
 * suite slow and flaky; `signInThroughUi` still covers the form itself.
 */
export async function signIn(page: Page): Promise<void> {
  const email = `t${unique()}@example.com`;
  const phone = `9${Math.floor(Math.random() * 9e8 + 1e8)}`;

  const start = await page.request.post(`${API}/api/auth/start`, {
    data: { identifier: email },
  });
  const { dev_code } = await start.json();

  const verified = await page.request.post(`${API}/api/auth/verify`, {
    data: { identifier: email, code: dev_code },
  });
  const { token } = await verified.json();

  await page.request.post(`${API}/api/auth/profile`, {
    data: { name: "Rohit Sharma", phone },
    headers: { Authorization: `Bearer ${token}` },
  });

  // Seed the session before any script runs, so the first render is signed in.
  await page.addInitScript((value) => {
    localStorage.setItem("panelmind.token", value as string);
  }, token);

  await page.goto("/daf");
  await page.getByTestId("daf-form").waitFor({ timeout: 30_000 });
}

/** Drives the sign-in form itself, for the tests that are about the form. */
export async function signInThroughUi(
  page: Page,
  identifier = `t${unique()}@example.com`,
): Promise<void> {
  await page.goto("/signin");
  await page.getByTestId("phone-input").fill(identifier);
  await page.getByTestId("send-code").click();

  // In development the code arrives filled in and submits itself the moment
  // six digits are present, so the code step can be gone before a fill lands.
  // Waiting for whichever step comes next is what makes this stable.
  await Promise.race([
    page.getByTestId("step-profile").waitFor({ timeout: 30_000 }),
    page.getByTestId("profile-button").waitFor({ timeout: 30_000 }),
  ]);

  if (await page.getByTestId("step-profile").isVisible().catch(() => false)) {
    await page.getByTestId("name-input").fill("Rohit Sharma");
    if (await page.getByTestId("email-input").isVisible().catch(() => false)) {
      await page.getByTestId("email-input").fill(`e${unique()}@example.com`);
    }
    if (await page.getByTestId("profile-phone-input").isVisible().catch(() => false)) {
      await page
        .getByTestId("profile-phone-input")
        .fill(`9${Math.floor(Math.random() * 9e8 + 1e8)}`);
    }
    await page.getByTestId("save-profile").click();
  }

  await page.getByTestId("profile-button").waitFor({ timeout: 30_000 });
}
