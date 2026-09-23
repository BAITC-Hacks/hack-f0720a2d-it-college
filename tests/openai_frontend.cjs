// Optional Playwright check: local static server, mocked API, no paid OpenAI calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = (process.env.UI_TEST_URL || 'http://127.0.0.1:8765').replace(/\/$/, '') + '/';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const output = path.resolve('.test-tmp/screenshots');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1365, height: 960 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://fonts.googleapis.com/**', route => route.abort());
    await page.route('https://fonts.gstatic.com/**', route => route.abort());
    let task = { id: 55, owner_id: 1, title: 'Тест AI', industry: 'Образование', raw_text: 'Исходное описание задачи для проверки сохранности формы.', status: 'draft', score: 0, level: 'draft', level_label: 'Черновик', breakdown: {}, missing: [], created_at: '2026-09-23T10:00:00', updated_at: '2026-09-23T10:00:00' };
    const user = { id: 1, name: 'Тестовый бизнес', role: 'business', team_id: null };
    let aiMode = { provider: 'openai', configured: true, model: 'test-model' };
    let questionCalls = 0, lateRoute = null, deferQuestions = false, manualPayload = null;
    let settings = { provider: 'auto', effective_provider: 'openai', base_url: 'https://api.openai.com/v1', model: 'test-model', has_api_key: true, response_format: 'json_schema' };
    let settingsPayload = null, pendingSettingsRoute = null;
    const analysis = { provider: 'openai', detected_fields: { users: 'Студенты и сотрудники учебного отдела.' }, missing_fields: ['need', 'data', 'expected_result'], questions: [{ field: 'need', text: 'Какую потребность решаем?' }, { field: 'data', text: 'Какие данные доступны?' }, { field: 'expected_result', text: 'Что нужно получить?' }] };
    const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    await page.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url()).pathname;
      if (url === '/api/users') return json(route, [user]);
      if (url === '/api/users/login') return json(route, user);
      if (url === '/api/teams' || url === '/api/catalog' || url === '/api/proposals') return json(route, []);
      if (url === '/api/ai/status') return json(route, aiMode);
      if (url === '/api/ai/settings') {
        if (req.method() === 'PUT') { settingsPayload = req.postDataJSON(); pendingSettingsRoute = route; return; }
        return json(route, settings);
      }
      if (url === '/api/ai/models') return json(route, { models: [{ id: 'test-model', chat_candidate: true }, { id: 'local-model', chat_candidate: true }], selected_model: 'test-model' });
      if (url === '/api/tasks') return json(route, [task]);
      if (url === '/api/tasks/draft') { task = { ...task, ...req.postDataJSON() }; return json(route, task, 201); }
      if (url === '/api/tasks/55/questions') {
        questionCalls++;
        if (deferQuestions) { lateRoute = route; return; }
        return questionCalls === 1 ? json(route, { detail: 'OpenAI временно недоступен' }, 503) : json(route, analysis);
      }
      if (url === '/api/tasks/55/card') return json(route, { detail: 'OpenAI: исчерпана квота' }, 429);
      if (url === '/api/tasks/55') {
        if (req.method() === 'PATCH') { manualPayload = req.postDataJSON(); task = { ...task, ...manualPayload }; }
        return json(route, task);
      }
      return json(route, { detail: 'Unmocked ' + url }, 404);
    });
    const screenshot = name => page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
    await page.goto(base + '#new');
    await page.locator('[data-ai-provider="openai"]').waitFor();
    assert.match(await page.locator('[data-ai-provider]').innerText(), /описание задачи передаётся OpenAI/);
    await screenshot('openai-new-desktop');
    await page.locator('[name="raw_text"]').fill(task.raw_text);
    await page.locator('[name="title"]').fill(task.title);
    await page.locator('[name="industry"]').fill(task.industry);
    await page.locator('#create-draft').click();
    await page.locator('#retry-analysis').waitFor();
    assert.match(await page.locator('#wizard-content').innerText(), /OpenAI временно недоступен/);
    assert.match(await page.locator('#wizard-content').innerText(), /Исходное описание задачи/);
    await screenshot('openai-error-desktop');
    await page.locator('#retry-analysis').click();
    await page.locator('#answers-form').waitFor();
    assert.equal(await page.locator('#answers-form .question').count(), 3);
    const values = { need: 'Сократить очереди на обслуживание студентов.', data: 'Есть таблица обращений за последние четыре недели.', expected_result: 'Рабочая форма подачи обращения и список для оператора.' };
    for (const [name, value] of Object.entries(values)) await page.locator('#answers-form [name="' + name + '"]').fill(value);
    await page.locator('#build-card').click();
    await page.getByText('OpenAI: исчерпана квота', { exact: true }).waitFor();
    assert.equal(await page.locator('[name="need"]').inputValue(), values.need);
    assert.equal(await page.locator('#build-card').isEnabled(), true);
    await page.locator('#manual-card').click();
    await page.locator('#card-form').waitFor();
    assert.equal(manualPayload.need, values.need);
    assert.equal(manualPayload.title, 'Тест AI');
    assert.equal(manualPayload.context, task.raw_text);
    assert.equal(manualPayload.users, analysis.detected_fields.users);
    assert.equal(await page.locator('[name="need"]').inputValue(), values.need);
    assert.equal(await page.evaluate(() => localStorage.getItem('ai-sana:answers:1:55')), null);
    await screenshot('openai-manual-desktop');
    deferQuestions = true;
    await page.goto(base + '#questions/55');
    await page.locator('[data-analysis-loading]').waitFor();
    for (let attempt = 0; !lateRoute && attempt < 100; attempt++) await page.waitForTimeout(20);
    assert.ok(lateRoute, 'Analysis request should start');
    await page.goto(base + '#business');
    await page.getByRole('heading', { name: 'Мои задачи', exact: true, level: 1 }).waitFor();
    await json(lateRoute, analysis);
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#answers-form').count(), 0);
    aiMode = { provider: 'openai', configured: false, model: 'test-model' };
    await page.goto(base + '#new');
    await page.locator('#create-manual').waitFor();
    assert.equal(await page.locator('#create-draft').isDisabled(), true);
    assert.equal(await page.locator('#create-manual').isEnabled(), true);
    aiMode = { provider: 'stub', configured: false, model: null };
    await page.goto(base + '#business');
    await page.goto(base + '#new');
    await page.locator('[data-ai-provider="stub"]').waitFor();
    assert.equal(await page.locator('#create-draft').isEnabled(), true);
    aiMode = { provider: 'compatible', configured: true, model: 'local<model>', base_url: 'http://127.0.0.1:1234/v1' };
    await page.goto(base + '#business');
    await page.goto(base + '#new');
    await page.locator('[data-ai-provider="compatible"]').waitFor();
    assert.match(await page.locator('[data-ai-provider]').innerText(), /127\.0\.0\.1:1234/);
    assert.match(await page.locator('[data-ai-provider]').innerText(), /local<model>/);
    assert.equal(await page.locator('[data-ai-provider] model').count(), 0);
    assert.equal(await page.locator('#create-draft').isEnabled(), true);
    deferQuestions = false;
    analysis.provider = 'compatible';
    await page.goto(base + '#questions/55');
    await page.locator('#answers-form [data-ai-provider="compatible"]').waitFor();
    assert.equal(await page.locator('#answers-form .question').count(), 3);
    await page.goto(base + '#ai');
    await page.locator('#ai-model option[value="local-model"]').waitFor({ state: 'attached' });
    await page.selectOption('#ai-provider', 'compatible');
    await page.locator('[name="api_key"]').fill('test-key-not-a-secret');
    await page.locator('[name="base_url"]').fill('http://127.0.0.1:4321/v1');
    assert.equal(await page.locator('[name="api_key"]').inputValue(), '');
    await page.locator('#refresh-models').click();
    await page.selectOption('#ai-model', 'local-model');
    await page.locator('#save-ai-settings').click();
    await page.waitForFunction(() => document.querySelector('#ai-provider')?.disabled);
    assert.equal(await page.locator('[name="base_url"]').isDisabled(), true);
    for (let attempt = 0; !pendingSettingsRoute && attempt < 100; attempt++) await page.waitForTimeout(20);
    assert.equal(settingsPayload.provider, 'compatible');
    assert.equal(settingsPayload.model, 'local-model');
    assert.equal(settingsPayload.api_key, '');
    settings = { ...settings, ...settingsPayload, effective_provider: 'compatible', has_api_key: false };
    delete settings.api_key;
    await json(pendingSettingsRoute, settings);
    await page.getByText('Настройки AI сохранены', { exact: true }).waitFor();
    assert.equal(await page.locator('#ai-provider').isEnabled(), true);
    assert.equal(await page.evaluate(() => Object.values(localStorage).some(value => value.includes('test-key-not-a-secret'))), false);
    await page.setViewportSize({ width: 390, height: 844 });
    await screenshot('ai-settings-mobile');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    aiMode = { provider: 'openai', configured: true, model: 'test-model' };
    analysis.provider = 'openai';
    await page.goto(base + '#business');
    await page.goto(base + '#new');
    await page.locator('[data-ai-provider="openai"]').waitFor();
    await screenshot('openai-new-mobile');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    deferQuestions = false; questionCalls = 0;
    await page.goto(base + '#questions/55');
    await page.locator('#retry-analysis').waitFor();
    await screenshot('openai-error-mobile');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#wizard-content').getByRole('link', { name: 'Заполнить вручную', exact: true }).click();
    await page.locator('#card-form').waitFor();
    await screenshot('openai-manual-mobile');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    console.log('PASS: OpenAI disclosure, retry, dynamic questions, build failure preservation, manual save, stale response protection, unavailable provider, stub, compatible disclosure, safe settings, desktop/mobile layouts; no page errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
