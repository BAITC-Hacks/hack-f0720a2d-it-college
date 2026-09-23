// Удаление собственной задачи с явным подтверждением и очисткой локальных копий форм.
import { api } from "./api.js";
import { esc, memory, showError, titleOf, toast } from "./helpers.js";

export const deleteTaskButton = '<button type="button" class="btn btn--danger btn--sm" data-delete-task>Удалить задачу</button>';

export function bindTaskDeletion(root, ctx, task) {
  const trigger = root.querySelector("[data-delete-task]");
  if (!trigger || ctx.user.role !== "business" || task.owner_id !== ctx.user.id) return () => {};
  let dialog = null, pending = false, disposed = false;

  function close() {
    dialog?.close();
    dialog?.remove();
    dialog = null;
    if (!disposed && root.isConnected) trigger.focus({ preventScroll: true });
  }

  trigger.addEventListener("click", () => {
    if (dialog || disposed) return;
    dialog = document.createElement("dialog");
    dialog.className = "delete-dialog";
    dialog.setAttribute("data-delete-dialog", "");
    dialog.setAttribute("aria-labelledby", "delete-task-title");
    dialog.setAttribute("aria-describedby", "delete-task-description");
    dialog.innerHTML = '<div class="stack"><h2 class="h2" id="delete-task-title">Удалить задачу?</h2>' +
      '<p class="delete-task-name">«' + esc(titleOf(task)) + '»</p>' +
      '<p id="delete-task-description">Карточка, черновик её изменений, все отклики и этапы работы будут удалены без возможности восстановления. Баллы за эти этапы перестанут учитываться у команд.</p>' +
      '<div data-errors role="alert"></div><div class="delete-dialog-actions">' +
      '<button type="button" class="btn btn--secondary" data-cancel-delete autofocus>Отмена</button>' +
      '<button type="button" class="btn btn--danger delete-confirm" data-confirm-delete>Удалить задачу и отклики</button>' +
      '</div></div>';
    root.append(dialog);
    dialog.querySelector("[data-cancel-delete]").addEventListener("click", close);
    dialog.addEventListener("cancel", event => { event.preventDefault(); if (!pending) close(); });
    dialog.querySelector("[data-confirm-delete]").addEventListener("click", async () => {
      if (pending || disposed) return;
      pending = true;
      const currentDialog = dialog;
      currentDialog.querySelector("[data-errors]").innerHTML = "";
      currentDialog.querySelectorAll("button").forEach(button => { button.disabled = true; });
      const confirm = currentDialog.querySelector("[data-confirm-delete]");
      confirm.setAttribute("aria-busy", "true");
      confirm.textContent = "Удаляем…";
      try {
        await api.deleteTask(task.id);
        // Убираем только копии форм удалённой задачи, остальные черновики остаются.
        for (const user of ctx.users) {
          for (const kind of ["card", "answers", "proposal"]) memory.remove(`${kind}:${user.id}:${task.id}`);
        }
        if (!disposed && root.isConnected) {
          close();
          toast("Задача и связанные отклики удалены");
          ctx.navigate("business");
        }
      } catch (error) {
        if (currentDialog.isConnected) showError(currentDialog, error);
      } finally {
        pending = false;
        if (currentDialog.isConnected) {
          currentDialog.querySelectorAll("button").forEach(button => { button.disabled = false; });
          confirm.removeAttribute("aria-busy");
          confirm.textContent = "Удалить задачу и отклики";
        }
      }
    });
    dialog.showModal();
  });

  return () => { disposed = true; close(); };
}
