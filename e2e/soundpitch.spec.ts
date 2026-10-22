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
  const texts = await items.locator(".cue-text").allTextContents();
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
  await expect(page.getByTestId("report-summary")).toHaveText(/^All \d+ descriptions? passed the check as written\.$/);
});

test("the page does not scroll sideways on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await ready(page);
  await playToEnd(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  const text = await page.locator("#transcript .cue-text").first().boundingBox();
  expect(text!.width).toBeGreaterThan(200); // the text keeps most of the line; it is not squeezed beside the time and badges
});

test("a failed reload leaves nothing to play from the old settings", async ({ page }) => {
  await ready(page);
  await page.route("**/api/session?*", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toHaveText("The commentary could not be prepared.");
  await page.getByTestId("play").click();
  await expect(page.getByTestId("status")).toHaveText("The commentary could not be prepared.");
  await expect(page.getByTestId("play")).toHaveText("Play");
});

test("captions follow the voice and can be switched off", async ({ page }) => {
  await ready(page);
  await page.getByTestId("play").click();
  await expect(page.getByTestId("captions")).not.toBeEmpty({ timeout: 10_000 });
  const lastCue = await page.locator('[data-testid^="transcript-cue-"] .cue-text').last().textContent();
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
  const spoken = await page.locator('[data-testid^="transcript-cue-"] .cue-text').allTextContents();
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

test("S23: the commentary is marked with its own language, so a screen reader uses the right voice", async ({ page }) => {
  await ready(page);
  const lang = (testId: string) => page.getByTestId(testId).getAttribute("lang");
  expect(await lang("transcript")).toBe("en");
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toContainText("Ready");
  expect(await lang("transcript")).toBe("it");
  expect(await lang("captions")).toBe("it");
  expect(await lang("live-region")).toBe("it");
  await expect(page.locator("html")).toHaveAttribute("lang", "en"); // the controls stay English
  await expect(page.getByTestId("lang").locator('option[value="it"]')).toHaveAttribute("lang", "it");
  await playToEnd(page);
  await expect(page.getByTestId("transcript-cue-1").locator('span[lang="it"]')).toHaveCount(1); // the cue text
  await expect(page.getByTestId("transcript-cue-1").locator(".badge")).toHaveAttribute("lang", "en"); // interface words stay English
  await expect(page.getByTestId("transcript-cue-1").locator(".time")).toHaveAttribute("lang", "en");
  await page.getByTestId("lang").selectOption("en");
  await expect(page.getByTestId("status")).toContainText("Ready");
  expect(await lang("transcript")).toBe("en");
  expect(await lang("captions")).toBe("en");
});

test("S31: the sentence on what the score now means is shown apart from the description, in both languages", async ({ page }) => {
  await ready(page, "/?speed=40&speech=off&preset=goal_2");
  await playToEnd(page);
  const context = page.locator('[data-testid^="transcript-context-"]');
  await expect(context).toHaveCount(1);
  await expect(context).toHaveText("That makes it level.");
  const item = page.locator('[data-testid^="transcript-cue-"]').filter({ has: context });
  await expect(item.locator(".cue-text")).toHaveText(/ That makes it level\.$/);
  await expect(item.locator(".badge").first()).toHaveText("checked");
  await expect(item.locator(".context-badge")).toHaveText("score context");
  await expect(item.locator(".context-badge")).toHaveAttribute("lang", "en");
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await playToEnd(page);
  await expect(page.locator('[data-testid^="transcript-context-"]')).toHaveText("Il risultato torna in parità.");
  await expect(page.locator('[data-testid^="transcript-cue-"] .cue-text[lang="it"]').filter({ hasText: "parità" })).toHaveCount(1);
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

test("S25: the page works under its content security policy", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (/content security policy|refused to/i.test(message.text())) problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await ready(page);
  const response = await page.request.get("/");
  expect(response.headers()["content-security-policy"]).toContain("default-src 'self'");
  // The policy blocks inline event handlers, so the markup must carry none (a submit would then reload the page).
  const inlineHandlers = await page.evaluate(() =>
    [...document.querySelectorAll("*")].flatMap((e) => [...e.attributes].filter((a) => /^on/i.test(a.name)).map((a) => `${e.tagName}.${a.name}`)),
  );
  expect(inlineHandlers).toEqual([]);
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("output").selectOption("screenreader");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await playToEnd(page);
  expect(problems).toEqual([]);
});

const withClips = (page: Page, stored = { en: 72, it: 68 }, live = false) =>
  page.route("**/api/voice", (route) => route.fulfill({ json: { stored_clips: stored, live } }));

async function watchAudio(page: Page) {
  await page.addInitScript(() => {
    const Real = window.Audio;
    (window as any).__audios = [];
    (window as any).Audio = function (src?: string) {
      const audio = new Real(src);
      (window as any).__audios.push(audio);
      return audio;
    };
  });
}

const playbackRates = (page: Page) => page.evaluate(() => (window as any).__audios.map((a: HTMLAudioElement) => a.playbackRate));

test("S28: a stored clip is played at the chosen speed and the voice is said to be synthetic", async ({ page }) => {
  await watchAudio(page);
  await withClips(page);
  await page.route("**/api/tts", (route) =>
    route.fulfill({ status: 200, headers: { "content-type": "audio/mpeg", "x-audio-rate": "1" }, body: Buffer.from("ID3") }),
  );
  await page.goto("/?speed=40&preset=goal_1");
  await expect(page.getByTestId("status")).toContainText("Ready");
  const note = page.getByTestId("voice-note");
  await expect(note).toBeVisible();
  await expect(note).toContainText("synthetic");
  expect(await page.getByTestId("output").getAttribute("aria-describedby")).toContain("voice-note");
  await page.getByTestId("rate").evaluate((el: HTMLInputElement) => {
    el.value = "1.5";
    el.dispatchEvent(new Event("input"));
    el.dispatchEvent(new Event("change"));
  });
  await page.getByTestId("output").selectOption("azure");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("play").click();
  await expect.poll(async () => (await playbackRates(page)).length).toBeGreaterThan(0);
  expect((await playbackRates(page)).every((r: number) => Math.abs(r - 1.5) < 0.01)).toBe(true);
  expect(await page.evaluate(() => (window as any).__audios.every((a: HTMLAudioElement) => a.preservesPitch !== false))).toBe(true);
});

test("S28: audio that already carries its speed, or says nothing about it, is played as it is", async ({ page }) => {
  await watchAudio(page);
  await withClips(page);
  await page.route("**/api/tts", (route) =>
    route.fulfill({ status: 200, headers: { "content-type": "audio/mpeg", "x-audio-rate": "1.5" }, body: Buffer.from("ID3") }),
  );
  await page.goto("/?speed=40&preset=goal_1");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("rate").evaluate((el: HTMLInputElement) => {
    el.value = "1.5";
    el.dispatchEvent(new Event("input"));
    el.dispatchEvent(new Event("change"));
  });
  await page.getByTestId("output").selectOption("azure");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("play").click();
  await expect.poll(async () => (await playbackRates(page)).length).toBeGreaterThan(0);
  expect((await playbackRates(page)).every((r: number) => Math.abs(r - 1) < 0.01)).toBe(true); // 1.5 asked, 1.5 in the audio
});

test("S29: without stored clips or a key the Azure voice is not offered and the browser voice is the default", async ({ page }) => {
  await ready(page);
  const option = page.getByTestId("output").locator('option[value="azure"]');
  await expect(option).toBeDisabled();
  await expect(page.getByTestId("output")).toHaveValue("browser");
  await expect(page.getByTestId("voice-note")).toContainText("not available");
  await expect(page.getByTestId("voice-note")).not.toContainText("is synthetic");
});

test("S29: the Azure voice is offered where clips exist and withdrawn for a language that has none", async ({ page }) => {
  await withClips(page, { en: 72, it: 0 });
  await ready(page);
  await expect(page.getByTestId("output").locator('option[value="azure"]')).toBeEnabled();
  await expect(page.getByTestId("voice-note")).toContainText("synthetic");
  await page.getByTestId("output").selectOption("azure");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("lang").selectOption("it");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await expect(page.getByTestId("output")).toHaveValue("browser"); // the choice cannot stay on a voice that is not there
  await expect(page.getByTestId("status")).toContainText("Azure");
  await expect(page.getByTestId("output").locator('option[value="azure"]')).toBeDisabled();
  await page.getByTestId("lang").selectOption("en");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await expect(page.getByTestId("output").locator('option[value="azure"]')).toBeEnabled();
});

test("S29: a live voice alone is enough to offer the Azure option", async ({ page }) => {
  await withClips(page, { en: 0, it: 0 }, true);
  await ready(page);
  await expect(page.getByTestId("output").locator('option[value="azure"]')).toBeEnabled();
});

async function fakeSpeech(page: Page, voices: string[]) {
  await page.addInitScript((langs: string[]) => {
    const spoken: string[] = [];
    (window as any).__spoken = spoken;
    const fake = {
      getVoices: () => langs.map((lang) => ({ lang, name: lang })),
      speak: (u: SpeechSynthesisUtterance) => spoken.push(u.text),
      cancel() {}, pause() {}, resume() {}, addEventListener() {},
    };
    Object.defineProperty(window, "speechSynthesis", { value: fake, configurable: true });
  }, voices);
}

test("S30: with no browser voice for the language the page says so and the captions keep going", async ({ page }) => {
  await fakeSpeech(page, ["it-IT"]);
  await page.goto("/?speed=1&preset=goal_1");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("play").click();
  await expect(page.getByTestId("status")).toContainText("no English voice");
  await expect(page.getByTestId("status")).toContainText("screen reader");
  await expect(page.getByTestId("captions")).not.toBeEmpty({ timeout: 15_000 });
  await expect(page.getByTestId("play")).toHaveText("Pause"); // it still plays
});

test("S30: with a voice for the language there is no such message and the cues are spoken", async ({ page }) => {
  await fakeSpeech(page, ["en-GB"]);
  await page.goto("/?speed=40&preset=goal_1");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("play").click();
  await expect(page.getByTestId("status")).toHaveText("The clip has finished.", { timeout: 15_000 });
  const spoken = await page.evaluate(() => (window as any).__spoken as string[]);
  expect(spoken.length).toBeGreaterThan(0);
});

test("S30: a browser with no speech synthesis at all gets the same honest message", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "speechSynthesis", { value: undefined, configurable: true });
    delete (window as any).speechSynthesis;
  });
  await page.goto("/?speed=1&preset=goal_1");
  await expect(page.getByTestId("status")).toContainText("Ready");
  await page.getByTestId("play").click();
  await expect(page.getByTestId("status")).toContainText("cannot speak aloud");
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
    await expect(page.getByTestId("report-summary")).toContainText("replaced by a template that always passes");
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
