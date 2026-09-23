// Три этапа работы команды; баллы и допуск к этапам подтверждает сервер.
import { api } from "./api.js";
import { esc, fmt, icon, titleOf, dateOf, statusBadge, field, formValues, validate, clearErrors, showError, busy, toast, linkButton, prototypeLink, alertBox } from "./helpers.js";

const stageNames = { not_started: "Не начат", pending: "На проверке", confirmed: "Подтверждён", rejected: "На доработке" };
const stageHints = {
  research: "Что изучили, какие потребности и ограничения выяснили, к каким выводам пришли?",
  prototype: "Что уже работает в прототипе и как это проверить?",
  final: "Какой результат передаёте бизнесу и как проверили критерии успеха?",
};

export async function renderProgress(root, ctx, proposalId) {
  const [proposals, initialSnapshot] = await Promise.all([api.proposals(), api.progress(proposalId)]);
  const proposal = proposals.find(item => item.id === proposalId);
  if (!proposal) throw new Error("Отклик недоступен текущему пользователю");
  const task = await api.task(proposal.task_id);
  if (!root.isConnected) return;
  const team = ctx.teams.find(item => item.id === proposal.team_id);
  const isTeam = ctx.user.role === "team";
  const accepted = proposal.status === "accepted";
  const back = isTeam ? "#proposals" : "#proposals/" + proposal.task_id;
  let snapshot = initialSnapshot, pending = false, disposed = false;
  root.className = "content-wide stack progress-page";

  function stageMarkup(stage, index) {
    const previousConfirmed = snapshot.stages.slice(0, index).every(item => item.status === "confirmed");
    const canSubmit = accepted && isTeam && previousConfirmed && ["not_started", "rejected"].includes(stage.status);
    const canReview = accepted && !isTeam && stage.status === "pending";
    let action = "";
    if (canSubmit) {
      action = '<form class="stack progress-form" data-progress-submit="' + esc(stage.stage) + '" novalidate><div data-errors role="alert"></div>' +
        field("description", "Что сделано на этапе", stage.description || "", { textarea: true, rows: 4, required: true, min: 10, max: 5000, placeholder: stageHints[stage.stage], hint: "Опишите фактический результат. После отправки его проверит бизнес." }) +
        field("link", "Ссылка на результат", stage.link || "", { type: "url", max: 500, placeholder: "https://", hint: "Необязательно: исследование, прототип или итоговые материалы по HTTP(S)-ссылке." }) +
        '<div class="actions"><button type="submit" class="btn btn--primary">' + (stage.status === "rejected" ? "Отправить повторно" : "Отправить на проверку") + '</button><span class="caption">Баллы начислятся после подтверждения бизнеса</span></div></form>';
    } else if (canReview) {
      action = '<form class="stack progress-form" data-progress-review="' + esc(stage.stage) + '" novalidate><div data-errors role="alert"></div>' +
        field("comment", "Комментарий к этапу", "", { textarea: true, rows: 3, max: 2000, placeholder: "Что принято или что нужно исправить", hint: "Комментарий увидит команда. При возврате поясните, что нужно доработать." }) +
        '<div class="actions"><button type="submit" class="btn btn--primary" data-review="confirm">' + icon("check") + 'Подтвердить этап</button><button type="submit" class="btn btn--secondary" data-review="reject">Вернуть на доработку</button></div></form>';
    } else if (stage.status === "pending") {
      action = '<p class="progress-stage__note">Результат отправлен на проверку. Подождите решения бизнеса, затем обновите страницу прогресса.</p>';
    } else if (stage.status !== "confirmed") {
      const message = !accepted ? "Отправка и проверка этапов доступны, когда бизнес выбрал этот отклик."
        : !previousConfirmed ? "Этап откроется после подтверждения предыдущих этапов."
          : "Ожидаем результат команды" + (stage.status === "rejected" ? " после доработки." : ".");
      action = '<p class="progress-stage__note">' + message + '</p>';
    }
    const submission = stage.description && !canSubmit
      ? '<div class="stack tight progress-stage__result"><div class="eyebrow">Результат команды</div><p>' + esc(stage.description) + '</p>' + (stage.link ? prototypeLink(stage.link) : '<span class="caption">Ссылка не приложена</span>') + '</div>'
      : "";
    return '<article class="panel progress-stage" data-stage="' + esc(stage.stage) + '" data-progress-status="' + esc(stage.status) + '"><div class="progress-stage__heading"><div class="stack tight"><span class="eyebrow">Этап ' + (index + 1) + ' из ' + snapshot.stages.length + '</span><h2 class="h2" tabindex="-1">' + esc(stage.title) + '</h2></div><div class="progress-stage__meta"><span class="progress-stage__status progress-stage__status--' + esc(stage.status) + '">' + esc(stageNames[stage.status] || stage.status) + '</span><span class="mono caption">' + fmt(stage.points) + (stage.status === "confirmed" ? " баллов начислено" : " баллов за подтверждение") + '</span></div></div>' +
      submission + (stage.review_comment ? '<div class="progress-review"><strong>Комментарий бизнеса</strong><p>' + esc(stage.review_comment) + '</p></div>' : "") +
      (stage.submitted_at || stage.reviewed_at ? '<div class="caption">' + (stage.submitted_at ? "Отправлено " + dateOf(stage.submitted_at) : "") + (stage.reviewed_at ? " · Проверено " + dateOf(stage.reviewed_at) : "") + '</div>' : "") + action + '</article>';
  }

  function render(focusStage = null) {
    root.innerHTML = '<nav class="breadcrumbs" aria-label="Путь к прогрессу"><a href="' + back + '">' + (isTeam ? "Мои отклики" : "Предложения") + '</a><span>/</span><span>Прогресс</span></nav>' +
      '<div class="page-heading"><div class="stack tight"><h1 class="h1">Прогресс по задаче</h1><p class="muted">' + esc(team?.name || "Команда " + proposal.team_id) + ' · <a href="#task/' + task.id + '">' + esc(titleOf(task)) + '</a></p></div><button type="button" class="btn btn--secondary" data-refresh-progress>Обновить прогресс</button></div>' +
      '<section class="panel progress-summary"><div class="progress-summary__intro"><div class="stack tight"><h2 class="h2">Подтверждённый результат</h2><p class="caption">Бизнес проверяет каждый этап. Баллы начисляются один раз за подтверждение.</p></div>' + statusBadge(proposal.status) + '</div><div class="progress-stats"><div><span class="caption">По этой задаче</span><strong class="score" data-progress-points>' + fmt(snapshot.earned_points) + '<span class="caption"> / 100</span></strong></div><div><span class="caption">Всего у команды</span><strong class="score" data-team-points>' + fmt(snapshot.team_points) + '</strong></div><div><span class="caption">Подтверждённый прогресс</span><strong class="score" data-completion-percent>' + fmt(snapshot.completion_percent) + '%</strong></div></div><progress class="progress-total" value="' + Number(snapshot.completion_percent) + '" max="100" aria-label="Подтверждённый прогресс">' + fmt(snapshot.completion_percent) + '%</progress></section>' +
      (!accepted ? alertBox("info", "Отклик пока не выбран", "Просмотр результатов доступен. Отправлять и проверять этапы можно только после выбора команды бизнесом.") : snapshot.stages.every(stage => stage.status === "confirmed") ? alertBox("success", "Все этапы подтверждены", "Бизнес принял итоговый результат. Баллы за эту задачу учтены в общей сумме команды.") : "") +
      '<div class="progress-stages stack">' + snapshot.stages.map(stageMarkup).join("") + '</div><div class="actions">' + linkButton(isTeam ? "Мои отклики" : "Вернуться к предложениям", back, "secondary", "back") + '</div>';
    root.querySelector("[data-refresh-progress]").addEventListener("click", () => { if (!pending) ctx.navigate("progress/" + proposalId); });
    root.querySelectorAll("[data-progress-submit]").forEach(form => form.addEventListener("submit", event => {
      event.preventDefault();
      if (!validate(form)) return;
      const values = formValues(form);
      mutate(form, event.submitter || form.querySelector('[type="submit"]'), form.dataset.progressSubmit,
        () => api.submitProgress(proposalId, { stage: form.dataset.progressSubmit, description: values.description.trim(), link: values.link.trim() || null }),
        "Результат этапа отправлен на проверку");
    }));
    root.querySelectorAll("[data-progress-review]").forEach(form => form.addEventListener("submit", event => {
      event.preventDefault();
      const control = event.submitter;
      if (!control?.dataset.review || !validate(form)) return;
      const stage = snapshot.stages.find(item => item.stage === form.dataset.progressReview);
      const decision = control.dataset.review;
      const comment = formValues(form).comment.trim() || null;
      mutate(form, control, stage.stage,
        () => api.reviewProgress(proposalId, stage.stage, decision, { submission_token: stage.submission_token, comment }),
        decision === "confirm" ? "Этап подтверждён. Баллы начислены команде" : "Этап возвращён на доработку");
    }));
    if (focusStage) root.querySelector('[data-stage="' + focusStage + '"] h2')?.focus({ preventScroll: true });
  }

  async function mutate(form, control, stage, action, message) {
    if (pending || disposed) return;
    clearErrors(form);
    await busy(control, async () => {
      pending = true;
      const controls = Array.from(root.querySelectorAll("button,input,textarea"));
      controls.forEach(element => { element.disabled = true; });
      try {
        const updated = await action();
        if (disposed || !root.isConnected) return;
        snapshot = updated;
        render(stage);
        toast(message);
      } catch (error) {
        if (!disposed && root.isConnected) showError(root, error, form);
      } finally {
        pending = false;
        controls.forEach(element => { element.disabled = false; });
      }
    });
  }
  render();
  return () => { disposed = true; };
}
