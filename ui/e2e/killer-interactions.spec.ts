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

  // The ledger's one distinguishing claim, checked against the REAL server
  // rather than a stubbed fetch: 18 of 20 shipped assumptions are expert-guess,
  // so the rail must say so. This renders nothing when the reader and the
  // endpoint disagree on the key name, which is exactly what happened across
  // v0.5 — both halves were unit-tested and the seam was not.
  await expect(page.getByTestId("ledger")).toContainText("never quote");
  await expect(page.getByText(/· \d+ never quote/)).toBeVisible();
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

  // The URL is also the only way to reach a condition with no prior pack — the
  // dropdown offers five, all covered. That path used to return a confident
  // number with no flag at all, visible only as a `generic:` substring inside
  // the identity stamp. It must now say so out loud, in amber, not in the
  // ledger's red: a coverage gap is a cost, not an integrity failure.
  await page.goto("/?condition=glaucoma&seed=7&n=100");
  const banner = page.getByTestId("generic-population");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("glaucoma");
  await expect(banner).toHaveCSS("border-left-color", "rgb(138, 90, 0)"); // --lost
});
