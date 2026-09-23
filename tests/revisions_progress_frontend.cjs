// Run against an isolated seeded database, never against the user's working database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.UI_TEST_URL || 'http://127.0.0.1:8765';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const output = path.resolve('.test-tmp/screenshots');
fs.mkdirSync(output, { recursive: true });
async function api(method, url, user = 1, data, expected = 200) {
  const response = await fetch(base + '/api' + url, {
    method, headers: { ...(user ? { 'X-User-Id': String(user) } : {}), 'Content-Type': 'application/json' },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  assert.equal(response.status, expected, `${method} ${url}: ${await response.clone().text()}`);
  return response.status === 204 ? null : response.json();
}
async function create(title, publish = true) {
  const task = await api('POST', '/tasks/draft', 1, { title, industry: 'Образование', raw_text: 'Нужна система заявок в мастерской.' }, 201);
  if (publish) {
    await api('POST', `/tasks/${task.id}/confirm`);
    await api('POST', `/tasks/${task.id}/publish`);
  }
  return task;
}
(async () => {
  const task = await create('Проверка подтверждений ' + Date.now());
  const draft = await create('Приватный черновик ' + Date.now(), false);
  const proposal = await api('POST', '/proposals', 3, { task_id: task.id, idea: 'Соберём журнал заявок для мастерской.', plan: 'Проведём исследование, создадим прототип и проверим результат.', deadline: '3 недели' }, 201);
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  await context.route('https://fonts.gstatic.com/**', route => route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const errors = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  const heading = name => page.getByRole('heading', { name, exact: true }).waitFor();
  async function visit(user, route, title) {
    await page.evaluate(id => localStorage.setItem('ai-sana:user-id', JSON.stringify(id)), user);
    await page.goto(base + '/?ui-test-user=' + user + '#' + route);
    await heading(title);
  }
  const stage = name => page.locator(`[data-stage="${name}"]`);
  const stageState = (name, status) => page.locator(`[data-stage="${name}"][data-progress-status="${status}"]`).waitFor();
  async function submitStage(name, description) {
    const form = stage(name).locator('[data-progress-submit]');
    await form.locator('[name="description"]').fill(description);
    await form.locator('[type="submit"]').click();
    await stageState(name, 'pending');
  }
  async function reviewStage(name, decision, comment) {
    const form = stage(name).locator('[data-progress-review]');
    if (comment) await form.locator('[name="comment"]').fill(comment);
    await form.locator(`[data-review="${decision}"]`).click();
    await stageState(name, decision === 'confirm' ? 'confirmed' : 'rejected');
  }
  try {
    await page.goto(base);
    await visit(1, `edit/${task.id}`, 'Проверьте карточку');
    const updatedTitle = task.title + ' — уточнено';
    const saved = page.waitForResponse(r => r.url().endsWith('/api/tasks/' + task.id) && r.request().method() === 'PATCH');
    await page.locator('[name="title"]').fill(updatedTitle);
    await page.locator('[name="data"]').fill('Доступен журнал реальных ремонтных заявок за три месяца.');
    await saved;
    await page.getByRole('button', { name: 'Проверить изменения', exact: true }).waitFor();
    const liveBefore = await api('GET', `/tasks/${task.id}`, null);
    assert.equal(liveBefore.title, task.title);
    assert.equal(liveBefore.score, 0);
    assert.equal((await api('GET', '/catalog')).find(t => t.id === task.id).score, 0);
    await page.reload();
    await heading('Проверьте карточку');
    assert.equal(await page.locator('[name="title"]').inputValue(), updatedTitle);
    assert.equal((await api('GET', '/tasks')).find(t => t.id === task.id).has_pending_changes, true);
    checks.push('Published edits persist separately; catalog and public score remain unchanged');
    await page.getByRole('button', { name: 'Проверить изменения', exact: true }).click();
    await heading('Подтвердите изменения');
    assert.equal(await page.locator('#confirm-changes').isDisabled(), true);
    await page.screenshot({ path: path.join(output, 'revision-review-desktop.png'), fullPage: true });
    await page.locator('#confirm-updated-facts').check();
    await page.locator('#confirm-changes').click();
    await heading(updatedTitle);
    assert.equal((await api('GET', `/tasks/${task.id}`, 3)).score, 20);
    checks.push('Explicit confirmation publishes the preview and updates its rating');

    await api('PATCH', `/tasks/${task.id}`, 1, { need: 'Первое дополнение, которое сейчас проверяет владелец.' });
    await visit(1, `review-changes/${task.id}`, 'Подтвердите изменения');
    await api('PATCH', `/tasks/${task.id}`, 1, { need: 'Другое дополнение из параллельно открытой вкладки.' });
    await page.locator('#confirm-updated-facts').check();
    const conflict = page.waitForResponse(r => r.url().endsWith('/confirm-changes'));
    await page.locator('#confirm-changes').click();
    assert.equal((await conflict).status(), 409);
    await page.waitForFunction(() => document.querySelector('#confirm-changes')?.disabled && !document.querySelector('#confirm-updated-facts')?.checked);
    assert.equal((await api('GET', `/tasks/${task.id}`, null)).need, null);
    await page.locator('#refresh-revision').click();
    await page.getByText('Другое дополнение из параллельно открытой вкладки.', { exact: true }).waitFor();
    await page.locator('#confirm-updated-facts').check();
    await page.locator('#confirm-changes').click();
    await heading(updatedTitle);
    checks.push('Stale review is rejected; user must review and confirm the current version');

    await api('GET', `/tasks/${draft.id}`, null, undefined, 401);
    await api('GET', `/tasks/${draft.id}`, 3, undefined, 403);
    await visit(3, `task/${draft.id}`, 'Не удалось открыть страницу');
    assert.equal(await page.getByText(draft.raw_text, { exact: true }).count(), 0);
    checks.push('Unpublished task is inaccessible to anonymous users and teams');

    await visit(3, `progress/${proposal.id}`, 'Прогресс по задаче');
    assert.equal(await page.locator('[data-progress-submit]').count(), 0);
    await api('POST', `/proposals/${proposal.id}/accept`);
    await page.locator('[data-refresh-progress]').click();
    await page.locator('[data-progress-submit="research"]').waitFor();
    assert.equal(await stage('prototype').locator('form').count(), 0);
    await submitStage('research', 'Провели интервью с сотрудниками мастерской и описали типовые заявки.');
    assert.equal((await api('GET', `/proposals/${proposal.id}/progress`, 3)).earned_points, 0);
    checks.push('Only accepted team submits the first stage; submission alone gives no points');
    await visit(1, `progress/${proposal.id}`, 'Прогресс по задаче');
    await reviewStage('research', 'reject', 'Добавьте выводы и требования сотрудников.');
    await visit(3, `progress/${proposal.id}`, 'Прогресс по задаче');
    await page.getByText('Добавьте выводы и требования сотрудников.', { exact: true }).waitFor();
    await submitStage('research', 'Добавили выводы интервью, перечень требований и список ограничений.');
    await visit(1, `progress/${proposal.id}`, 'Прогресс по задаче');
    const token = (await api('GET', `/proposals/${proposal.id}/progress`)).stages[0].submission_token;
    await reviewStage('research', 'confirm', 'Исследование принято.');
    await api('POST', `/proposals/${proposal.id}/progress/research/confirm`, 1, { submission_token: token }, 409);
    assert.equal((await api('GET', `/proposals/${proposal.id}/progress`)).earned_points, 20);
    checks.push('Business returns work for revision, confirms resubmission, and awards 20 points once');

    for (const [name, expected] of [['prototype', 50], ['final', 100]]) {
      await visit(3, `progress/${proposal.id}`, 'Прогресс по задаче');
      await submitStage(name, 'Готовый результат этапа проверен на реальных примерах ремонтных заявок.');
      await visit(1, `progress/${proposal.id}`, 'Прогресс по задаче');
      await reviewStage(name, 'confirm', 'Результат проверен и принят.');
      assert.equal((await api('GET', `/proposals/${proposal.id}/progress`)).earned_points, expected);
    }
    await page.reload();
    await heading('Прогресс по задаче');
    await page.getByText('Все этапы подтверждены', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-completion-percent]').textContent(), '100%');
    checks.push('Three stages finish sequentially with 100 points and survive reload');
    await page.screenshot({ path: path.join(output, 'progress-business-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(output, 'progress-mobile.png'), fullPage: true });
    await api('PATCH', `/tasks/${task.id}`, 1, { title: updatedTitle + ' новая версия' });
    await visit(1, `review-changes/${task.id}`, 'Подтвердите изменения');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(output, 'revision-review-mobile.png'), fullPage: true });
    checks.push('Progress and revision confirmation fit mobile');
    await api('POST', `/proposals/${proposal.id}/reopen`);
    await visit(3, `progress/${proposal.id}`, 'Прогресс по задаче');
    assert.equal(await page.locator('[data-progress-submit]').count(), 0);
    assert.equal((await api('GET', `/proposals/${proposal.id}/progress`, 3)).earned_points, 100);
    checks.push('Reopening the proposal preserves earned points and pauses stage actions');
    await api('DELETE', `/tasks/${task.id}`, 1, undefined, 204);
    await api('GET', `/proposals/${proposal.id}/progress`, 3, undefined, 404);
    await visit(3, 'proposals', 'Мои отклики');
    assert.equal(await page.locator(`a[href="#progress/${proposal.id}"]`).count(), 0);
    checks.push('Deletion removes proposal progress and the team history link');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, checks, screenshots: output }, null, 2));
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'revisions-progress-failure.png'), fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
