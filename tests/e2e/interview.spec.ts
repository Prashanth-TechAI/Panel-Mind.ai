import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

/**
 * The room.
 *
 * The guard tests run always. The full-loop test is tagged @live: it convenes
 * a real board (five LLM calls), joins a real LiveKit room and waits for the
 * Chairman to actually speak. It needs the voice worker running:
 *
 *   cd backend && uv run python -m agent.worker dev
 */

test.describe("entering the room", () => {
  test("refuses to seat a candidate with no prepared interview", async ({ page }) => {
    await page.goto("/interview");
    await page.getByTestId("join").click();

    const error = page.getByTestId("join-error");
    await expect(error).toBeVisible();
    await expect(error).toContainText(/no interview is prepared/i);

    // It must point them at the fix rather than dead-ending.
    await expect(page.getByRole("link", { name: /fill your form/i })).toBeVisible();
  });

  test("shows the room is not convened before joining", async ({ page }) => {
    await page.goto("/interview");

    await expect(page.getByTestId("phase")).toContainText(/not convened/i);
    await expect(page.getByTestId("clock")).toContainText("00:00");
    await expect(page.getByTestId("transcript")).toHaveCount(0);
  });

  test("asks to be let in, and says why it cannot yet", async ({ page }) => {
    await page.goto("/interview");

    // Arriving with nothing prepared, the page leads with that rather than
    // with the microphone warning — which belongs to a room that exists.
    await expect(page.getByTestId("join")).toContainText(/may i come in/i);
    await expect(page.getByTestId("join-error")).toContainText(
      /no interview is prepared/i,
    );
  });
});

test.describe("@live full interview loop", () => {
  // Convening the board is five cold-tier LLM calls, then a real room join.
  test.setTimeout(240_000);

  test("the board convenes, seats itself, and the Chairman opens", async ({ page }) => {
    await signIn(page);
    await page.getByTestId("daf-specimen").click();
    await page.getByTestId("daf-submit").click();
    await expect(page).toHaveURL(/\/daf\/review$/);
    await page.getByTestId("confirm-read").check();

    // Five members read the file and build their question trees. Slow by design.
    await page.getByTestId("convene").click();
    await expect(page).toHaveURL(/\/interview$/, { timeout: 120_000 });

    await page.getByTestId("join").click();

    // The worker has to accept the job, seat the board and open. If the
    // Chairman never speaks, the voice plane is not actually wired.
    const transcript = page.getByTestId("transcript");
    await expect(transcript).toBeVisible({ timeout: 30_000 });
    await expect(transcript).toContainText(/have a seat/i, { timeout: 90_000 });

    // The Chairman holds the mic and nobody else does.
    await expect(page.getByTestId("seat-M0")).toHaveAttribute("data-speaking", "true", {
      timeout: 30_000,
    });
    for (const member of ["M1", "M2", "M3", "M4"]) {
      await expect(page.getByTestId(`seat-${member}`)).toHaveAttribute(
        "data-speaking",
        "false",
      );
    }

    await expect(page.getByTestId("phase")).toContainText(/chairman opening/i);
    // The clock is running, so the Conductor's time budgets are live.
    await expect(page.getByTestId("clock")).not.toContainText("00:00");
  });
});

test.describe("@live the board rotates", () => {
  // A real interview: the candidate speaks (a looped WAV plays into the fake
  // microphone), the board transcribes it, and the mic must move on.
  test.setTimeout(600_000);

  test("hands the mic from the Chairman to a second member", async ({ page }) => {
    await signIn(page);
    await page.getByTestId("daf-specimen").click();
    await page.getByTestId("daf-submit").click();
    await expect(page).toHaveURL(/\/daf\/review$/);
    await page.getByTestId("confirm-read").check();

    await page.getByTestId("convene").click();
    await expect(page).toHaveURL(/\/interview$/, { timeout: 180_000 });
    await page.getByTestId("join").click();

    // The Chairman opens.
    await expect(page.getByTestId("seat-M0")).toHaveAttribute("data-speaking", "true", {
      timeout: 90_000,
    });

    // The candidate is speaking into the mic on a loop. Within the Chairman's
    // block budget the mic must reach somebody else — that is the whole test.
    const others = ["M1", "M2", "M3", "M4"];
    await expect
      .poll(
        async () => {
          for (const id of others) {
            const speaking = await page
              .getByTestId(`seat-${id}`)
              .getAttribute("data-speaking");
            if (speaking === "true") return id;
          }
          return null;
        },
        { timeout: 420_000, intervals: [3_000] },
      )
      .not.toBeNull();

    // And the transcript records the candidate actually being heard.
    await expect(page.getByTestId("transcript")).toContainText(/rural|water|district/i);
  });
});
