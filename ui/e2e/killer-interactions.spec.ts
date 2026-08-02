import { expect, test } from "@playwright/test";

/**
 * Targeted by role with an exact name: getByLabel substring-matches, so
 * "inclusion rule 1" would also select the "Remove inclusion rule 1" button and
 * trip strict mode.
 *
 * The three interactions the product is judged on:
 *   1. type a rule and watch attrition move
 *   2. a broken rule marks the readout stale without blanking it
 *   3. a shared link reproduces the exact view
 *
 * Nothing else lives here on purpose.
 */

test("typing a rule moves the attrition figure", async ({ page }) => {
  await page.goto("/?condition=type+2+diabetes&seed=42&n=400&inc=age+%3E%3D+50");

  const count = page.getByTestId("eligible-count");
  await expect(count).not.toBeEmpty();
  const before = Number(await count.textContent());
  expect(before).toBeGreaterThan(0);

  // Tighten the rule. Eligibility must fall live, with no submit.
  await page.getByRole("textbox", { name: "inclusion rule 1", exact: true }).fill("age >= 75");
  await expect.poll(async () => Number(await count.textContent()), { timeout: 10_000 })
    .toBeLessThan(before);

  // And the per-rule attrition table must name the rule doing the damage.
  await expect(page.getByText("age >= 75")).toBeVisible();
});

test("a broken rule marks the readout stale without blanking it", async ({ page }) => {
  await page.goto("/?condition=type+2+diabetes&seed=42&n=400&inc=age+%3E%3D+50");

  const count = page.getByTestId("eligible-count");
  await expect(count).not.toBeEmpty();
  const before = await count.textContent();

  await page.getByRole("textbox", { name: "inclusion rule 1", exact: true }).fill("bmi_at_screening > 30");

  await expect(page.getByTestId("stale-note")).toBeVisible({ timeout: 10_000 });
  // The message appears twice — inline by the rule and in the stale banner.
  await expect(page.getByText(/unknown field/i).first()).toBeVisible();

  // Being mid-keystroke is not an error state: the LAST GOOD number stays.
  // Not the server's score for the surviving rules — breaking your only rule
  // would make eligibility appear to jump to 100%.
  await expect(count).toHaveText(before!);
});

test("the reproducible link round-trips the exact view", async ({ page }) => {
  await page.goto("/?condition=COPD&seed=7&n=250&inc=age+%3E%3D+40");
  await expect(page.getByTestId("eligible-count")).not.toBeEmpty();

  const shared = (await page.getByTestId("share-url").textContent())!;
  expect(shared).toContain("seed=7");
  expect(shared).toContain("n=250");
  const eligible = await page.getByTestId("eligible-count").textContent();

  // Paste it into a design review and see the same simulation, not a screenshot.
  await page.goto(shared);
  await expect(page.getByTestId("eligible-count")).toHaveText(eligible!, { timeout: 10_000 });
});
