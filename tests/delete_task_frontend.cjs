// Optional browser regression. Run against a seeded, disposable database on port 8765.
// PowerShell: $env:NODE_PATH = Join-Path (Get-Location) '.test-tmp/ui-qa/node_modules'
//            node tests/delete_task_frontend.cjs
// Playwright is a test-only dependency; the application needs no Node.js packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const base = process.env.UI_TEST_URL || 'http://127.0.0.1:8765';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname), 'Use a local disposable test server');
const screenshots = process.env.UI_SCREENSHOTS_DIR || path.join(__dirname, '..', '.test-tmp', 'screenshots');
fs.mkdirSync(screenshots, { recursive: true });
let checks = 0;
const passed = name => { checks += 1; console.log('PASS ' + name); };

async function api(method, endpoint, user = 1, body, expected = 200) {
  const response = await fetch(base + '/api' + endpoint, {
    method,
    headers: { 'X-User-Id': String(user), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const text = await response.text();
  assert.equal(response.status, expected, method + ' ' + endpoint + ': ' + text);
  return text ? JSON.parse(text) : null;
}

async function task(title, publish = true) {
  const created = await api('POST', '/tasks/draft', 1, {
    title, industry: 'Образование', raw_text: 'Тестовая задача для проверки удаления карточки вместе с откликами команд.',
  }, 201);
  if (publish) {
    await api('POST', '/tasks/' + created.id + '/confirm');
    await api('POST', '/tasks/' + created.id + '/publish');
  }
  return created;
}

async function proposal(taskId, user) {
  return api('POST', '/proposals', user, {
    task_id: taskId, idea: 'Подготовим рабочее решение для этой задачи.',
    plan: 'Соберём требования, создадим и проверим прототип.', deadline: '2 недели',
  }, 201);
}

(async () => {
  const stamp = Date.now();
  const target = await task('Удаление задачи ' + stamp);
  const keep = await task('Сохраняем задачу ' + stamp);
  const draft = await task('Удаление черновика ' + stamp, false);
  const first = await proposal(target.id, 3);
  const second = await proposal(target.id, 4);
  const keptProposal = await proposal(keep.id, 3);
  await api('POST', '/proposals/' + first.id + '/accept');

  const browser = await chromium.launch({ channel: process.env.UI_BROWSER_CHANNEL || 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  // Do not make visual checks depend on access to Google Fonts.
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());

  async function visit(route, heading) {
    await page.goto(base + '/#' + route);
    await page.locator('#main-content h1').filter({ hasText: heading }).waitFor();
    assert.equal(await page.locator('#main-content h1').textContent(), heading);
  }
  async function switchUser(role, user) {
    if (await page.locator('[data-role="' + role + '"]').getAttribute('aria-pressed') !== 'true') {
      await page.locator('[data-role="' + role + '"]').click();
      await page.waitForFunction(role => document.querySelector('[data-role="' + role + '"]')?.getAttribute('aria-pressed') === 'true', role);
    }
    if (await page.locator('#user-select').inputValue() !== String(user)) {
      await page.locator('#user-select').selectOption(String(user));
    }
    await page.waitForFunction(user => Number(localStorage.getItem('ai-sana:user-id')) === user && !document.querySelector('#user-select')?.disabled, user);
    await page.waitForFunction(() => !document.querySelector('#main-content .loading'));
  }
  const dialog = () => page.locator('dialog[data-delete-dialog][open]');
  const taskKey = id => ['ai-sana:card:1:' + id, 'ai-sana:answers:1:' + id, 'ai-sana:proposal:3:' + id, 'ai-sana:proposal:4:' + id];
  try {
    await visit('task/' + target.id, target.title);
    await switchUser('team', 3);
    await visit('task/' + target.id, target.title);
    assert.equal(await page.locator('[data-delete-task]').count(), 0);
    await switchUser('business', 2);
    await visit('task/' + target.id, target.title);
    assert.equal(await page.locator('[data-delete-task]').count(), 0);
    passed('Удаление недоступно команде и чужому бизнесу');

    await switchUser('team', 3);
    const taskReadEndpoint = base + '/api/tasks/' + target.id;
    await page.route(taskReadEndpoint, route => route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Задача не найдена' }) }));
    await visit('proposals', 'Мои отклики');
    assert.equal(await page.locator('.proposal-card').filter({ hasText: target.title }).count(), 0);
    assert.equal(await page.locator('.proposal-card').filter({ hasText: keep.title }).count(), 1);
    await page.unroute(taskReadEndpoint);
    passed('Удаление между загрузкой откликов и карточек не ломает список команды');

    await page.route(taskReadEndpoint, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Проверка ошибки сервера' }) }));
    await page.reload();
    await page.getByRole('heading', { name: 'Не удалось открыть страницу' }).waitFor();
    await page.getByText('Проверка ошибки сервера', { exact: true }).waitFor();
    await page.unroute(taskReadEndpoint);
    passed('Ошибки сервера не маскируются как удаление задачи');

    await switchUser('business', 1);
    await visit('task/' + target.id, target.title);
    assert.equal(await page.locator('[data-delete-task]').count(), 1);
    await page.locator('[data-delete-task]').click();
    await dialog().waitFor();
    assert.ok((await dialog().textContent()).includes(target.title));
    assert.match(await dialog().textContent(), /отклик/i);
    await dialog().locator('[data-cancel-delete]').click();
    await dialog().waitFor({ state: 'hidden' });
    await api('GET', '/tasks/' + target.id);
    assert.equal((await api('GET', '/tasks/' + target.id + '/proposals')).length, 2);
    passed('Подтверждение на карточке показывает задачу; отмена сохраняет задачу и отклики');

    await visit('business/' + target.id, 'Мои задачи');
    await page.evaluate(keys => keys.forEach(key => localStorage.setItem(key, JSON.stringify({ saved: 'Не потерять' }))), [...taskKey(target.id), ...taskKey(keep.id)]);
    await page.locator('[data-owned-task="' + target.id + '"] [data-delete-task]').click();
    await dialog().waitFor();
    await page.screenshot({ path: path.join(screenshots, 'delete-desktop.png') });
    await page.keyboard.press('Escape');
    await dialog().waitFor({ state: 'hidden' });
    await api('GET', '/tasks/' + target.id);
    passed('Удаление доступно в кабинете; Escape отменяет действие');

    await page.locator('[data-owned-task="' + target.id + '"] [data-delete-task]').click();
    const targetEndpoint = base + '/api/tasks/' + target.id;
    await page.route(targetEndpoint, route => route.request().method() === 'DELETE' ? route.abort('failed') : route.continue());
    await dialog().locator('[data-confirm-delete]').click();
    await dialog().getByText(/Нет связи с сервером/).waitFor();
    await page.waitForFunction(() => !document.querySelector('[data-confirm-delete]')?.disabled);
    assert.equal(await dialog().isVisible(), true);
    assert.doesNotMatch(await page.locator('#toast-region').textContent(), /Задача.*удален/i);
    await api('GET', '/tasks/' + target.id);
    assert.equal((await api('GET', '/tasks/' + target.id + '/proposals')).length, 2);
    assert.ok((await page.evaluate(key => localStorage.getItem(key), taskKey(target.id)[0])));
    await page.unroute(targetEndpoint);
    passed('Ошибка сети сохраняет данные и позволяет повторить удаление');

    const deleteResponse = page.waitForResponse(response => response.url() === targetEndpoint && response.request().method() === 'DELETE');
    await dialog().locator('[data-confirm-delete]').click();
    assert.equal((await deleteResponse).status(), 204);
    await page.waitForURL('**/#business');
    await page.waitForFunction(() => !document.querySelector('#main-content .loading'));
    assert.equal(await dialog().count(), 0);
    assert.equal(await page.locator('a[href="#business/' + target.id + '"]').count(), 0);
    await api('GET', '/tasks/' + target.id, 1, undefined, 404);
    assert.ok(!(await api('GET', '/catalog')).some(t => t.id === target.id));
    for (const user of [1, 3, 4]) {
      assert.ok(!(await api('GET', '/proposals', user)).some(p => [first.id, second.id].includes(p.id)));
    }
    passed('Подтверждение удаляет задачу и принятые/ожидающие отклики, обновляет кабинет и каталог');

    const stored = await page.evaluate(keys => Object.fromEntries(keys.map(key => [key, localStorage.getItem(key)])), [...taskKey(target.id), ...taskKey(keep.id)]);
    for (const key of taskKey(target.id)) assert.equal(stored[key], null, key);
    for (const key of taskKey(keep.id)) assert.ok(stored[key], key);
    await api('GET', '/tasks/' + keep.id);
    assert.ok((await api('GET', '/proposals', 3)).some(p => p.id === keptProposal.id));
    passed('Локальные копии удалённой карточки очищены; другая задача и её отклик сохранены');

    await page.reload();
    await page.locator('#user-select').waitFor();
    await switchUser('team', 3);
    await visit('proposals', 'Мои отклики');
    assert.equal(await page.locator('.proposal-card').filter({ hasText: target.title }).count(), 0);
    assert.equal(await page.locator('.proposal-card').filter({ hasText: keep.title }).count(), 1);
    await page.reload();
    await page.locator('#main-content h1').filter({ hasText: 'Мои отклики' }).waitFor();
    assert.equal(await page.locator('.proposal-card').filter({ hasText: target.title }).count(), 0);
    assert.equal(await page.locator('.proposal-card').filter({ hasText: keep.title }).count(), 1);
    passed('История команды после смены роли и перезагрузки не содержит удалённых откликов');

    await switchUser('business', 1);
    await page.setViewportSize({ width: 390, height: 844 });
    await visit('business/' + draft.id, 'Мои задачи');
    await page.locator('[data-owned-task="' + draft.id + '"] [data-delete-task]').click();
    await dialog().waitFor();
    const geometry = await dialog().evaluate(element => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, innerWidth, innerHeight,
        contentWidth: element.scrollWidth, width: element.clientWidth,
        documentWidth: document.documentElement.scrollWidth };
    });
    assert.ok(geometry.left >= 0 && geometry.right <= geometry.innerWidth + 1, JSON.stringify(geometry));
    assert.ok(geometry.top >= 0 && geometry.bottom <= geometry.innerHeight + 1, JSON.stringify(geometry));
    assert.ok(geometry.contentWidth <= geometry.width + 1, JSON.stringify(geometry));
    assert.ok(geometry.documentWidth <= geometry.innerWidth + 1, JSON.stringify(geometry));
    await page.screenshot({ path: path.join(screenshots, 'delete-mobile.png') });
    passed('Диалог удаления помещается на мобильном экране 390 × 844');

    await dialog().locator('[data-confirm-delete]').click();
    await page.waitForURL('**/#business');
    await page.waitForFunction(() => !document.querySelector('#main-content .loading'));
    await api('GET', '/tasks/' + draft.id, 1, undefined, 404);
    await api('GET', '/tasks/' + keep.id);
    passed('Черновик без откликов также удаляется');

    assert.deepEqual(pageErrors, []);
    passed('В браузере нет необработанных ошибок JavaScript');
    console.log('Browser deletion regression: ' + checks + ' checks passed.');
  } catch (error) {
    await page.screenshot({ path: path.join(screenshots, 'delete-failure.png') }).catch(() => {});
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
