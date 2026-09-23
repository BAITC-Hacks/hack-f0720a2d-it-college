// Optional browser integration against an isolated seeded DB in explicit stub mode.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const base = process.env.UI_TEST_URL || 'http://127.0.0.1:8765';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
assert.equal(process.env.UI_TEST_ALLOW_WRITE, '1', 'Use only an isolated test database; set UI_TEST_ALLOW_WRITE=1 to run.');
fs.mkdirSync('.test-tmp/screenshots', { recursive: true });

async function api(method, path, user = 1, data) {
  const response = await fetch(base + '/api' + path, {
    method, headers: { 'Content-Type': 'application/json', 'X-User-Id': String(user) },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  assert.ok(response.ok, `${method} ${path}: ${response.status} ${await response.clone().text()}`);
  return response.status === 204 ? null : response.json();
}

(async () => {
  assert.equal((await api('GET', '/ai/status')).provider, 'stub', 'This check must not call an external AI provider.');
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(20000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://fonts.googleapis.com/**', route => route.abort());
  await page.route('https://fonts.gstatic.com/**', route => route.abort());
  const go = async hash => { await page.goto(base + '/#' + hash); };
  try {
    await go('ai');
    await page.selectOption('#ai-provider', 'stub');
    await page.click('#save-ai-settings');
    await page.getByText('Настройки AI сохранены', { exact: true }).waitFor();
    assert.equal((await api('GET', '/ai/settings')).provider, 'stub');
    await page.screenshot({ path: '.test-tmp/screenshots/ai-settings.png', fullPage: true });

    await go('new');
    await page.fill('[name=raw_text]', 'В столовой колледжа очереди по 20 минут. Решением будут пользоваться студенты. Есть обезличенные чеки за три месяца. Нужен веб-прототип прогноза загрузки.');
    await page.fill('[name=title]', 'Проверка интеграции AI Sana');
    await page.fill('[name=industry]', 'Образование');
    const analysisResponse = page.waitForResponse(response => response.url().endsWith('/questions') && response.request().method() === 'POST', { timeout: 240000 });
    await page.click('#create-draft');
    const analysisHTTP = await analysisResponse;
    assert.equal(analysisHTTP.status(), 200, await analysisHTTP.text());
    const analysis = await analysisHTTP.json();
    assert.equal(analysis.provider, 'stub');
    assert.ok(analysis.questions.length >= 3);
    assert.equal(new Set(analysis.questions.map(q => q.field)).size, analysis.questions.length);
    await page.locator('#answers-form').waitFor();
    const taskId = Number(new URL(page.url()).hash.split('/')[1]);
    const texts = {
      title: 'Проверка интеграции AI Sana', industry: 'Образование',
      context: 'В обеденный перерыв студенты колледжа стоят в очереди до двадцати минут.',
      need: 'Нужно сократить время ожидания студентов с помощью прогноза загрузки.',
      users: 'Пользователями будут студенты и сотрудники столовой колледжа.',
      data: 'Есть обезличенные чеки за три месяца и расписание учебных занятий.',
      constraints: 'Четыре недели, браузерный прототип без хранения персональных данных.',
      expected_result: 'Работающий веб-прототип прогноза загрузки столовой по времени.',
      success_criteria: 'Ошибка прогноза не превышает 15 процентов на контрольной выборке.',
      contact: 'Куратор отвечает в рабочем чате и проводит консультации по средам.',
    };
    for (const question of analysis.questions) await page.fill('#answers-form [name=' + question.field + ']', texts[question.field]);
    await page.reload();
    await page.locator('#answers-form').waitFor({ timeout: 240000 });
    assert.equal(await page.inputValue('#answers-form [name=' + analysis.questions[0].field + ']'), texts[analysis.questions[0].field]);
    const buildResponse = page.waitForResponse(response => response.url().endsWith('/card') && response.request().method() === 'POST', { timeout: 240000 });
    await page.click('#build-card');
    const buildHTTP = await buildResponse;
    assert.equal(buildHTTP.status(), 200, await buildHTTP.text());
    await page.locator('#card-form').waitFor();
    const initialScore = (await api('GET', '/tasks/' + taskId)).score;
    assert.equal(initialScore, 0, 'Saving AI output alone must not award points.');
    for (const [name, value] of Object.entries(texts)) await page.fill('#card-form [name=' + name + ']', value);
    await page.click('#confirm-fields');
    await page.getByText('Поля подтверждены. Рейтинг: 100/100', { exact: true }).waitFor();
    const confirmed = await api('GET', '/tasks/' + taskId);
    assert.equal(confirmed.score, 100);
    assert.equal(confirmed.status, 'confirmed');
    await page.click('#next-step');
    await page.locator('#confirm-facts').waitFor();
    await page.check('#confirm-facts');
    await page.check('#confirm-manual');
    await page.click('#publish-task');
    await page.waitForURL('**/#published/' + taskId);
    const published = await api('GET', '/tasks/' + taskId);
    assert.equal(published.score, 100);
    assert.ok(published.score >= initialScore);
    console.log('Stub analysis, cached reload, build, manual field confirmation and publication passed:', taskId);

    async function selectRole(role, user) {
      await page.locator('[data-role=' + role + ']').click();
      await page.waitForFunction(role => document.querySelector('[data-role=' + role + ']')?.getAttribute('aria-pressed') === 'true', role);
      if (await page.locator('#user-select').inputValue() !== String(user)) await page.selectOption('#user-select', String(user));
      await page.waitForFunction(user => localStorage.getItem('ai-sana:user-id') === String(user), user);
    }
    for (const user of [3, 4]) {
      await selectRole('team', user);
      await go('task/' + taskId);
      await page.fill('[name=idea]', 'Создадим простой прогноз загрузки по исходным данным.');
      await page.fill('[name=plan]', 'Проверим данные, соберём прототип и проведём тестирование.');
      await page.fill('[name=deadline]', '4 недели');
      await page.click('#send-proposal');
      await page.getByRole('heading', { name: 'Предложение отправлено' }).waitFor();
    }
    await selectRole('business', 1);
    await go('proposals/' + taskId);
    await page.locator('[data-decision=accept]').first().click();
    await page.locator('[data-decision=accept]').first().click();
    await page.waitForFunction(() => document.querySelectorAll('[data-decision=reopen]').length === 2);
    const proposals = await api('GET', '/tasks/' + taskId + '/proposals');
    assert.ok(proposals.every(p => p.status === 'accepted'));
    await page.screenshot({ path: '.test-tmp/screenshots/ai-comparison.png', fullPage: true });

    await selectRole('team', 3);
    await go('proposals');
    const first = proposals.find(p => p.team_id === 1);
    const form = page.locator('[data-progress-form="' + first.id + '"]');
    await form.locator('textarea').fill('Реализовали прогноз и проверили ошибку на контрольной выборке данных.');
    await form.locator('input[type=url]').fill('https://example.com/result');
    await form.locator('button[type=submit]').click();
    await page.getByText('Результат ожидает проверки · 0 баллов', { exact: true }).waitFor();
    await selectRole('business', 1);
    await go('proposals/' + taskId);
    await page.locator('[data-reject-progress="' + first.id + '"]').click();
    await page.getByText('Результат возвращён на доработку', { exact: true }).waitFor();
    assert.equal((await api('GET', '/proposals', 3)).find(p => p.id === first.id).progress, null);
    await selectRole('team', 3);
    await go('proposals');
    const revised = page.locator('[data-progress-form="' + first.id + '"]');
    await revised.locator('textarea').fill('Уточнили прогноз по замечаниям и повторно проверили ошибку на контрольной выборке.');
    await revised.locator('button[type=submit]').click();
    await page.getByText('Результат ожидает проверки · 0 баллов', { exact: true }).waitFor();
    await selectRole('business', 1);
    await go('proposals/' + taskId);
    await page.locator('[data-confirm-progress="' + first.id + '"]').click();
    await page.getByText('Подтверждено · +10 баллов команде', { exact: true }).waitFor();
    await selectRole('team', 3);
    await go('proposals');
    assert.equal(await page.locator('#team-progress-points').innerText(), '10');
    assert.equal(await page.locator('[data-progress-form="' + first.id + '"]').count(), 0);
    await selectRole('business', 1);

    await go('edit/' + taskId);
    await page.fill('[name=data]', '');
    await page.click('#next-step');
    await page.locator('#confirm-facts').waitFor();
    const publicBefore = (await api('GET', '/catalog')).find(t => t.id === taskId);
    assert.equal(publicBefore.score, 100);
    await page.check('#confirm-facts');
    await page.check('#confirm-manual');
    await page.click('#publish-task');
    await page.waitForURL('**/#published/' + taskId);
    assert.equal((await api('GET', '/catalog')).find(t => t.id === taskId).score, 80);

    await page.setViewportSize({ width: 390, height: 844 });
    await go('catalog');
    await page.locator('.sidebar-toggle').click();
    assert.equal(await page.locator('.sidebar-toggle').getAttribute('aria-expanded'), 'true');
    await go('proposals/' + taskId);
    await page.locator('.compare-scroll').waitFor();
    assert.ok(await page.locator('.compare-scroll').evaluate(el => el.scrollWidth > el.clientWidth));
    await page.screenshot({ path: '.test-tmp/screenshots/ai-mobile-comparison.png', fullPage: true });
    await go('ai');
    await page.locator('#ai-model').waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: '.test-tmp/screenshots/ai-mobile-settings.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('Two teams, manual choice, progress points, confirmed edits, mobile and console: passed');
  } catch (error) {
    console.error('UI failure at', page.url(), 'Page errors:', errors);
    await page.screenshot({ path: '.test-tmp/screenshots/ai-failure.png', fullPage: true });
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
