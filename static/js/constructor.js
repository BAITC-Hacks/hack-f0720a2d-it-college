// Четыре шага конструктора: описание, вопросы, сохранение карточки и явная публикация.
import { api } from "./api.js";
import { INDICATORS } from "./ui.js";
import { esc, fmt, FIELDS, field, formValues, validate, clearErrors, showError, busy, memory, toast, button, linkButton, icon, ratingPanel, readonlyCard, titleOf, alertBox, INDUSTRIES } from "./helpers.js";

const TITLES = { new: "Опишите задачу", questions: "Ответьте на вопросы", edit: "Проверьте карточку", publish: "Подтвердите и опубликуйте" };
const SUBTITLES = {
  new: "Начните с короткого описания. Карточку, рейтинг и публикацию соберём по шагам.",
  questions: "Уточните детали, чтобы команда понимала результат, данные и условия работы.",
  edit: "Проверьте текст и подтвердите заполненные поля, чтобы получить баллы. Сохранение само по себе баллов не даёт.",
  publish: "Опубликованную задачу увидят все студенческие команды. Решение о выборе команды останется за вами.",
};
const hints = {
  context: "Что происходит сейчас и почему возникла задача?",
  need: "Что именно бизнес хочет изменить?",
  users: "Кто будет пользоваться решением?",
  data: "Какие таблицы, материалы или примеры получит команда?",
  constraints: "Сроки, технологии, доступы и ограничения",
  expected_result: "Что конкретно команда должна сдать?",
  success_criteria: "Как вы измерите, что решение работает?",
  contact: "Контакт, время консультаций и формат обратной связи",
};
const aiPanel = () => '<section class="panel stack tight"><div class="eyebrow">AI-помощник</div><p class="caption">Анализ выполняет выбранная модель. Проверьте извлечённые сведения перед подтверждением.</p>' + linkButton("Настройки AI", "#ai", "secondary") + '</section>';
const stepper = (step) => '<ol class="stepper" aria-label="Шаги создания задачи">' + ["Описание", "Уточнение", "Карточка", "Публикация"].map((label, i) =>
  '<li class="' + (i + 1 < step ? "is-done" : "") + '"' + (i + 1 === step ? ' aria-current="step"' : "") + '><span class="stepper__dot">' + (i + 1 < step ? icon("check") : i + 1) + "</span><span>" + label + "</span></li>").join("") + "</ol>";
function shell(root, mode, task, content, aside) {
  const step = { new: 1, questions: 2, edit: 3, publish: 4 }[mode];
  root.className = "wizard";
  root.innerHTML = '<div class="wizard-heading stack"><div class="between"><nav class="breadcrumbs"><a href="#business">Мои задачи</a><span>/</span><span>' + (task ? esc(titleOf(task)) : "Новая задача") + '</span></nav><span class="caption" id="save-status" role="status">' + (task ? "Изменения сохранены" : "Описание ещё не отправлено") + "</span></div>" + stepper(step) +
    '<div class="stack tight"><h1 class="h1">' + TITLES[mode] + '</h1><p class="lead muted">' + SUBTITLES[mode] + '</p></div></div><div class="page wizard-page"><div class="stack" id="wizard-content">' + content + '</div><aside class="stack sticky-aside" id="wizard-aside">' + aside + "</aside></div>";
}
const weightsPanel = () => '<section class="panel"><div class="eyebrow">Как считается рейтинг</div><p class="muted">Баллы показывают полноту карточки. Перед публикацией вы проверите и подтвердите сведения.</p><div>' +
  INDICATORS.map(([, label, weight]) => '<div class="weight-row"><span>' + label + '</span><span class="mono">' + weight + "</span></div>").join("") +
  '</div><p class="caption">Только подтверждённые поля: пусто, заглушка или повтор — 0; короче 30 символов — половина веса; от 30 — полный вес. Контекст и потребность по 10 баллов.</p></section>';

const answerFields = new Set(["title", "industry", ...FIELDS.map(([name]) => name)]);
const knownAnswers = values => Object.fromEntries(Object.entries(values || {}).filter(([name, value]) => answerFields.has(name) && typeof value === "string"));
const aiAvailable = mode => mode && !mode.error && (mode.provider === "stub" || mode.provider === "openai" && mode.configured);
const aiName = mode => mode?.provider === "openai" ? "OpenAI" : mode?.provider === "stub" ? "Локальные шаблоны" : "Сервис анализа";
const getAiMode = () => api.aiStatus().catch(error => ({ error }));
function aiNotice(mode) {
  let message;
  if (mode?.error) message = alertBox("error", "Не удалось определить режим анализа", mode.error.message + " Можно повторить проверку или заполнить карточку вручную.");
  else if (mode?.provider === "openai") message = alertBox(mode.configured ? "info" : "error", "Анализ: OpenAI" + (mode.model ? " · " + mode.model : ""),
    (mode.configured ? "" : "OpenAI не настроен. Сейчас доступно ручное заполнение. ") + "При проверке полноты описание задачи передаётся OpenAI; при сборке карточки передаются описание и ваши ответы. Проверьте, какие сведения вы отправляете.");
  else if (mode?.provider === "stub") message = alertBox("info", "Анализ: локальные шаблоны", "Вопросы и карточка формируются на этом сервере без обращения к OpenAI. При сборке используются только описание и ваши ответы.");
  else message = alertBox("error", "Не удалось определить режим анализа", "Сервер не сообщил доступный режим. Повторите проверку или заполните карточку вручную.");
  return '<div data-ai-provider="' + esc(mode?.provider || "unknown") + '">' + message + '</div>';
}

export async function renderConstructor(root, ctx, mode, taskId) {
  const [task, aiMode] = await Promise.all([
    mode === "new" ? null : api.task(taskId),
    ["new", "questions"].includes(mode) ? getAiMode() : null,
  ]);
  if (!root.isConnected) return;
  if (task && task.owner_id !== ctx.user.id) throw new Error("Редактирование доступно только владельцу задачи");
  if (mode === "published") return published(root, ctx, task);
  if (mode === "questions" && task.status === "published") { ctx.navigate("edit/" + task.id); return; }
<<<<<<< HEAD
  if (mode === "publish" && task.status === "published") { ctx.navigate("published/" + task.id); return; }
  if (mode === "new") return draft(root, ctx, aiMode);
  if (mode === "questions") return questions(root, ctx, task, aiMode);
=======
  if (mode === "publish" && task.status === "published" && !task.has_pending_changes) { ctx.navigate("published/" + task.id); return; }
  if (mode === "new") return draft(root, ctx);
  if (mode === "questions") return questions(root, ctx, task);
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
  if (mode === "edit") return editor(root, ctx, task);
  return confirm(root, ctx, task);
}

function draft(root, ctx, aiMode) {
  const key = "draft:" + ctx.user.id;
  const values = memory.get(key, {});
  const body = '<form id="draft-form" class="panel panel--roomy" novalidate><div data-errors></div>' + aiNotice(aiMode) +
    field("raw_text", "Опишите задачу своими словами", values.raw_text, { textarea: true, rows: 6, required: true, max: 10000, placeholder: "Что происходит сейчас и что вы хотите изменить?", hint: "Пишите как есть. После уточняющих вопросов проверьте собранную карточку перед публикацией." }) +
    '<div class="caption mono align-right" id="raw-count"></div><div class="form-grid">' +
    field("title", "Рабочее название", values.title, { max: 240, hint: "Можно изменить позже", placeholder: "Например: Прогноз загрузки столовой" }) +
    field("industry", "Отрасль", values.industry, { max: 120, placeholder: "Например: Образование" }) +
    '</div><div class="form-footer"><span class="caption">Шаг 1 из 4</span><div class="actions">' +
<<<<<<< HEAD
    linkButton("Отмена", "#business", "ghost") + button("Заполнить вручную", "create-manual", "secondary") + button("Проверить полноту", "create-draft", "primary", "submit") + '</div></div>' +
    (!aiAvailable(aiMode) ? '<button type="button" class="text-button" id="retry-ai-mode">Повторить проверку режима</button>' : "") + '</form>';
  shell(root, "new", null, body, weightsPanel());
=======
    linkButton("Отмена", "#business", "ghost") + button("Проверить полноту", "create-draft", "primary", "submit") + "</div></div></form>";
  shell(root, "new", null, body, aiPanel() + weightsPanel());
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
  const form = root.querySelector("#draft-form");
  form.querySelector('[data-field="raw_text"]').append(root.querySelector("#raw-count"));
  const industry = form.elements.industry;
  industry.setAttribute("list", "industries");
  form.insertAdjacentHTML("beforeend", '<datalist id="industries">' + INDUSTRIES.map(i => '<option value="' + esc(i) + '"></option>').join("") + "</datalist>");
  const update = () => {
    memory.set(key, formValues(form));
    root.querySelector("#raw-count").textContent = form.elements.raw_text.value.length + " / 10 000";
    root.querySelector("#save-status").textContent = "Описание сохранено в этом браузере";
  };
  form.addEventListener("input", update);
  root.querySelector("#raw-count").textContent = form.elements.raw_text.value.length + " / 10 000";
  form.querySelector("#create-draft").disabled = !aiAvailable(aiMode);
  form.querySelector("#retry-ai-mode")?.addEventListener("click", () => ctx.navigate("new"));
  let saving = false;
  async function create(control, manual) {
    if (saving) return;
    if (!validate(form)) return;
    const payload = formValues(form);
    memory.set(key, payload);
    await busy(control, async () => {
      saving = true;
      const controls = Array.from(form.querySelectorAll("button,input,textarea"));
      controls.forEach(element => { element.disabled = true; });
      try {
        const task = await api.draft(payload);
        if (!root.isConnected) return;
        memory.remove(key);
        ctx.navigate((manual ? "edit/" : "questions/") + task.id);
      } catch (error) { if (root.isConnected) showError(root, error, form); }
      finally {
        saving = false;
        controls.forEach(element => { element.disabled = false; });
        form.querySelector("#create-draft").disabled = !aiAvailable(aiMode);
      }
    });
    form.querySelector("#create-draft").disabled = !aiAvailable(aiMode);
  }
  form.addEventListener("submit", event => { event.preventDefault(); if (aiAvailable(aiMode)) create(form.querySelector("#create-draft"), false); });
  form.querySelector("#create-manual").addEventListener("click", event => create(event.currentTarget, true));
}

<<<<<<< HEAD
function questions(root, ctx, task, initialMode) {
  const key = "answers:" + ctx.user.id + ":" + task.id;
  let aiMode = initialMode, disposed = false, pending = false, analysisVersion = 0;
  const current = () => !disposed && root.isConnected;
  const original = '<section class="panel"><div class="between"><span class="eyebrow">Ваше описание · черновик сохранён</span>' +
    linkButton("Изменить", "#edit/" + task.id, "ghost", "edit") + '</div><blockquote>' + esc(task.raw_text) + '</blockquote></section>';
  function show(content) {
    if (!current()) return;
    shell(root, "questions", task, original + content, weightsPanel() + alertBox("info", "Только ваши сведения", "Проверьте результат анализа перед публикацией. Вопрос можно пропустить и заполнить поле позже."));
=======
async function questions(root, ctx, task) {
  shell(root, "questions", task, '<div class="panel loading" role="status"><span class="spinner"></span>AI анализирует описание и готовит вопросы…</div>', aiPanel());
  let analysis;
  try { analysis = await api.questions(task.id); }
  catch (error) {
    if (!root.isConnected) return;
    shell(root, "questions", task, alertBox("error", "Анализ пока недоступен", error.message) + '<div class="actions">' + button("Повторить анализ", "retry-analysis") + linkButton("Заполнить карточку вручную", "#edit/" + task.id, "secondary") + '</div>', aiPanel());
    root.querySelector("#retry-analysis").addEventListener("click", () => ctx.navigate("questions/" + task.id));
    return;
  }
  if (!root.isConnected) return;
  const key = "answers:" + ctx.user.id + ":" + task.id;
  const values = { ...analysis.detected_fields, ...Object.fromEntries(Object.entries(task).filter(([, value]) => value != null)), ...memory.get(key, {}) };
  const cards = analysis.questions.map((question, i) =>
    '<div class="question"><div class="question-number mono">' + String(i + 1).padStart(2, "0") + '</div><div class="stack tight">' +
    field(question.field, question.text, values[question.field], {
      textarea: !["title", "industry"].includes(question.field), rows: 3,
      max: question.field === "title" ? 240 : question.field === "industry" ? 120 : 10000,
      placeholder: "Ваш ответ", hint: hints[question.field] || "",
    }) + '<button type="button" class="text-button skip-question" data-skip="' + question.field + '">Пропустить вопрос</button></div></div>').join("");
  const content = '<section class="panel"><div class="between"><span class="eyebrow">Ваше описание</span>' +
    linkButton("Изменить", "#edit/" + task.id, "ghost", "edit") + '</div><blockquote>' + esc(task.raw_text) + '</blockquote></section>' +
    '<form id="answers-form" class="panel panel--roomy" novalidate><div data-errors></div><div class="between"><h2 class="h2">' + analysis.questions.length + ' уточняющих вопросов</h2><span class="caption" id="answered-count"></span></div><div>' +
    cards + '</div><div class="form-footer">' + button("Сохранить и выйти", "save-answers", "secondary") + button("Собрать карточку", "build-card", "primary", "submit") + "</div></form>";
  const detected = FIELDS.filter(([name]) => analysis.detected_fields?.[name]).map(([, label]) => label);
  shell(root, "questions", task, content, aiPanel() + (detected.length ? alertBox("info", "В описании уже есть сведения", detected.join(", ") + ". Они будут учтены при сборке карточки.") : "") + weightsPanel());
  const form = root.querySelector("#answers-form");
  const update = () => {
    const data = formValues(form);
    memory.set(key, data);
    root.querySelector("#answered-count").textContent = "Отвечено " + Object.values(data).filter(v => v.trim()).length + " из " + analysis.questions.length;
    root.querySelector("#save-status").textContent = "Ответы сохранены в этом браузере";
  };
  form.addEventListener("input", update);
  form.querySelectorAll("[data-skip]").forEach(btn => btn.addEventListener("click", () => {
    const input = form.elements[btn.dataset.skip];
    input.value = ""; update();
    const inputs = Array.from(form.querySelectorAll("input,textarea"));
    (inputs[inputs.indexOf(input) + 1] || form.querySelector("#build-card")).focus();
  }));
  update();
  async function save(control, exit) {
    if (!validate(form)) return;
    await busy(control, async () => {
      form.querySelectorAll("button").forEach(el => { el.disabled = true; });
      try {
        const answers = formValues(form);
        if (exit) await api.updateTask(task.id, answers);
        else await api.buildCard(task.id, answers);
        memory.remove(key);
        if (root.isConnected) ctx.navigate(exit ? "business/" + task.id : "edit/" + task.id);
      } catch (error) { showError(root, error, form); }
      finally { form.querySelectorAll("button").forEach(el => { el.disabled = false; }); }
    });
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
  }
  async function analyze(refreshMode = false) {
    if (pending || !current()) return;
    pending = true;
    const version = ++analysisVersion;
    show('<section class="panel">' + aiNotice(aiMode) + '<div class="loading" data-analysis-loading role="status"><span class="spinner"></span>Анализируем описание. Это может занять несколько секунд…</div></section>');
    try {
      if (refreshMode) aiMode = await getAiMode();
      if (!current() || version !== analysisVersion) return;
      if (!aiAvailable(aiMode)) throw new Error(aiMode?.error?.message || (aiMode?.provider === "openai" ? "OpenAI не настроен. Можно заполнить карточку вручную." : "Режим анализа недоступен. Можно заполнить карточку вручную."));
      const analysis = await api.questions(task.id);
      if (!current() || version !== analysisVersion) return;
      if (!Array.isArray(analysis?.questions) || analysis.questions.length < 3 || analysis.questions.length > 10 ||
          new Set(analysis.questions.map(item => item?.field)).size !== analysis.questions.length ||
          analysis.questions.some(item => !answerFields.has(item?.field) || typeof item?.text !== "string" || !item.text.trim()) ||
          analysis.provider && !["openai", "stub"].includes(analysis.provider)) {
        throw new Error(aiName(aiMode) + ": получен некорректный список вопросов. Повторите анализ или заполните карточку вручную.");
      }
      aiMode = { ...aiMode, provider: analysis.provider || aiMode.provider };
      renderAnswers(analysis);
    } catch (error) {
      if (!current() || version !== analysisVersion) return;
      show('<section class="panel">' + aiNotice(aiMode) + alertBox("error", aiName(aiMode) + ": анализ не завершён", error.message) +
        '<p class="muted">Исходное описание сохранено в черновике. Повторите анализ или продолжите заполнение вручную.</p><div class="actions">' +
        button("Повторить анализ", "retry-analysis") + linkButton("Заполнить вручную", "#edit/" + task.id, "secondary") + '</div></section>');
      root.querySelector("#retry-analysis").addEventListener("click", () => analyze(true));
    } finally { pending = false; }
  }
  function renderAnswers(analysis) {
    const baseAnswers = { ...knownAnswers(task), ...knownAnswers(memory.get(key, {})) };
    const cards = analysis.questions.map((question, i) =>
      '<div class="question"><div class="question-number mono">' + String(i + 1).padStart(2, "0") + '</div><div class="stack tight">' +
      field(question.field, question.text, baseAnswers[question.field], {
        textarea: !["title", "industry"].includes(question.field), rows: 3,
        max: question.field === "title" ? 240 : question.field === "industry" ? 120 : "",
        placeholder: "Ваш ответ", hint: hints[question.field] || "",
      }) + '<button type="button" class="text-button skip-question" data-skip="' + esc(question.field) + '">Пропустить вопрос</button></div></div>').join("");
    show('<form id="answers-form" class="panel panel--roomy" novalidate>' + aiNotice(aiMode) + '<div data-errors></div><div class="between"><h2 class="h2">Уточняющие вопросы · ' + analysis.questions.length + '</h2><span class="caption" id="answered-count"></span></div><div>' +
      cards + '</div><p class="caption" id="build-status" role="status"></p><div class="form-footer">' + button("Сохранить и выйти", "save-answers", "secondary") +
      '<div class="actions">' + button("Заполнить без ИИ", "manual-card", "secondary") + button("Собрать карточку", "build-card", "primary", "submit") + '</div></div></form>');
    const form = root.querySelector("#answers-form");
    const allAnswers = () => ({ ...baseAnswers, ...formValues(form) });
    const update = () => {
      memory.set(key, allAnswers());
      root.querySelector("#answered-count").textContent = "Отвечено " + Object.values(formValues(form)).filter(value => value.trim()).length + " из " + analysis.questions.length;
      root.querySelector("#save-status").textContent = "Ответы сохранены в этом браузере";
    };
    form.addEventListener("input", update);
    form.querySelectorAll("[data-skip]").forEach(control => control.addEventListener("click", () => {
      const input = form.elements[control.dataset.skip];
      input.value = ""; update();
      const inputs = Array.from(form.querySelectorAll("input,textarea"));
      (inputs[inputs.indexOf(input) + 1] || form.querySelector("#build-card")).focus();
    }));
    update();
    async function save(control, action) {
      if (pending || !current() || !validate(form)) return;
      const answers = allAnswers();
      memory.set(key, answers);
      const label = control.textContent;
      await busy(control, async () => {
        pending = true;
        const controls = Array.from(form.querySelectorAll("button,input,textarea"));
        controls.forEach(element => { element.disabled = true; });
        control.textContent = action === "build" ? "Собираем карточку…" : "Сохраняем ответы…";
        form.querySelector("#build-status").textContent = action === "build" ? aiName(aiMode) + " формирует карточку. Это может занять несколько секунд." : "Сохраняем ваши ответы без ИИ.";
        try {
          if (action === "build") await api.buildCard(task.id, answers);
          else await api.updateTask(task.id, { context: task.context || task.raw_text, ...answers });
          if (!current()) return;
          memory.remove(key);
          ctx.navigate((action === "exit" ? "business/" : "edit/") + task.id);
        } catch (error) {
          if (!current()) return;
          showError(root, error, form);
          form.querySelector("#build-status").textContent = action === "build" ? aiName(aiMode) + ": сборка не завершена. Ответы сохранены в этом браузере. Повторите сборку или нажмите «Заполнить без ИИ»." : "Ответы остались в форме и в этом браузере. Повторите сохранение.";
          root.querySelector("#save-status").textContent = "Ответы сохранены в этом браузере";
        } finally {
          pending = false;
          control.textContent = label;
          controls.forEach(element => { element.disabled = false; });
        }
      });
    }
    form.addEventListener("submit", event => { event.preventDefault(); save(form.querySelector("#build-card"), "build"); });
    form.querySelector("#save-answers").addEventListener("click", event => save(event.currentTarget, "exit"));
    form.querySelector("#manual-card").addEventListener("click", event => save(event.currentTarget, "manual"));
  }
  analyze();
  return () => { disposed = true; analysisVersion++; };
}

function editor(root, ctx, initialTask) {
  let task = initialTask, timer, disposed = false, queue = Promise.resolve();
  let revision = 0, savedRevision = 0;
  const key = "card:" + ctx.user.id + ":" + task.id;
  const answersKey = "answers:" + ctx.user.id + ":" + task.id;
  const answerBackup = knownAnswers(memory.get(answersKey, {}));
  const cardBackup = memory.get(key);
  const recovered = cardBackup || Object.keys(answerBackup).length ? { ...answerBackup, ...cardBackup } : null;
  const values = { ...task, ...recovered };
  if (recovered) revision++;
  const content = '<form id="card-form" class="panel panel--roomy" novalidate><div data-errors></div>' +
    (recovered ? alertBox("info", "Восстановлены несохранённые изменения", "Проверьте поля и сохраните карточку.") : "") +
    '<div class="form-grid">' + field("title", "Название задачи", values.title, { max: 240 }) + field("industry", "Отрасль", values.industry, { max: 120 }) + "</div>" +
    '<details><summary class="text-button">Исходное описание</summary><div class="details-content">' + field("raw_text", "Исходное описание задачи", values.raw_text, { textarea: true, required: true, max: 10000 }) + "</div></details>" +
    FIELDS.map(([key, label, weight]) => '<div class="card-field"><div class="field-score caption mono" data-points="' + key + '">' + fmt(task.breakdown[key]?.earned || 0) + "/" + weight + "</div>" +
      field(key, label, values[key], { textarea: true, rows: 3, max: 10000, placeholder: hints[key] }) + "</div>").join("") +
    '<div class="form-footer"><span class="caption">Изменения сохраняются автоматически</span>' + button("Сохранить", "save-card", "secondary", "submit") + "</div></form>";
  shell(root, "edit", task, content, ratingPanel(task) + '<div class="panel stack tight">' +
    button("Подтвердить заполненные поля", "confirm-fields") +
    '<p class="caption">Нажимая, я подтверждаю достоверность проверенных мной полей. Это начислит баллы, но не опубликует задачу.</p>' +
    button(task.status === "published" ? "Открыть опубликованную задачу" : "Перейти к публикации", "next-step", "secondary") +
    '<p class="caption align-center">Публикация доступна при любом рейтинге</p>' +
    linkButton("Мои задачи", "#business/" + task.id, "ghost") + "</div>" + (task.status === "published" ? alertBox("info", "Дополнения требуют подтверждения", "Здесь показан предварительный рейтинг. До подтверждения изменений каталог сохраняет прежнюю карточку и рейтинг.") : ""));
  const form = root.querySelector("#card-form");
  const status = root.querySelector("#save-status");
  function renderRating() {
    const panel = root.querySelector(".rating-panel");
    panel.outerHTML = ratingPanel(task);
    FIELDS.forEach(([name, , weight]) => { root.querySelector('[data-points="' + name + '"]').textContent = fmt(task.breakdown[name]?.earned || 0) + "/" + weight; });
  }
  function persist() {
    clearTimeout(timer);
    if (!validate(form)) return Promise.resolve(false);
    const version = revision;
    const payload = formValues(form);
    status.textContent = "Сохраняем…";
    const request = queue.catch(() => {}).then(async () => {
      if (disposed) return false;
      try {
        task = await api.updateTask(task.id, payload);
        savedRevision = version;
        if (version === revision && !disposed && root.isConnected) { memory.remove(key); memory.remove(answersKey); }
        if (root.isConnected) {
          status.textContent = version === revision ? "Изменения сохранены" : "Есть новые изменения…";
          renderRating(); clearErrors(form);
        }
        return true;
      } catch (error) {
        if (root.isConnected) { status.textContent = "Не сохранено. Повторите попытку."; showError(root, error, form); }
        return false;
      }
    });
    queue = request;
    return request;
  }
  form.addEventListener("input", () => {
    revision++;
    memory.set(key, formValues(form));
    status.textContent = "Есть несохранённые изменения";
    clearTimeout(timer);
    timer = setTimeout(() => { if (!disposed) persist(); }, 850);
  });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    await busy(form.querySelector("#save-card"), async () => { if (await persist()) toast("Карточка сохранена"); });
  });
  root.querySelector("#confirm-fields").addEventListener("click", async e => {
    await busy(e.currentTarget, async () => {
      try {
        if (!await persist()) return;
        task = await api.confirm(task.id, task.updated_at);
        if (root.isConnected) { renderRating(); toast("Поля подтверждены. Рейтинг: " + fmt(task.score) + "/100"); }
      } catch (error) { showError(root, error, form); }
    });
  });
  root.querySelector("#next-step").addEventListener("click", async e => {
    await busy(e.currentTarget, async () => {
      if (await persist()) {
        if (root.isConnected) ctx.navigate(task.status === "published" && !task.has_pending_changes ? "task/" + task.id : "publish/" + task.id);
      }
    });
  });
  const guard = event => { if (revision !== savedRevision) { event.preventDefault(); event.returnValue = ""; } };
  window.addEventListener("beforeunload", guard);
  return () => { disposed = true; clearTimeout(timer); window.removeEventListener("beforeunload", guard); };
}

function confirm(root, ctx, initialTask) {
  let task = initialTask;
  const isUpdate = task.status === "published";
  const content = '<section class="panel panel--roomy"><div class="between"><div class="eyebrow">Итоговая карточка</div><a href="#edit/' + task.id + '">Вернуться к редактированию</a></div><h2 class="h2">' + esc(titleOf(task)) + '</h2><p class="caption">' + esc(task.industry || "Отрасль не указана") + "</p>" + readonlyCard(task) + '</section><form id="publish-form" class="panel"><div data-errors></div>' +
    '<label class="check-row check-row--wrap"><input type="checkbox" id="confirm-facts"><span>Я проверил карточку: все сведения указаны мной и могут быть переданы студентам</span></label>' +
    '<label class="check-row check-row--wrap"><input type="checkbox" id="confirm-manual"><span>Решение о выборе команды я приму сам — система никого не назначает</span></label>' +
    '<div class="form-footer">' + linkButton("Сохранить и выйти", "#business/" + task.id, "secondary") + '<button type="submit" id="publish-task" class="btn btn--primary" disabled>Опубликовать в каталоге</button></div></form>';
  shell(root, "publish", task, content, ratingPanel(task) + alertBox("info", "Всё готово к публикации", "Подтвердите сведения двумя галочками. После публикации команды смогут предложить решения."));
  const form = root.querySelector("#publish-form"), submit = form.querySelector("#publish-task");
  if (isUpdate) {
    root.querySelector("h1").textContent = "Подтвердите изменения";
    root.querySelector(".lead").textContent = "После подтверждения новая версия карточки и её рейтинг появятся в каталоге.";
    submit.textContent = "Подтвердить изменения";
  }
  const ready = () => form.querySelector("#confirm-facts").checked && form.querySelector("#confirm-manual").checked;
  form.addEventListener("change", () => { if (!submit.hasAttribute("aria-busy")) submit.disabled = !ready(); });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!ready() || submit.disabled) return;
    await busy(submit, async () => {
      try {
        task = await api.confirm(task.id, task.updated_at);
        if (!isUpdate) task = await api.publish(task.id);
        if (root.isConnected) ctx.navigate("published/" + task.id);
      } catch (error) { showError(root, error, form); }
    });
    submit.disabled = !ready();
  });
}

async function published(root, ctx, task) {
  if (task.status !== "published") { ctx.navigate("publish/" + task.id); return; }
  const catalog = await api.catalog();
  if (!root.isConnected) return;
  const rank = catalog.findIndex(t => t.id === task.id) + 1;
  root.className = "success-page";
  root.innerHTML = '<section class="panel success-panel"><div class="success-icon">' + icon("check") + '</div><h1 class="h1">Задача опубликована</h1><p class="lead muted">«' + esc(titleOf(task)) + '» уже в каталоге. Команды пришлют предложения, а вы сравните их в кабинете и сами решите, с кем работать.</p>' +
    '<div class="success-stats"><div><span class="caption">Рейтинг</span><span class="score">' + fmt(task.score) + '</span></div><div><span class="caption">Позиция</span><span class="score">' + rank + " / " + catalog.length + '</span></div><div><span class="caption">Предложений</span><span class="score">' + (catalog.find(t => t.id === task.id)?.proposals_count || 0) + '</span></div></div><div class="actions">' +
    linkButton("Открыть в каталоге", "#task/" + task.id) + linkButton("Перейти к предложениям", "#proposals/" + task.id, "secondary") + "</div></section>";
}
