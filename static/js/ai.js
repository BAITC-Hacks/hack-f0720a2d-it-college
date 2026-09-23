// Настройки подключения сохраняются сервером; ключ не попадает в LocalStorage.
import { api } from "./api.js";
import { esc, field, formValues, validate, busy, showError, clearErrors, toast, linkButton, alertBox } from "./helpers.js";

export async function renderAISettings(root, ctx) {
  let settings = await api.aiSettings();
  if (!root.isConnected) return;
  root.className = "content-wide stack ai-settings";
  root.innerHTML = '<div class="page-heading"><div class="stack tight"><h1 class="h1">Настройки AI</h1><p class="muted">Выберите OpenAI, совместимый сервер или локальные шаблоны для анализа задач.</p></div>' + linkButton("Создать задачу", "#new") + '</div>' +
    '<form class="panel panel--roomy stack" id="ai-settings-form" novalidate><div data-errors></div>' +
    '<div class="field" data-field="provider"><label class="field__label" for="ai-provider">Режим анализа</label><select class="select" name="provider" id="ai-provider"><option value="auto">Настройки сервера</option><option value="openai">OpenAI</option><option value="compatible">Совместимый AI-сервер · LM Studio / llmster</option><option value="stub">Локальные шаблоны</option></select><div class="field__error"></div><p class="caption" id="ai-provider-hint"></p></div>' +
    field("base_url", "Адрес API", settings.base_url, { type: "url", required: true, max: 2000, placeholder: "http://127.0.0.1:1234/v1", hint: "Локальный или публичный HTTP(S) адрес. Для llmster можно указать https://ваш-сервер/v1." }) +
    field("api_key", "API-ключ", "", { type: "password", hint: settings.has_api_key ? "Ключ уже сохранён. Оставьте поле пустым, чтобы сохранить его для этого адреса." : "Необязательно для локального сервера без авторизации." }) +
    '<label class="check-row"><input type="checkbox" name="clear_api_key"><span>Удалить сохранённый ключ</span></label>' +
    '<div class="field" data-field="model"><label class="field__label" for="ai-model">Модель</label><select class="select" name="model" id="ai-model"><option value="">Автоматический выбор модели</option>' +
    (settings.model ? '<option selected value="' + esc(settings.model) + '">' + esc(settings.model) + '</option>' : '') + '</select><div class="field__error"></div><p class="caption">Список загружается с выбранного сервера. Модель должна поддерживать текстовые диалоги.</p></div>' +
    '<div class="actions"><button type="button" class="btn btn--secondary" id="refresh-models">Обновить список моделей</button><span class="caption" id="ai-connection-status" role="status"></span></div>' +
    '<details><summary class="text-button">Совместимость ответа</summary><div class="details-content"><label class="field__label" for="ai-format">Формат JSON</label><select class="select" id="ai-format" name="response_format"><option value="auto">Автоматически</option><option value="json_schema">JSON Schema</option><option value="json_object">JSON Object</option><option value="text">JSON в тексте</option></select><p class="caption">Автоматический режим проверяет поддержку формата сервером. Полученные сведения всегда проходят проверку.</p></div></details>' +
    '<div class="form-footer"><span class="caption">Настройки сохраняются для текущего бизнес-пользователя.</span><button type="submit" class="btn btn--primary" id="save-ai-settings">Сохранить настройки</button></div></form>' +
    alertBox("info", "Модель работает с вашими сведениями", "При выборе OpenAI или совместимого AI-сервера описание и ответы отправляются этому провайдеру. Локальные шаблоны работают без внешних запросов. Перед публикацией вы проверяете и подтверждаете карточку.");
  const form = root.querySelector("form"), status = root.querySelector("#ai-connection-status");
  form.elements.api_key.autocomplete = "new-password";
  form.elements.provider.value = settings.provider || "auto";
  form.elements.response_format.value = settings.response_format;
  const payload = () => {
    const values = formValues(form);
    if (["auto", "stub"].includes(values.provider)) return { provider: values.provider };
    return { ...values, base_url: values.provider === "openai" ? "https://api.openai.com/v1" : values.base_url, clear_api_key: form.elements.clear_api_key.checked };
  };
  let loading = false;
  const providerHint = root.querySelector("#ai-provider-hint");
  function applyMode() {
    const provider = form.elements.provider.value, custom = ["openai", "compatible"].includes(provider);
    const compatible = provider === "compatible";
    form.elements.base_url.required = compatible;
    form.elements.base_url.disabled = loading || !compatible;
    if (provider === "openai") form.elements.base_url.value = "https://api.openai.com/v1";
    for (const name of ["api_key", "clear_api_key", "model"]) form.elements[name].disabled = loading || !custom;
    form.elements.response_format.disabled = loading || !compatible;
    root.querySelector("#refresh-models").disabled = loading || provider === "stub" || provider === "auto" && settings.effective_provider === "stub";
    const effective = { openai: "OpenAI", compatible: "совместимый AI-сервер", stub: "локальные шаблоны" }[settings.effective_provider] || "настройки сервера";
    providerHint.textContent = provider === "auto" ? "Сейчас используется: " + effective + ". Сохранение этого режима отменит личное подключение и вернёт настройки приложения." : provider === "openai" ? "Описание и ответы отправляются OpenAI. Адрес фиксирован; ключ совместимого сервера здесь не используется." : provider === "stub" ? "Локальные шаблоны работают без внешних API. Ключ и модель не нужны." : "Описание и ответы отправляются указанному серверу. Для этого подключения используется отдельный ключ.";
  }
  const freeze = (value) => {
    loading = value;
    form.querySelectorAll("input,select,button").forEach(control => { control.disabled = value; });
    applyMode();
  };
  const resetConnection = () => {
    form.elements.api_key.value = "";
    form.elements.clear_api_key.checked = false;
    form.elements.model.innerHTML = '<option value="">Автоматический выбор модели</option>';
  };
  applyMode();
  async function refresh() {
    if (loading || !validate(form)) return;
    const body = payload();
    freeze(true);
    status.textContent = "Подключаемся к серверу…";
    try {
      const result = await api.aiModels(body);
      if (!root.isConnected) return;
      form.elements.model.innerHTML = '<option value="">Автоматический выбор модели</option>' + result.models.map(model =>
        '<option value="' + esc(model.id) + '">' + esc(model.id) + (model.chat_candidate ? '' : ' · возможно, не для диалогов') + '</option>').join("");
      const selectedModel = body.model ?? settings.model;
      form.elements.model.value = result.models.some(model => model.id === selectedModel) ? selectedModel : "";
      status.textContent = result.models.length ? 'Доступно моделей: ' + result.models.length + (result.selected_model ? '. Автовыбор: ' + result.selected_model : '. Выберите модель.') : "Сервер доступен, но список моделей пуст. Добавьте текстовую модель на сервере.";
      clearErrors(form);
    } catch (error) {
      if (root.isConnected) { status.textContent = "Подключение не проверено"; showError(root, error, form); }
    } finally { freeze(false); }
  }
  form.elements.base_url.addEventListener("input", () => {
    resetConnection();
    status.textContent = "Обновите список для нового адреса. Старый ключ на новый адрес не отправляется.";
  });
  form.elements.provider.addEventListener("change", () => {
    resetConnection();
    form.elements.base_url.value = form.elements.provider.value === "compatible" ? "http://127.0.0.1:1234/v1" : settings.base_url || "";
    status.textContent = "Режим изменится после сохранения настроек.";
    applyMode();
  });
  root.querySelector("#refresh-models").addEventListener("click", refresh);
  form.elements.model.addEventListener("change", () => {
    status.textContent = "Сохраните настройки, чтобы применить выбор модели.";
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (loading || !validate(form)) return;
    const body = payload();
    await busy(root.querySelector("#save-ai-settings"), async () => {
      freeze(true);
      try {
        settings = await api.saveAISettings(body);
        if (!root.isConnected) return;
        form.elements.base_url.value = settings.base_url;
        form.elements.response_format.value = settings.response_format;
        form.elements.api_key.value = "";
        form.elements.clear_api_key.checked = false;
        root.querySelector("#hint-api_key").textContent = settings.has_api_key ? "Ключ сохранён. Оставьте поле пустым, чтобы сохранить его для этого адреса." : "Ключ не задан.";
        status.textContent = settings.model ? "Настройки сохранены. Модель: " + settings.model : "Настройки сохранены.";
        clearErrors(form); toast("Настройки AI сохранены");
      } catch (error) { if (root.isConnected) showError(root, error, form); }
      finally { freeze(false); }
    });
  });
  if (!root.querySelector("#refresh-models").disabled) await refresh();
}
