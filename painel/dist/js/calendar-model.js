// Pure presentation helpers. Keep business authorization and conflicts on the server.
export const statusNames = {
  confirmed: "Confirmado",
  cancelled: "Cancelado",
  reserved: "Reservado",
};

export const resorts = { cs: "Costa do Sauípe", rq: "Rio Quente" };
export const phases = {
  setup: "Montagem",
  event: "Evento",
  teardown: "Desmontagem",
};
export const months = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );

export const fmt = (date) =>
  String(date).slice(0, 10).split("-").reverse().join("/");
export const normalized = (value) =>
  String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

export const option = (value, text, selected) =>
  `<option value="${esc(value)}" ${String(value) === String(selected) ? "selected" : ""}>${esc(text)}</option>`;
export const pill = (status) =>
  `<span class="status-pill status-${status}">${statusNames[status]}</span>`;
export const btn = (action, label, attrs = "", primary = false) =>
  `<button type="button" class="btn ${primary ? "primary" : ""}" data-action="${action}" ${attrs}>${label}</button>`;

export const passwordField = (label, name, autocomplete, min = 0, max = 10) =>
  `<div class="password-input"><label for="password-${name}">${label}</label><div class="password-control"><input id="password-${name}" name="${name}" type="password" autocomplete="${autocomplete}" required ${min ? `minlength="${min}"` : ""} maxlength="${max}"><button type="button" class="password-toggle" data-action="toggle-password" aria-controls="password-${name}" aria-label="Mostrar ${label.toLowerCase()}" aria-pressed="false">Mostrar</button></div></div>`;

export function monthRange(year, month) {
  const prefix = `${year}-${String(month + 1).padStart(2, "0")}`;
  return {
    from: `${prefix}-01`,
    to: `${prefix}-${new Date(year, month + 1, 0).getDate()}`,
  };
}

export function buildQueryString(state, full = false) {
  let dates = full
    ? { from: "2026-01-01", to: "2028-12-31" }
    : monthRange(state.year, state.month);
  if (state.view === "reports")
    dates = { from: state.reportFrom, to: state.reportTo };
  return new URLSearchParams({
    ...dates,
    resort: state.resort,
    status: state.status,
    search: state.search,
  }).toString();
}

export function allocationResort(config) {
  return config && resorts[config.resort_id] ? config.resort_id : "unassigned";
}

export function spaceOptions(catalog, resort, selected = "") {
  return (
    option(
      "",
      resort ? "Selecione um espaço" : "Selecione o empreendimento",
      selected,
    ) +
    catalog
      .filter((config) => allocationResort(config) === resort)
      .map((config) => option(config.id, config.name, selected))
      .join("")
  );
}
