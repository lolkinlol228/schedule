import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("administrator can set up, generate, edit and export; responsive and accessible", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Данные хранятся на вашем сервере")).toHaveCount(
    0,
  );
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Initial-school-password42");
  await page.getByLabel("Повторите пароль").fill("Initial-school-password42");
  await page.getByRole("button", { name: "Создать администратора" }).click();
  await page.getByLabel("Текущий пароль").fill("Initial-school-password42");
  await page.getByLabel("Новый пароль").fill("Permanent-school-password43");
  await page.getByLabel("Повторите пароль").fill("Permanent-school-password43");
  await page
    .getByRole("button", { name: "Сохранить пароль", exact: true })
    .click();
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Permanent-school-password43");
  await page.getByRole("button", { name: "Войти в систему" }).click();
  await expect(
    page.getByRole("heading", { name: "Обзор расписания" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Выбрать демонстрацию" }).click();
  await page
    .getByLabel("Перейти в демонстрационный режим.", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Открыть сценарий", exact: true })
    .click();
  await expect(
    page.getByText("Исходные данные прошли предварительную проверку."),
  ).toBeVisible();
  for (const [width, height] of [
    [1440, 1000],
    [768, 1024],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    const a11y = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      a11y.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    ).toEqual([]);
    await page.screenshot({
      path: `test-results/overview-${width}.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Открыть меню" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Учителя", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Учителя", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Добавить запись", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByLabel("Название", { exact: true })
    .fill("Новый преподаватель");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Новый преподаватель", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Расписание", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Составить расписание", exact: true })
    .click();
  await page.getByRole("button", { name: "Начать расчёт" }).click();
  await expect(
    page.getByText("Полное расписание", { exact: true }),
  ).toBeVisible({ timeout: 25000 });
  await page.getByRole("button", { name: "Принять результат" }).click();
  await expect(page.getByLabel("Все классы")).toBeVisible();
  await page.getByLabel("Все классы").selectOption("c0");
  await page.screenshot({
    path: "test-results/schedule-1440.png",
    fullPage: true,
  });
  const a11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    a11y.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page.locator("button.lesson").first().click();
  await page.getByLabel("Фиксация", { exact: true }).selectOption("locked");
  await page.getByRole("button", { name: "Проверить и применить" }).click();
  await expect(page.getByText("Не сохранено", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.getByText("Сохранено", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/);
  for (const name of ["На проверке", "Утверждено", "Опубликовано"])
    await page.getByRole("button", { name, exact: true }).click();
  for (const [width, height] of [
    [768, 1024],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `test-results/schedule-${width}.png`,
      fullPage: true,
    });
  }
  expect(errors).toEqual([]);
  await page.getByRole("button", { name: "Вернуться к данным школы" }).click();
  await expect(
    page.getByText("Демонстрационный режим", { exact: true }),
  ).toHaveCount(0);
});

test("two shifts save; feedback stays beside save; scenarios restore school data", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // This case can also run alone against a fresh test database.
  const status = await (await page.request.get("/api/auth/status")).json();
  if (status.setup_required) {
    await page.request.post("/api/auth/setup", {
      data: { password: "Initial-school-password42" },
    });
    const login = await (
      await page.request.post("/api/auth/login", {
        data: { password: "Initial-school-password42" },
      })
    ).json();
    await page.request.post("/api/auth/password", {
      headers: { "X-CSRF-Token": login.csrf },
      data: {
        current: "Initial-school-password42",
        password: "Permanent-school-password43",
      },
    });
  }
  await page.goto("/");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Permanent-school-password43");
  await page.getByRole("button", { name: "Войти в систему" }).click();
  await expect(
    page.getByRole("heading", { name: "Обзор расписания" }),
  ).toBeVisible();
  const original = await (await page.request.get("/api/data")).json();
  await page.getByRole("link", { name: "Демонстрации", exact: true }).click();
  await page.getByLabel("Ситуация").selectOption("two_shifts");
  await expect(page.getByLabel("Ситуация").locator("option")).toHaveCount(11);
  await page
    .getByLabel("Перейти в демонстрационный режим.", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Открыть сценарий", exact: true })
    .click();
  await expect(
    page.getByText("Демонстрационный режим", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Учебный год и звонки", exact: true })
    .click();
  await expect(page.locator(".bell-row")).toHaveCount(10);
  await page
    .getByRole("button", { name: "Сохранить настройки", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Настройки сохранены" }).first(),
  ).toBeVisible();
  await page.locator("#bell-end-9").fill("12:00");
  const save = page.getByRole("button", {
    name: "Сохранить настройки",
    exact: true,
  });
  await save.click();
  const feedback = page
    .getByRole("alert")
    .filter({ hasText: "Настройки не сохранены" });
  await expect(feedback).toBeFocused();
  await expect(feedback).toContainText(
    "Продолжительность урока нарушает норматив",
  );
  const rect = await feedback.boundingBox();
  const button = await save.boundingBox();
  expect(button!.y - (rect!.y + rect!.height)).toBeLessThan(30);
  await page.locator("#bell-end-9").fill("17:55");
  await save.click();
  await expect(feedback).toHaveCount(0);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({
      path: `test-results/bells-${width}.png`,
      fullPage: true,
    });
    const overflow = await page.evaluate(() =>
      [...document.querySelectorAll("main *")]
        .filter((el) => el.getBoundingClientRect().right > innerWidth + 1)
        .map((el) => ({
          tag: el.tagName,
          class: el.className,
          right: el.getBoundingClientRect().right,
        }))
        .slice(0, 8),
    );
    expect(overflow).toEqual([]);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      result.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    ).toEqual([]);
    await page.screenshot({
      path: `test-results/bells-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("link", { name: "Расписание", exact: true }).click();
  await page
    .getByRole("button", { name: "Составить расписание", exact: true })
    .click();
  await page.getByRole("button", { name: "Начать расчёт" }).click();
  await expect(
    page.getByText("Полное расписание", { exact: true }),
  ).toBeVisible({ timeout: 25000 });
  await page.getByRole("button", { name: "Принять результат" }).click();
  await expect(
    page.getByRole("rowheader", { name: "2 смена · 5 урок", exact: true }),
  ).toHaveCount(1);
  await expect(
    page
      .getByText("Смена 2", { exact: false })
      .filter({ has: page.locator("span") }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Сменить сценарий" }).click();
  await page.getByLabel("Ситуация").selectOption("few_rooms");
  await page.getByLabel("Начать новый сценарий.", { exact: false }).check();
  await page
    .getByRole("button", { name: "Открыть сценарий", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Обзор расписания" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Вернуться к данным школы" }).click();
  await expect(
    page.getByText("Демонстрационный режим", { exact: true }),
  ).toHaveCount(0);
  const restored = await (await page.request.get("/api/data")).json();
  expect(restored.data).toEqual(original.data);
  expect(errors).toEqual([]);
});

test("rule form hides the inert value of a soft wish", async ({ page }) => {
  // A soft rule is weighted by its priority; a numeric value there changes
  // nothing, so the form must not offer it. Hard limits keep the field.
  const status = await (await page.request.get("/api/auth/status")).json();
  if (status.setup_required) {
    await page.request.post("/api/auth/setup", {
      data: { password: "Initial-school-password42" },
    });
    const login = await (
      await page.request.post("/api/auth/login", {
        data: { password: "Initial-school-password42" },
      })
    ).json();
    await page.request.post("/api/auth/password", {
      headers: { "X-CSRF-Token": login.csrf },
      data: {
        current: "Initial-school-password42",
        password: "Permanent-school-password43",
      },
    });
  }
  await page.goto("/");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Permanent-school-password43");
  await page.getByRole("button", { name: "Войти в систему" }).click();
  await expect(
    page.getByRole("heading", { name: "Обзор расписания" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Правила решателя", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Правила решателя", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Редактировать Равномерность предметов", { exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Тип", { exact: true })).toHaveValue("soft");
  await expect(dialog.getByLabel("Значение", { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel("Приоритет", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Редактировать Дневной максимум", { exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByLabel("Значение", { exact: true }),
  ).toBeVisible();
});
