// Публичная карточка и отправка отклика от выбранной команды.
import { api } from "./api.js";
import { bindTaskDeletion, deleteTaskButton } from "./task-actions.js";
import { esc, field, formValues, validate, busy, showError, memory, toast, button, linkButton, icon, titleOf, dateOf, ratingPanel, readonlyCard, statusBadge, prototypeLink, alertBox } from "./helpers.js";

export async function renderTask(root, ctx, taskId) {
  const [task, proposals] = await Promise.all([api.task(taskId), api.proposals()]);
  if (!root.isConnected) return;
  const owner = ctx.users.find(u => u.id === task.owner_id);
  const team = ctx.teams.find(t => t.id === ctx.user.team_id);
  const existing = ctx.user.role === "team" ? proposals.find(p => p.task_id === taskId) : null;
  const key = "proposal:" + ctx.user.id + ":" + taskId;
  const draft = memory.get(key, {});
  let action;
  if (ctx.user.role === "business") {
    action = '<section class="panel"><h2 class="h2">' + (task.owner_id === ctx.user.id ? "Ваша задача" : "Задача другого бизнеса") + '</h2><p class="muted">' +
      (task.owner_id === ctx.user.id ? "Дополняйте карточку и сравнивайте предложения команд в кабинете." : "Чтобы предложить решение, переключитесь на роль команды в шапке.") + "</p>" +
      (task.owner_id === ctx.user.id ? linkButton("Сравнить предложения", "#proposals/" + task.id) + linkButton("Редактировать карточку", "#edit/" + task.id, "secondary", "edit") + deleteTaskButton : linkButton("Вернуться в каталог", "#catalog", "secondary")) + "</section>";
  } else if (existing) action = sent(existing, false);
  else if (task.status !== "published") action = alertBox("info", "Задача ещё не опубликована", "Отклик станет доступен после публикации владельцем.");
  else action = '<form id="proposal-form" class="panel" novalidate><div class="stack tight"><h2 class="h2">Предложить решение</h2><p class="caption">От команды <strong>' + esc(team?.name || ctx.user.name) + '</strong></p></div><div data-errors></div>' +
    field("idea", "Идея решения", draft.idea, { textarea: true, rows: 4, required: true, min: 10, max: 5000, placeholder: "Как вы решите задачу и почему так" }) +
    field("plan", "План работы", draft.plan, { textarea: true, rows: 4, required: true, min: 10, max: 5000, placeholder: "Этапы: что сделаете на каждой неделе" }) +
    field("deadline", "Срок", draft.deadline, { required: true, min: 2, max: 120, placeholder: "3 недели" }) +
    field("link", "Ссылка на прототип", draft.link, { type: "url", max: 500, placeholder: "https://", hint: "Необязательно: можно отправить идею без готового прототипа" }) +
    button("Отправить предложение", "send-proposal", "primary", "submit") + '<p class="caption align-center">Бизнес сравнит все отклики и сам решит, с кем работать.</p></form>';
  root.className = "page task-page";
  root.innerHTML = '<div class="stack"><nav class="breadcrumbs"><a href="#catalog">Каталог</a><span>/</span><span>' + esc(titleOf(task)) + '</span></nav>' +
    '<section class="panel panel--roomy task-hero ' + (task.level === "priority" ? "task-hero--priority" : "") + '"><div class="task-meta">' + esc(task.industry || "Отрасль не указана") + " · " + esc(owner?.name || "Бизнес") + " · " + (task.status === "published" ? "опубликована" : "создана") + " " + dateOf(task.created_at) + '</div><h1 class="task-title">' + esc(titleOf(task)) + '</h1><div class="expected-result"><span class="eyebrow">Ожидаемый результат</span><p>' + esc(task.expected_result || "Не указан. Предложите свой вариант результата в отклике.") + "</p></div>" +
    (task.level === "draft" ? alertBox("draft", "Описание черновое — отклик всё равно открыт", "Команде может понадобиться уточнить результат и данные. Эти вопросы можно задать прямо в предложении.") : "") +
    '</section><section class="panel panel--roomy"><h2 class="h2">Описание задачи</h2>' + readonlyCard(task) + '</section></div><aside class="stack task-aside">' + ratingPanel(task) + '<div id="proposal-area">' + action + "</div></aside>";
  const form = root.querySelector("#proposal-form");
  const disposeDeletion = bindTaskDeletion(root, ctx, task);
  if (!form) return disposeDeletion;
  form.addEventListener("input", () => memory.set(key, formValues(form)));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!validate(form)) return;
    await busy(form.querySelector("#send-proposal"), async () => {
      try {
        const values = formValues(form);
        const proposal = await api.propose({ ...values, task_id: task.id, link: values.link.trim() || null });
        memory.remove(key);
        if (!root.isConnected) return;
        root.querySelector("#proposal-area").innerHTML = sent(proposal, true);
        toast("Предложение отправлено");
      } catch (error) { showError(root, error, form); }
    });
  });
  return disposeDeletion;
}

function sent(proposal, justSent) {
  return '<section class="panel"><div class="success-icon">' + icon("check") + '</div><h2 class="h2">' + (justSent ? "Предложение отправлено" : "Ваш отклик") + '</h2><p class="muted">Решение принимает бизнес вручную. Его можно проверить в разделе «Мои отклики».</p><div class="weight-row"><span class="caption">Статус</span>' + statusBadge(proposal.status) + '</div><div class="weight-row"><span class="caption">Срок</span><span>' + esc(proposal.deadline) + '</span></div><div class="stack tight"><span class="caption">Ваша идея</span><p>' + esc(proposal.idea) + '</p></div><div class="stack tight"><span class="caption">Прототип</span>' + prototypeLink(proposal.link) + '</div><div class="actions">' + linkButton("Мои отклики", "#proposals") + linkButton("В каталог", "#catalog", "secondary") + "</div></section>";
}
