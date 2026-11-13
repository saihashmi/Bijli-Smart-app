import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const FIX = path.join(__dirname, "fixtures");
const SHOTS = process.env.SCREENSHOT_DIR;

// sales_small.xlsx: Amount by region North 5,710, South 6,780, East 6,770; total 19,260 over 58 values.

async function openAnalyst(page: Page) {
  await page.goto("/upload");
  await page.getByTestId("file-input").setInputFiles(path.join(FIX, "sales_small.xlsx"));
  await expect(page.getByTestId("raw-preview")).toBeVisible();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/s\/[0-9a-f-]{36}\/health$/);
  await page.goto(page.url().replace(/\/health$/, "/analyst"));
  await expect(page.getByTestId("analyst-studio")).toBeVisible();
}

async function ask(page: Page, question: string) {
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

test("typed questions get computed answers with the calculation shown", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await openAnalyst(page);
  await expect(page.getByTestId("analyst-mode")).toContainText("built-in interpreter");
  await expect(page.getByTestId("limitations").getByRole("listitem")).toHaveCount(3);

  await ask(page, "Which region has the highest total amount?");
  const answer = page.getByTestId("answer").last();
  await expect(answer.getByTestId("answer-text")).toHaveText(
    "“South” has the highest total of “Amount” among “Region” groups: 6,780. 3 groups were compared.",
  );
  await expect(answer.getByText("Computed result", { exact: true })).toBeVisible();
  await expect(answer.getByTestId("answer-notes")).toContainText("2 rows have no value in “Amount” and are not counted as zero.");
  await expect(answer.getByTestId("answer-how")).toContainText("Question understood by built-in rules. Calculation used: Rank groups");
  await expect(answer.getByTestId("answer-how")).toContainText("Group by: Region");
  await expect(answer.getByTestId("answer-how")).toContainText("Calculation: total");
  await expect(answer.locator("svg.recharts-surface")).toBeVisible();
  await answer.getByText("Figures (3 rows)").click();
  await expect(answer.getByTestId("answer-table").getByRole("row").nth(1)).toContainText("South");
  await expect(answer.getByTestId("ai-explanation")).toHaveCount(0); // no AI service: nothing is presented as AI

  await ask(page, "What is the total amount?");
  await expect(page.getByTestId("answer").last().getByTestId("answer-text")).toHaveText("The total of “Amount” is 19,260, calculated from 58 values.");
  expect(errors).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/analyst-${info.project.name}.png`, fullPage: true });
});

test("unsupported questions are refused honestly with real alternatives", async ({ page }) => {
  await openAnalyst(page);
  await ask(page, "What will sales be next year?");
  const refusal = page.getByTestId("cannot-answer");
  await expect(refusal).toContainText("I can't answer that with this data or the supported operations.");
  await expect(page.getByTestId("answer")).toHaveCount(0);
  await refusal.getByRole("button", { name: "What is the total of Amount?" }).click();
  await expect(page.getByTestId("answer").last().getByTestId("answer-text")).toContainText("19,260");
});

test("suggested questions and the guided builder work without typing", async ({ page }) => {
  await openAnalyst(page);
  await page.getByTestId("suggestions").getByRole("button", { name: "How many rows are there?" }).click();
  await expect(page.getByTestId("answer").last().getByTestId("answer-text")).toHaveText("There are 60 rows.");

  const builder = page.getByTestId("guided-builder");
  await builder.getByLabel("Calculation", { exact: true }).first().selectOption("compare_groups");
  await expect(builder.getByRole("status")).toHaveText("Tick 2 to 5 values to compare.");
  await expect(builder.getByRole("button", { name: "Run calculation" })).toBeDisabled();
  await builder.getByRole("checkbox", { name: "North" }).click();
  await builder.getByRole("checkbox", { name: "South" }).click();
  await builder.getByLabel("Column (optional)").selectOption("Amount");
  await builder.getByLabel("Calculation", { exact: true }).last().selectOption("sum");
  await builder.getByRole("button", { name: "Run calculation" }).click();
  const answer = page.getByTestId("answer").last();
  await expect(answer.getByTestId("answer-text")).toContainText("“South” is higher than “North” by 1,070.");
  await expect(answer.getByTestId("answer-how")).toContainText("Chosen in the guided builder");

  // earlier questions are kept and can be run again
  await page.reload();
  await expect(page.getByTestId("history").getByRole("button").first()).toContainText("Compare groups");
  await page.getByTestId("history").getByRole("button").first().click();
  await expect(page.getByTestId("answer").last().getByTestId("answer-text")).toContainText("by 1,070");
});
