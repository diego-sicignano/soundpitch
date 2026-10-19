import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const FAST = "/?speed=40&speech=off&preset=goal_1";

async function ready(page: Page, path = FAST) {
  await page.goto(path);
  await expect(page.getByTestId("status")).toContainText("Ready");
}

async function playToEnd(page: Page) {
  await page.getByTestId("play").click();
  await expect(page.getByTestId("status")).toHaveText("The clip has finished.", { timeout: 15_000 });
}

test("the page loads the match and its five moments", async ({ page }) => {
  await ready(page);
  await expect(page.getByTestId("preset").locator("option")).toHaveCount(5);
  await expect(page.getByTestId("scoreline")).toHaveText("Northgate 0 – 0 Harbour");
  await expect(page.getByTestId("transcript-cue-1")).toHaveCount(0);
  await expect(page.getByTestId("pitch")).toBeVisible();
  await expect(page.getByTestId("ball")).toBeVisible();
});

test("S8: play fills the transcript in order, draws the timeline and ends on the goal score", async ({ page }) => {
  await ready(page);
  const session = await (await page.request.get("/api/session?preset=goal_1")).json();
  await expect(page.locator('[data-testid^="timeline-cue-"]')).toHaveCount(session.cues.length);

  await playToEnd(page);
  const items = page.locator('[data-testid^="transcript-cue-"]');
  await expect(items).toHaveCount(session.cues.length);
  const texts = await items.locator("span:nth-child(2)").allTextContents();
  expect(texts).toEqual(session.cues.map((c: { text: string }) => c.text));
  await expect(page.getByTestId("transcript")).toContainText(/Goal!|It's in!/);
  await expect(page.getByTestId("scoreline")).toHaveText("Northgate 1 – 0 Harbour");
  await expect(page.getByTestId("play")).toHaveText("Play again");
});

test("the report shows how the commentary was checked", async ({ page }) => {
  await ready(page);
  const report = page.getByTestId("report");
  await expect(report).toContainText("Verified");
  await expect(report).toContainText("Overlaps");
  await expect(report.locator("div", { hasText: "Overlaps" }).locator("dd")).toHaveText("0");
  await expect(report.locator("div", { hasText: "Template fallback" }).locator("dd")).toHaveText("0");
});

test("captions follow the voice and can be switched off", async ({ page }) => {
  await ready(page);
  await page.getByTestId("play").click();
  await expect(page.getByTestId("captions")).not.toBeEmpty({ timeout: 10_000 });
  const lastCue = await page.locator('[data-testid^="transcript-cue-"] span:nth-child(2)').last().textContent();
  expect(lastCue).toContain((await page.getByTestId("captions").textContent())!.slice(0, 10));
  await page.getByTestId("toggle-captions").uncheck();
  await expect(page.getByTestId("captions")).toBeEmpty();
});

test("S8: the screen reader output writes into the aria-live region", async ({ page }) => {
  await ready(page);
  await page.getByTestId("output").selectOption("screenreader");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await expect(page.getByTestId("live-region")).toHaveAttribute("aria-live", "polite");
  await playToEnd(page);
  const spoken = await page.locator('[data-testid^="transcript-cue-"] span:nth-child(2)').allTextContents();
  const live = (await page.getByTestId("live-region").textContent()) ?? "";
  expect(live).not.toBe("");
  expect(spoken).toContain(live);
});

test("S8: the space bar toggles play and pause", async ({ page }) => {
  await ready(page, "/?speed=1&speech=off&preset=goal_1");
  await page.locator("h1").click();
  await page.keyboard.press("Space");
  await expect(page.getByTestId("status")).toHaveText("Playing");
  await page.keyboard.press("Space");
  await expect(page.getByTestId("status")).toHaveText("Paused");
});

test("Italian commentary", async ({ page }) => {
  await ready(page);
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await playToEnd(page);
  await expect(page.getByTestId("transcript")).toContainText(/Gol!|Rete!/);
  await expect(page.getByTestId("transcript")).not.toContainText("Goal!");
});

test("changing the detail level changes how much is described", async ({ page }) => {
  await ready(page);
  const count = async () => page.locator('[data-testid^="timeline-cue-"]').count();
  await page.getByTestId("detail").selectOption("essential");
  await expect(page.getByTestId("status")).toContainText("Ready");
  const essential = await count();
  await page.getByTestId("detail").selectOption("full");
  await expect(page.getByTestId("status")).toContainText("Ready");
  expect(await count()).toBeGreaterThan(essential);
});

test("S9: no accessibility violations before and after playing", async ({ page }) => {
  await ready(page);
  const before = await new AxeBuilder({ page }).analyze();
  expect(before.violations).toEqual([]);
  await playToEnd(page);
  await page.getByText("Pipeline steps").click();
  const after = await new AxeBuilder({ page }).analyze();
  expect(after.violations).toEqual([]);
});

test.describe("when the language model keeps getting it wrong", () => {
  test.use({ baseURL: "http://localhost:8101" });

  test("the commentary still completes with verified templates", async ({ page }) => {
    await ready(page);
    const report = page.getByTestId("report");
    await expect(report.locator("div", { hasText: "Verified" }).first().locator("dd")).toHaveText("0");
    await expect(report.locator("div", { hasText: "Attempts" }).locator("dd")).toHaveText("3");
    await expect(report.locator("div", { hasText: "Template fallback" }).locator("dd")).not.toHaveText("0");
    await page.getByText("Pipeline steps").click();
    await expect(page.locator("#trace li", { hasText: "verifier, attempt 3: failed" })).toHaveCount(1);
    await playToEnd(page);
    await expect(page.locator(".badge.fallback").first()).toHaveText("template");
    await expect(page.getByTestId("transcript")).toContainText(/Goal!|It's in!/);
  });
});

test.describe("when the first attempt is wrong and the retry is right", () => {
  test.use({ baseURL: "http://localhost:8102" });

  test("everything is verified after one retry", async ({ page }) => {
    await ready(page);
    const report = page.getByTestId("report");
    await expect(report.locator("div", { hasText: "Attempts" }).locator("dd")).toHaveText("2");
    await expect(report.locator("div", { hasText: "Template fallback" }).locator("dd")).toHaveText("0");
  });
});
