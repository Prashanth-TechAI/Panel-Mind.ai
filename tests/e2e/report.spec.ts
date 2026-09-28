import { test, expect, type APIRequestContext } from "@playwright/test";

async function tokenFor(request: APIRequestContext): Promise<string> {
  const id = `t${Date.now()}@example.com`;
  const start = await request.post(`${API}/api/auth/start`, { data: { identifier: id } });
  const { dev_code } = await start.json();
  const verified = await request.post(`${API}/api/auth/verify`, {
    data: { identifier: id, code: dev_code },
  });
  return (await verified.json()).token;
}

const API = process.env.E2E_API_URL ?? `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8100}`;

const DAF = {
  full_name: "Rohit Sharma",
  home_state: "Uttar Pradesh",
  home_district: "Jhansi",
  education: {
    graduation_subject: "Mechanical Engineering",
    graduation_college: "IIT Kanpur",
  },
  optional_subject: "Sociology",
  hobbies: ["Reading historical fiction", "Long-distance running"],
  service_preference: ["IAS", "IPS"],
  work_experience: ["Two years at ISRO"],
  positions_of_responsibility: ["NSS unit secretary"],
  attempt_number: 2,
};

/**
 * A short interview with deliberately mixed quality: one honest "I don't know",
 * one confident factual error to catch the bluff detector, and one ramble.
 */
const EXCHANGES: [string, string | null, string][] = [
  ["Chairman", "M0", "Please, come in. Tell us what brought you here."],
  ["You", null, "Sir, I want to work on rural administration. My district still has water problems."],
  ["Shri Rathore", "M2", "What is the biggest administrative failure in Jhansi?"],
  ["You", null, "Water management, sir. The Bundelkhand package money did not reach the ground."],
  ["Shri Rathore", "M2", "Whose failure was that?"],
  ["You", null, "I don't know the specifics of who was responsible, sir. I would not want to guess."],
  ["Dr. Menon", "M3", "When was NITI Aayog set up?"],
  ["You", null, "NITI Aayog was set up in 2012, sir, replacing the Planning Commission."],
  ["Dr. Menon", "M3", "Hmm. Are you certain about that year?"],
  ["You", null, "Yes sir, I am confident it was 2012."],
  ["Chairman", "M0", "Thank you. Your interview is over."],
];

async function seedInterview(request: APIRequestContext, token: string): Promise<string> {
  const created = await request.post(`${API}/api/session`, { data: DAF, timeout: 180_000, headers: { Authorization: `Bearer ${token}` } });
  expect(created.ok(), `session creation failed: ${await created.text()}`).toBe(true);
  const { session_id } = await created.json();

  for (const [speaker, member_id, text] of EXCHANGES) {
    const res = await request.post(`${API}/api/session/${session_id}/transcript`, {
      data: { speaker, member_id, text, at_ms: 0 },
    });
    expect(res.ok()).toBe(true);
  }

  await request.post(`${API}/api/session/${session_id}/end?reason=interview_complete`);
  return session_id;
}

test.describe("scorecard guards", () => {
  test("says so when no interview is specified", async ({ page }) => {
    await page.goto("/report");
    await expect(page.getByTestId("report-error")).toContainText(/no interview specified/i);
  });

  test("refuses to mark an interview that was never sat", async ({ request, page }) => {
    const created = await request.post(`${API}/api/session`, {
      data: DAF,
      timeout: 180_000,
      headers: { Authorization: `Bearer ${await tokenFor(request)}` },
    });
    const { session_id } = await created.json();

    await page.goto(`/report?session=${session_id}`);

    // No transcript means nothing to score — it must say that, not invent marks.
    await expect(page.getByTestId("report-error")).toContainText(/nothing to score/i);
    await expect(page.getByTestId("consolidated-marks")).toHaveCount(0);
  });
});

test.describe("@live the board marks the candidate", () => {
  test.setTimeout(420_000);

  test("produces five independent scorecards and a consolidated mark", async ({
    request,
    page,
  }) => {
    const sessionId = await seedInterview(request, await tokenFor(request));

    await page.goto(`/report?session=${sessionId}`);
    await expect(page.getByTestId("marking")).toBeVisible();

    const report = page.getByTestId("report");
    await expect(report).toBeVisible({ timeout: 300_000 });

    // A real mark, in the range a real board awards.
    const marks = Number(await page.getByTestId("consolidated-marks").innerText());
    expect(marks).toBeGreaterThan(60);
    expect(marks).toBeLessThanOrEqual(275);

    // All five members marked independently.
    for (const name of ["Chairman", "Prof. Iyer", "Shri Rathore", "Dr. Menon", "Dr. Kaur"]) {
      await expect(report).toContainText(name);
    }

    // All seven official traits scored.
    for (const trait of [
      "Mental alertness",
      "Critical assimilation",
      "Clear exposition",
      "Balance of judgement",
      "Depth of interest",
      "Social cohesion",
      "Moral integrity",
    ]) {
      await expect(report).toContainText(trait);
    }

    // The measured signals are real: the candidate said "I don't know" once.
    await expect(report).toContainText("How you spoke");
    await expect(report).toContainText(/1×/);

    // An AI mark must never be presented as a UPSC mark.
    await expect(report).toContainText(/not calibrated against actual UPSC marks/i);
  });

  test("offers a table view so identity is never colour-alone", async ({ request, page }) => {
    const sessionId = await seedInterview(request, await tokenFor(request));
    await page.goto(`/report?session=${sessionId}`);
    await expect(page.getByTestId("report")).toBeVisible({ timeout: 300_000 });

    await page.getByRole("button", { name: /show table/i }).click();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByRole("table")).toContainText("/ 10");
  });
});
