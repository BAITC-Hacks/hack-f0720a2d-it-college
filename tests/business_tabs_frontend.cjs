// Optional Playwright check against a separate seeded database on localhost:8765.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.UI_TEST_URL || 'http://127.0.0.1:8765';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const output = path.resolve('.test-tmp/screenshots');
fs.mkdirSync(output, { recursive: true });
async function api(method, url, user = 1, data) {
  const response = await fetch(base + '/api' + url, {
    method, headers: { 'X-User-Id': String(user), 'Content-Type': 'application/json' },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  assert.ok(response.ok, `${method} ${url}: ${response.status}`);
  return response.json();
}
async function create(title, published = true) {
  const task = await api('POST', '/tasks/draft', 1, { title, industry: 'Образование', raw_text: 'Нужен журнал ремонтных заявок для мастерской колледжа.' });
  if (published) {
    await api('POST', `/tasks/${task.id}/confirm`);
    await api('POST', `/tasks/${task.id}/publish`);
  }
  return task;
}
(async () => {
  const task = await create('Проверка разделов ' + Date.now());
  const draft = await create('Черновик разделов ' + Date.now(), false);
  const proposals = [];
  for (const user of [3, 4]) proposals.push(await api('POST', '/proposals', user, {
    task_id: task.id, idea: 'Сделаем журнал ремонтных заявок с поиском.',
    plan: 'Согласуем поля, создадим прототип и проверим поиск.', deadline: 'Две недели',
  }));
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const errors = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  const heading = name => page.getByRole('heading', { name, exact: true, level: 1 }).waitFor();
  const owned = id => page.locator(`[data-owned-task="${id}"]`);
  const active = async route => assert.equal(await page.locator('.nav a[aria-current="page"]').getAttribute('href'), '#' + route);
  try {
    await page.route('**/api/proposals', route => route.abort());
    await page.goto(base + '/#business');
    await heading('Мои задачи');
    await owned(task.id).waitFor();
    await owned(draft.id).waitFor();
    assert.equal(await page.locator('.compare, [data-decision]').count(), 0);
    assert.equal(await owned(task.id).locator('[data-delete-task]').count(), 1);
    await active('business');
    await page.unroute('**/api/proposals');
    checks.push('Task management is independent of proposals and includes drafts');
    await page.screenshot({ path: path.join(output, 'tabs-tasks-desktop.png'), fullPage: true });
    await page.locator('[data-task-status="draft"]').click();
    assert.equal(await owned(task.id).count(), 0);
    await owned(draft.id).waitFor();
    await page.locator('[data-task-status="all"]').click();
    checks.push('Task status filters work');

    await owned(task.id).getByRole('link', { name: 'Предложения', exact: true }).click();
    await page.waitForURL(`**/#proposals/${task.id}`);
    await heading('Предложения');
    await page.getByRole('heading', { name: task.title, level: 2 }).waitFor();
    assert.equal(await page.locator('.compare').count(), 1);
    assert.equal(await page.locator('[data-owned-task], [data-delete-task]').count(), 0);
    await active('proposals');
    checks.push('Proposal view is separate and opens the selected task');
    await page.screenshot({ path: path.join(output, 'tabs-proposals-desktop.png'), fullPage: true });
    for (const [proposal, decision, expected] of [[proposals[0], 'accept', 'accepted'], [proposals[1], 'reject', 'rejected'], [proposals[0], 'reopen', 'pending']]) {
      const response = page.waitForResponse(r => r.url().endsWith(`/api/proposals/${proposal.id}/${decision}`) && r.request().method() === 'POST');
      await page.locator(`[data-decision="${decision}"][data-id="${proposal.id}"]`).click();
      assert.equal((await (await response).json()).status, expected);
      await page.locator(`[data-decision="${expected === 'pending' ? 'accept' : 'reopen'}"][data-id="${proposal.id}"]`).waitFor();
    }
    checks.push('Accept, reject and reopen remain functional');
    await page.reload();
    await heading('Предложения');
    await page.locator(`[data-decision="accept"][data-id="${proposals[0].id}"]`).waitFor();
    await active('proposals');
    await page.locator('.nav a[href="#business"]').click();
    await heading('Мои задачи');
    await page.goBack();
    await heading('Предложения');
    await active('proposals');
    checks.push('Reload and browser back preserve the correct section');

    await page.goto(base + `/#task/${task.id}`);
    await heading(task.title);
    await page.getByRole('link', { name: 'Сравнить предложения' }).click();
    await page.waitForURL(`**/#proposals/${task.id}`);
    await heading('Предложения');
    await page.goto(base + `/#proposals/${draft.id}`);
    await heading('Предложения');
    await page.getByRole('heading', { name: 'Предложений пока нет' }).waitFor();
    assert.equal(await page.locator('.compare').count(), 0);
    await page.getByRole('link', { name: 'К моей задаче' }).click();
    await heading('Мои задачи');
    assert.ok(await owned(draft.id).evaluate(el => el.classList.contains('is-selected')));
    checks.push('Card links and empty proposals lead to the appropriate section');

    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Tasks fit mobile');
    await owned(task.id).screenshot({ path: path.join(output, 'tabs-task-mobile.png') });
    await owned(task.id).getByRole('link', { name: 'Предложения', exact: true }).click();
    await heading('Предложения');
    await page.locator('.compare').waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Proposal comparison scrolls inside the page');
    await page.screenshot({ path: path.join(output, 'tabs-proposals-mobile.png') });
    checks.push('Both sections fit mobile');
    await page.locator('[data-role="team"]').click();
    await page.waitForFunction(() => document.querySelector('[data-role="team"]')?.getAttribute('aria-pressed') === 'true');
    await page.locator('.nav a[href="#proposals"]').click();
    await heading('Мои отклики');
    await page.locator('.proposal-card').filter({ hasText: task.title }).waitFor();
    assert.equal(await page.locator('.compare, [data-delete-task]').count(), 0);
    checks.push('Team history is unchanged');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, checks, screenshots: output }, null, 2));
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'tabs-failure.png') });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
