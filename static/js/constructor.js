// Четыре шага конструктора: описание, вопросы, сохранение карточки и явная публикация.
import { api } from "./api.js";
import { esc, fmt, FIELDS, field, formValues, validate, clearErrors, showError, busy, memory, toast, button, linkButton, icon, ratingPanel, readonlyCard, titleOf, alertBox, INDUSTRIES } from "./helpers.js";

const TITLES = { new: "Опишите задачу", questions: "Ответьте на вопросы", edit: "Проверьте карточку", publish: "Подтвердите и опубликуйте" };
const SUBTITLES = {
  new: "Начните с короткого описания. Карточку, рейтинг и публикацию соберём по шагам.",
  questions: "Уточните детали, чтобы команда понимала результат, данные и условия работы.",
  edit: "Карточка собрана из вашего текста и ответов. Баллы пересчитываются после сохранения.",
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
const stepper = (step) => '<ol class="stepper" aria-label="Шаги создания задачи">' + ["Описание", "Уточнение", "Карточка", "Публикация"].map((label, i) =>
  '<li class="' + (i + 1 < step ? "is-done" : "") + '"' + (i + 1 === step ? ' aria-current="step"' : "") + '><span class="stepper__dot">' + (i + 1 < step ? icon("check") : i + 1) + "</span><span>" + label + "</span></li>").join("") + "</ol>";
function shell(root, mode, task, content, aside) {
  const step = { new: 1, questions: 2, edit: 3, publish: 4 }[mode];
  root.className = "wizard";
  root.innerHTML = '<div class="wizard-heading stack"><div class="between"><nav class="breadcrumbs"><a href="#business">Мои задачи</a><span>/</span><span>' + (task ? esc(titleOf(task)) : "Новая задача") + '</span></nav><span class="caption" id="save-status" role="status">' + (task ? "Изменения сохранены" : "Описание ещё не отправлено") + "</span></div>" + stepper(step) +
    '<div class="stack tight"><h1 class="h1">' + TITLES[mode] + '</h1><p class="lead muted">' + SUBTITLES[mode] + '</p></div></div><div class="page wizard-page"><div class="stack" id="wizard-content">' + content + '</div><aside class="stack sticky-aside" id="wizard-aside">' + aside + "</aside></div>";
}
const weightsPanel = () => '<section class="panel"><div class="eyebrow">Как считается рейтинг</div><p class="muted">Баллы показывают полноту карточки. Перед публикацией вы проверите и подтвердите сведения.</p><div>' +
  FIELDS.map(([, label, weight]) => '<div class="weight-row"><span>' + label + '</span><span class="mono">' + weight + "</span></div>").join("") +
  '</div><p class="caption">Пустое поле — 0 баллов. Текст короче 30 символов даёт половину веса, от 30 — полный вес.</p></section>';

export async function renderConstructor(root, ctx, mode, taskId) {
  let task = mode === "new" ? null : await api.task(taskId);
  if (!root.isConnected) return;
  if (task && task.owner_id !== ctx.user.id) throw new Error("Редактирование доступно только владельцу задачи");
  if (mode === "published") return published(root, ctx, task);
  if (mode === "questions" && task.status === "published") { ctx.navigate("edit/" + task.id); return; }
  if (mode === "publish" && task.status === "published") { ctx.navigate("published/" + task.id); return; }
  if (mode === "new") return draft(root, ctx);
  if (mode === "questions") return questions(root, ctx, task);
  if (mode === "edit") return editor(root, ctx, task);
  return confirm(root, ctx, task);
}

function draft(root, ctx) {
  const key = "draft:" + ctx.user.id;
  const values = memory.get(key, {});
  const body = '<form id="draft-form" class="panel panel--roomy" novalidate><div data-errors></div>' +
    field("raw_text", "Опишите задачу своими словами", values.raw_text, { textarea: true, rows: 6, required: true, max: 10000, placeholder: "Что происходит сейчас и что вы хотите изменить?", hint: "Пишите как есть. На следующем шаге появятся уточняющие вопросы — новых фактов система не добавляет." }) +
    '<div class="caption mono align-right" id="raw-count"></div><div class="form-grid">' +
    field("title", "Рабочее название", values.title, { max: 240, hint: "Можно изменить позже", placeholder: "Например: Прогноз загрузки столовой" }) +
    field("industry", "Отрасль", values.industry, { max: 120, placeholder: "Например: Образование" }) +
    '</div><div class="form-footer"><span class="caption">Шаг 1 из 4</span><div class="actions">' +
    linkButton("Отмена", "#business", "ghost") + button("Проверить полноту", "create-draft", "primary", "submit") + "</div></div></form>";
  shell(root, "new", null, body, weightsPanel());
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
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!validate(form)) return;
    await busy(form.querySelector("#create-draft"), async () => {
      try {
        const task = await api.draft(formValues(form));
        memory.remove(key);
        if (root.isConnected) ctx.navigate("questions/" + task.id);
      } catch (error) { showError(root, error, form); }
    });
  });
}

async function questions(root, ctx, task) {
  const analysis = await api.questions(task.id);
  if (!root.isConnected) return;
  const key = "answers:" + ctx.user.id + ":" + task.id;
  const values = { ...task, ...memory.get(key, {}) };
  const cards = analysis.questions.map((question, i) =>
    '<div class="question"><div class="question-number mono">' + String(i + 1).padStart(2, "0") + '</div><div class="stack tight">' +
    field(question.field, question.text, values[question.field], {
      textarea: !["title", "industry"].includes(question.field), rows: 3,
      max: question.field === "title" ? 240 : question.field === "industry" ? 120 : "",
      placeholder: "Ваш ответ", hint: hints[question.field] || "",
    }) + '<button type="button" class="text-button skip-question" data-skip="' + question.field + '">Пропустить вопрос</button></div></div>').join("");
  const content = '<section class="panel"><div class="between"><span class="eyebrow">Ваше описание</span>' +
    linkButton("Изменить", "#edit/" + task.id, "ghost", "edit") + '</div><blockquote>' + esc(task.raw_text) + '</blockquote></section>' +
    '<form id="answers-form" class="panel panel--roomy" novalidate><div data-errors></div><div class="between"><h2 class="h2">' + analysis.questions.length + ' уточняющих вопросов</h2><span class="caption" id="answered-count"></span></div><div>' +
    cards + '</div><div class="form-footer">' + button("Сохранить и выйти", "save-answers", "secondary") + button("Собрать карточку", "build-card", "primary", "submit") + "</div></form>";
  shell(root, "questions", task, content, weightsPanel() + alertBox("info", "Только ваши сведения", "Карточка соберётся из исходного текста и ответов. Вопрос можно пропустить и заполнить поле позже."));
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
  }
  form.addEventListener("submit", event => { event.preventDefault(); save(form.querySelector("#build-card"), false); });
  form.querySelector("#save-answers").addEventListener("click", event => save(event.currentTarget, true));
}

function editor(root, ctx, initialTask) {
  let task = initialTask, timer, disposed = false, queue = Promise.resolve();
  let revision = 0, savedRevision = 0;
  const key = "card:" + ctx.user.id + ":" + task.id;
  const recovered = memory.get(key);
  const values = { ...task, ...recovered };
  if (recovered) revision++;
  const content = '<form id="card-form" class="panel panel--roomy" novalidate><div data-errors></div>' +
    (recovered ? alertBox("info", "Восстановлены несохранённые изменения", "Проверьте поля и сохраните карточку.") : "") +
    '<div class="form-grid">' + field("title", "Название задачи", values.title, { max: 240 }) + field("industry", "Отрасль", values.industry, { max: 120 }) + "</div>" +
    '<details><summary class="text-button">Исходное описание</summary><div class="details-content">' + field("raw_text", "Исходное описание задачи", values.raw_text, { textarea: true, required: true, max: 10000 }) + "</div></details>" +
    FIELDS.map(([key, label, weight]) => '<div class="card-field"><div class="field-score caption mono" data-points="' + key + '">' + fmt(task.breakdown[key]?.earned || 0) + "/" + weight + "</div>" +
      field(key, label, values[key], { textarea: true, rows: 3, placeholder: hints[key] }) + "</div>").join("") +
    '<div class="form-footer"><span class="caption">Изменения сохраняются автоматически</span>' + button("Сохранить", "save-card", "secondary", "submit") + "</div></form>";
  shell(root, "edit", task, content, ratingPanel(task) + '<div class="panel">' +
    button(task.status === "published" ? "Открыть опубликованную задачу" : "Подтвердить карточку", "next-step") +
    '<p class="caption align-center">Публикация доступна при любом рейтинге</p>' +
    linkButton("Мои задачи", "#business/" + task.id, "ghost") + "</div>");
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
        if (version === revision) memory.remove(key);
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
  root.querySelector("#next-step").addEventListener("click", async e => {
    await busy(e.currentTarget, async () => {
      if (await persist()) {
        if (root.isConnected) ctx.navigate(task.status === "published" ? "task/" + task.id : "publish/" + task.id);
      }
    });
  });
  const guard = event => { if (revision !== savedRevision) { event.preventDefault(); event.returnValue = ""; } };
  window.addEventListener("beforeunload", guard);
  return () => { disposed = true; clearTimeout(timer); window.removeEventListener("beforeunload", guard); };
}

function confirm(root, ctx, initialTask) {
  let task = initialTask;
  const content = '<section class="panel panel--roomy"><div class="between"><div class="eyebrow">Итоговая карточка</div><a href="#edit/' + task.id + '">Вернуться к редактированию</a></div><h2 class="h2">' + esc(titleOf(task)) + '</h2><p class="caption">' + esc(task.industry || "Отрасль не указана") + "</p>" + readonlyCard(task) + '</section><form id="publish-form" class="panel"><div data-errors></div>' +
    '<label class="check-row check-row--wrap"><input type="checkbox" id="confirm-facts"><span>Я проверил карточку: все сведения указаны мной и могут быть переданы студентам</span></label>' +
    '<label class="check-row check-row--wrap"><input type="checkbox" id="confirm-manual"><span>Решение о выборе команды я приму сам — система никого не назначает</span></label>' +
    '<div class="form-footer">' + linkButton("Сохранить и выйти", "#business/" + task.id, "secondary") + '<button type="submit" id="publish-task" class="btn btn--primary" disabled>Опубликовать в каталоге</button></div></form>';
  shell(root, "publish", task, content, ratingPanel(task) + alertBox("info", "Всё готово к публикации", "Подтвердите сведения двумя галочками. После публикации команды смогут предложить решения."));
  const form = root.querySelector("#publish-form"), submit = form.querySelector("#publish-task");
  const ready = () => form.querySelector("#confirm-facts").checked && form.querySelector("#confirm-manual").checked;
  form.addEventListener("change", () => { if (!submit.hasAttribute("aria-busy")) submit.disabled = !ready(); });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!ready() || submit.disabled) return;
    await busy(submit, async () => {
      try {
        if (task.status !== "confirmed") task = await api.confirm(task.id);
        task = await api.publish(task.id);
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
