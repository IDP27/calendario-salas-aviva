import { request, repository } from "./storage.js";
import { createViews } from "./calendar-views.js";
import {
  allocationResort,
  btn,
  buildQueryString,
  esc,
  fmt,
  monthRange,
  months,
  normalized,
  option,
  passwordField,
  phases,
  pill,
  resorts,
  spaceOptions as catalogSpaceOptions,
  statusNames,
} from "./calendar-model.js";
const $ = (s) => document.querySelector(s);
const today = new Date();
const state = {
  user: null,
  view: "calendar",
  year: Math.min(2028, Math.max(2026, today.getFullYear())),
  month: today.getMonth(),
  resort: "all",
  search: "",
  status: "",
  mode: matchMedia("(max-width:760px)").matches ? "list" : "grid",
  catalog: [],
  resources: [],
  bookings: [],
  occupying: [],
  days: [],
  calendar: [],
  users: [],
  online: true,
  lastSync: "",
  reportFrom: "2026-01-01",
  reportTo: "2028-12-31",
};
let modalDirty = false,
  loading = false,
  refreshNumber = 0,
  toastTimer;
const resourceName = (id) =>
  state.resources.find((r) => r.id === id)?.name || id;
const resortName = (id) => resorts[id] || "Empreendimento não definido";
const {
  sidebar,
  toolbar,
  calendarView,
  bookingList,
  catalogView,
  reportsView,
  usersView,
} = createViews(state, resortName);
function toast(text, error = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = `visible ${error ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = ""), error ? 9000 : 4000);
}
function errorView(error) {
  toast(error.message, true);
  if (error.status === 401) {
    state.user = null;
    closeModal(true);
    boot();
  }
}
function range() {
  return monthRange(state.year, state.month);
}
function queryString(full = false) {
  return buildQueryString(state, full);
}
function closeModal(force = false) {
  if (
    !force &&
    modalDirty &&
    !confirm("Descartar as alterações não salvas deste formulário?")
  )
    return false;
  $("#editor").close();
  $("#editor").innerHTML = "";
  modalDirty = false;
  return true;
}
function modal(title, body, actions = "", wide = false) {
  if ($("#editor").open && !closeModal()) return false;
  const el = $("#editor");
  el.className = wide ? "wide-modal" : "";
  el.innerHTML = `<div class="modal-head"><h2 id="editor-title">${title}</h2>${btn("close", "×", 'aria-label="Fechar"')}</div><div class="modal-body">${body}</div>${actions ? `<div class="modal-actions">${actions}</div>` : ""}`;
  modalDirty = false;
  el.showModal();
  el.oncancel = (e) => {
    e.preventDefault();
    closeModal();
  };
  el.oninput = () => (modalDirty = true);
  return true;
}
function bindForm(selector, handler) {
  const form = $(selector);
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    const submit =
      form.querySelector("[type=submit]") ||
      document.querySelector(`[form="${form.id}"]`);
    if (submit) submit.disabled = true;
    const err = form.querySelector(".form-error");
    if (err) err.textContent = "";
    try {
      await handler(new FormData(form));
    } catch (error) {
      if (err) err.textContent = error.message;
      else errorView(error);
    } finally {
      if (submit) submit.disabled = false;
    }
  };
}
async function boot() {
  try {
    const session = await repository.session();
    state.user = session.user;
    state.qa = session.qa_mode;
    state.authMode = session.auth_mode;
    if (!state.user) {
      if (state.authMode === "entra") corporateLoginScreen();
      else loginScreen(session);
      return;
    }
    await refresh();
  } catch (error) {
    $("#app").innerHTML =
      `<main class="loading-screen"><h1>Não foi possível abrir a agenda</h1><p class="notice">${esc(error.message)}</p>${btn("retry", "Tentar novamente")}</main>`;
  }
}
function corporateLoginScreen() {
  const failed = new URLSearchParams(location.search).has("login_error");
  $("#app").innerHTML =
    `<main class="login-shell"><section class="login-story"><div class="aviva-brand"><img src="/static/assets/aviva-logo.png" alt="Aviva" width="427" height="200"></div><div class="brand-caption">Costa do Sauípe · Rio Quente</div><div class="login-copy"><div class="eyebrow">COMERCIAL MICE & OPERAÇÃO</div><h1>Um espaço para<br>cada encontro.<br><em>Uma agenda<br>para todos.</em></h1><p>Consulte os espaços, organize os bloqueios<br>e acompanhe cada negociação.</p></div><div class="story-footer">CALENDÁRIO DE ESPAÇOS <span>2026 — 2028</span></div></section><section class="login-main"><div class="login-form-wrap"><span class="tiny-label">AGENDA COMPARTILHADA</span><h2>Seu próximo evento<br>começa aqui.</h2><p class="muted">Entre com sua conta corporativa.</p>${failed ? '<p class="notice" role="alert">Não foi possível concluir o acesso. Confirme com a equipe responsável se sua conta está autorizada.</p>' : ""}<a class="btn primary login-submit" href="/api/entra/login">Entrar com Microsoft</a></div><footer>Calendário provisório de salas <span>2026 · 2027 · 2028</span></footer></section></main>`;
}
function loginScreen(session) {
  const setup = session.setup_required;
  $("#app").innerHTML =
    `<main class="login-shell"><section class="login-story"><div class="aviva-brand"><img src="/static/assets/aviva-logo.png" alt="Aviva" width="427" height="200"></div><div class="brand-caption">Costa do Sauípe · Rio Quente</div><div class="login-copy"><div class="eyebrow">COMERCIAL MICE & OPERAÇÃO</div><h1>Um espaço para<br>cada encontro.<br><em>Uma agenda<br>para todos.</em></h1><p>Consulte os espaços, organize os bloqueios<br>e acompanhe cada negociação.</p></div><div class="story-footer">CALENDÁRIO DE ESPAÇOS <span>2026 — 2028</span></div></section><section class="login-main"><div class="login-form-wrap"><span class="tiny-label">AGENDA COMPARTILHADA</span><h2>${setup ? "Vamos preparar<br>seu primeiro acesso." : "Seu próximo evento<br>começa aqui."}</h2><p class="muted">${setup ? "Crie sua conta individual para administrar este ambiente." : "Entre com sua conta individual."}</p><form id="login-form">${setup ? '<label>Seu nome<input name="name" autocomplete="name" required maxlength="120"></label><label>Equipe<select name="team_id"><option value="commercial">Comercial MICE</option><option value="operations">Operacional</option></select></label>' : ""}<label>Usuário<input name="username" autocomplete="username" required minlength="3" maxlength="64" placeholder="Usuário ou e-mail cadastrado" aria-describedby="username-help" autofocus></label><p id="username-help" class="form-help">${setup ? "Defina seu usuário sem espaços. Você pode usar seu e-mail." : "Informe o usuário definido no cadastro, que pode ser seu e-mail. O nome completo não é o login."}</p>${passwordField("Senha", "password", setup ? "new-password" : "current-password", setup ? 15 : 0, setup ? 128 : 256)}<p class="form-help">Dica de senha: novas senhas devem ter de 15 a 128 caracteres.</p><div class="form-error" role="alert"></div><button class="btn primary login-submit" type="submit" ${setup && !session.local_setup_allowed ? "disabled" : ""}>${setup ? "Criar primeiro acesso" : "Entrar na agenda"}</button></form>${setup ? '<div class="notice">A primeira conta administra cadastros, acessos e a fila. Cada equipe continua editando apenas seus próprios bloqueios. Use uma senha de 15 a 128 caracteres.</div>' : '<p class="local-note">Use seu usuário e sua senha cadastrados para acessar a agenda.</p>'}</div><footer>Calendário provisório de salas <span>2026 · 2027 · 2028</span></footer></section></main>`;
  bindForm("#login-form", async (fields) => {
    const data = Object.fromEntries(fields);
    const result = setup
      ? await request("/setup", { method: "POST", body: data })
      : await repository.login(data);
    state.user = result.user;
    state.view = "calendar";
    state.status = "";
    state.search = "";
    state.resort = "all";
    await refresh();
  });
}
async function refresh(quiet = false) {
  if (!["all", "cs", "rq"].includes(state.resort)) state.resort = "all";
  if (!state.user || loading) return;
  if (
    quiet &&
    ($("#editor").open ||
      ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName))
  )
    return;
  loading = true;
  const serial = ++refreshNumber;
  try {
    const catalog = await repository.catalog();
    state.catalog = catalog.configurations;
    state.resources = catalog.resources;
    state.sourceCount = catalog.source_count;
    if (state.view === "calendar") {
      const data = await request(`/calendar?${queryString()}`);
      state.calendar = data.configurations;
      state.days = data.days;
      state.bookings = data.bookings;
      state.occupying = data.occupying_bookings;
    } else if (["queue", "reports"].includes(state.view)) {
      state.bookings = (
        await request(`/bookings?${queryString(true)}`)
      ).bookings;
    } else if (state.view === "users") {
      state.users = (await request("/users")).users;
    }
    state.online = true;
    state.lastSync = new Date().toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    if (serial === refreshNumber) render();
  } catch (error) {
    state.online = false;
    if (!quiet) errorView(error);
    const el = $("#sync");
    if (el) {
      el.className = "sync-state offline";
      el.textContent = "Sem conexão · dados podem estar desatualizados";
    }
  } finally {
    loading = false;
  }
}
function render() {
  const titles = {
    calendar: [
      "Calendário de espaços",
      "Veja a ocupação e acompanhe as solicitações, dia a dia.",
    ],
    queue: [
      "Solicitações & fila",
      "Ordem de entrada, com prioridade concedida manualmente.",
    ],
    catalog: [
      "Salas & espaços",
      "Consulte os espaços e valide suas composições.",
    ],
    reports: [
      "Relatórios",
      "Consulte e compartilhe os bloqueios do período selecionado.",
    ],
    users: [
      "Pessoas & acessos",
      "Contas individuais, equipes e responsabilidades bem definidas.",
    ],
  };
  const [title, subtitle] = titles[state.view];
  const unvalidated = state.catalog.filter((c) => !c.validated).length;
  $("#app").innerHTML =
    `<div class="agenda-shell">${sidebar()}<div class="agenda-main"><header class="agenda-top"><span>Espaços de eventos <span aria-hidden="true">/</span> ${title}</span><div><span id="sync" class="sync-state ${state.online ? "" : "offline"}">${state.online ? `Atualizado às ${state.lastSync}` : "Sem conexão · consulta desatualizada"}</span> <button class="icon-btn" data-action="refresh" aria-label="Atualizar agenda">↻</button><button class="icon-btn" data-action="logout" aria-label="Sair">↗</button></div></header><main class="agenda-content">${state.qa ? '<div class="notice qa-banner">AMBIENTE DE TESTES · Dados e validações fictícios, isolados da base operacional.</div>' : ""}<div class="agenda-heading"><div><div class="agenda-eyebrow">COSTA DO SAUÍPE & RIO QUENTE</div><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-actions">${state.view === "users" ? btn("new-user", "Adicionar pessoa", "", true) : state.view === "catalog" ? `${state.user.can_catalog ? btn("classify-selected", "Classificar seleção") + btn("add-resource", "Novo recurso físico") : ""}` : btn("availability", "Consultar disponibilidade") + btn("new-booking", "＋ Nova solicitação", "", true)}</div></div>${state.view === "calendar" ? `<section class="agenda-stats"><article class="agenda-stat"><small>Espaços e configurações<br>Catálogo compartilhado</small><strong>${state.catalog.length}</strong></article><article class="agenda-stat"><small>Solicitações no período<br>Conforme os filtros</small><strong>${state.bookings.length}</strong></article></section>` : ""}${unvalidated && state.view === "calendar" ? `<div class="notice">${unvalidated} configurações aguardam validação física. A área hachurada significa “a validar”; dias vazios não garantem disponibilidade.</div>` : ""}${state.view === "calendar" ? calendarView() : state.view === "queue" ? `<section class="agenda-card">${toolbar(false)}<div class="calendar-caption"><strong>Solicitações por ordem de entrada</strong><span>Sem promoção ou expiração automática</span></div>${bookingList(state.bookings)}</section>` : state.view === "catalog" ? catalogView() : state.view === "reports" ? reportsView() : usersView()}<footer class="agenda-footer"><span>Calendário compartilhado · bloqueios por dia inteiro</span><span>2026 — 2028 · ${esc(state.user.name)}</span></footer></main></div></div>`;
  bindMain();
}
function bindMain() {
  for (const [id, key] of [
    ["month", "month"],
    ["year", "year"],
    ["resort", "resort"],
    ["status", "status"],
  ]) {
    const el = $(`#${id}`);
    if (el)
      el.onchange = async () => {
        state[key] = ["month", "year"].includes(key)
          ? Number(el.value)
          : el.value;
        await refresh();
      };
  }
  const search = $("#search");
  if (search) {
    let timer;
    search.oninput = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        state.search = search.value;
        const pos = search.selectionStart;
        await refresh();
        const next = $("#search");
        next?.focus();
        if (next) next.setSelectionRange(pos, pos);
      }, 450);
    };
  }
}
function spaceOptions(resort, selected = "") {
  return catalogSpaceOptions(state.catalog, resort, selected);
}
function allocMarkup(a) {
  const c = state.catalog.find((item) => item.id === a.configuration_id);
  const resort = c
    ? allocationResort(c)
    : a.resort_id || (["cs", "rq"].includes(state.resort) ? state.resort : "");
  const selected = JSON.stringify([...(a.resources || [])].sort());
  const unassigned = state.catalog.some(
    (item) => allocationResort(item) === "unassigned",
  );
  return `<div class="allocation-row" data-allocation><label class="allocation-resort">Empreendimento<select data-resort-filter required>${option("", "Selecione o empreendimento", resort)}${Object.entries(
    resorts,
  )
    .map(([id, name]) => option(id, name, resort))
    .join(
      "",
    )}${unassigned ? option("unassigned", "Sem empreendimento definido", resort) : ""}</select></label><label class="allocation-space">Espaço<select data-field="configuration_id" required ${resort ? "" : "disabled"}>${spaceOptions(resort, a.configuration_id)}</select></label><label>Fase<select data-field="phase">${Object.entries(
    phases,
  )
    .map(([k, v]) => option(k, v, a.phase || "event"))
    .join(
      "",
    )}</select></label><label>Início<input data-field="start_date" type="date" value="${esc(a.start_date)}" min="2026-01-01" max="2028-12-31" required></label><label>Último dia<input data-field="end_date" type="date" value="${esc(a.end_date)}" min="2026-01-01" max="2028-12-31" required></label>${btn("remove-allocation", "×", 'aria-label="Remover período"')}<label class="composition">${c?.validated ? "Composição homologada" : "Composição pendente de validação"}<select data-field="resources" ${c?.validated ? "" : "disabled"}>${!c?.validated ? option("[]", "Composição física a validar", "[]") : c.options.map((o) => option(JSON.stringify(o), o.map(resourceName).join(" + "), selected)).join("")}</select></label></div>`;
}
function readAllocations() {
  return [...document.querySelectorAll("[data-allocation]")].map((row) =>
    Object.fromEntries(
      [...row.querySelectorAll("[data-field]")].map((el) => [
        el.dataset.field,
        el.dataset.field === "resources"
          ? JSON.parse(el.value || "[]")
          : el.value,
      ]),
    ),
  );
}
function wireAllocations() {
  document.querySelectorAll("[data-allocation]").forEach((row) => {
    const resort = row.querySelector("[data-resort-filter]");
    const space = row.querySelector('[data-field="configuration_id"]');
    const updateComposition = () => {
      const c = state.catalog.find((item) => item.id === space.value);
      const field = row.querySelector('[data-field="resources"]');
      field.disabled = !c?.validated;
      field.innerHTML = c?.validated
        ? c.options
            .map((o) =>
              option(
                JSON.stringify(o),
                o.map(resourceName).join(" + "),
                JSON.stringify(c.options[0]),
              ),
            )
            .join("")
        : option("[]", "Composição física a validar", "[]");
      row.querySelector(".composition").firstChild.textContent = c?.validated
        ? "Composição homologada"
        : "Composição pendente de validação";
    };
    resort.onchange = () => {
      space.innerHTML = spaceOptions(resort.value);
      space.disabled = !resort.value;
      updateComposition();
    };
    space.onchange = updateComposition;
  });
}
function bookingForm(booking = null, configId = "", dateValue = "") {
  const dates = range();
  const allocations = booking?.allocations || [
    {
      configuration_id: configId,
      phase: "event",
      start_date: dateValue || dates.from,
      end_date: dateValue || dates.from,
      resources: state.catalog.find((c) => c.id === configId)?.options[0] || [],
    },
  ];
  const states =
    !booking || ["pending", "waiting"].includes(booking.status)
      ? ["pending", "waiting"]
      : booking.status === "option"
        ? [
            "option",
            ...(state.user.can_schedule ? ["confirmed"] : []),
            "waiting",
            "pending",
          ]
        : ["confirmed", "waiting", "pending"];
  if (
    !modal(
      booking ? "Editar solicitação" : "Nova solicitação",
      `<form id="booking-form"><div class="form-grid"><label>Evento / motivo<input name="title" maxlength="180" required value="${esc(booking?.title || "")}" autofocus></label><label>Responsável<input name="responsible" maxlength="120" required value="${esc(booking?.responsible || state.user.name)}"></label><label>Situação<select name="status">${states.map((s) => option(s, statusNames[s], booking?.status || "pending")).join("")}</select></label><label>Equipe proprietária<input value="${state.user.team_id === "commercial" ? "Comercial MICE" : "Operacional"}" disabled></label></div><div class="notice">Todos os dias informados são incluídos. Solicitações pendentes e em espera não bloqueiam o espaço. O responsável pela fila pode confirmar a reserva, bloqueando a configuração escolhida em todos os dias informados. Composições físicas ainda não validadas exigem atenção especial.</div><div id="allocations">${allocations.map(allocMarkup).join("")}</div>${btn("add-allocation", "＋ Adicionar espaço ou fase")}<label class="full-width">Observações<textarea name="notes" maxlength="4000">${esc(booking?.notes || "")}</textarea></label>${state.user.can_schedule && (!booking || ["pending", "waiting"].includes(booking.status)) ? '<label class="checkbox-line"><input type="checkbox" name="confirm_reservation">Confirmar reserva e bloquear o espaço neste período</label>' : ""}<div class="form-help">${booking ? "Alterar datas/espaços de uma solicitação em espera reposiciona sua entrada na fila." : "A equipe e a autoria são registradas pelo servidor."}</div><div class="form-error" role="alert"></div></form>`,
      `${btn("close", "Cancelar")}<button class="btn primary" type="submit" form="booking-form">Salvar solicitação</button>`,
      true,
    )
  )
    return;
  wireAllocations();
  let key = crypto.randomUUID();
  $("#booking-form").oninput = () => {
    key = crypto.randomUUID();
    modalDirty = true;
  };
  bindForm("#booking-form", async (fields) => {
    const payload = {
      ...Object.fromEntries(fields),
      allocations: readAllocations(),
      ...(booking ? { version: booking.version } : {}),
    };
    if (fields.get("confirm_reservation") === "on")
      payload.status = "confirmed";
    delete payload.confirm_reservation;
    await repository.save(payload, booking?.id, key);
    closeModal(true);
    await refresh();
    toast(
      payload.status === "confirmed"
        ? "Reserva confirmada; o espaço está bloqueado no período."
        : payload.status === "pending"
          ? "Solicitação pendente registrada; a sala ainda não está bloqueada."
          : "Solicitação salva na base compartilhada.",
    );
  });
}
async function bookingDetail(id) {
  const { booking: b, history } = await request(`/bookings/${id}`);
  const own = b.team_id === state.user.team_id;
  const actions = `${own && b.status !== "cancelled" ? btn("edit-booking", "Editar", `data-id="${id}"`) + btn("cancel-booking", "Cancelar solicitação", `data-id="${id}" data-version="${b.version}"`) : ""}${state.user.can_schedule && b.status === "waiting" ? btn("promote", "Conceder opção prioritária", `data-id="${id}" data-version="${b.version}"`) : ""}${state.user.can_schedule && ["pending", "waiting", "option"].includes(b.status) ? btn("confirm-booking", "Confirmar reserva", `data-id="${id}" data-version="${b.version}"`, true) : ""}`;
  modal(
    esc(b.title),
    `<dl class="detail-grid"><div><dt>Situação</dt><dd>${pill(b.status)}</dd></div><div><dt>Equipe / responsável</dt><dd>${esc(b.team_name)} · ${esc(b.responsible)}</dd></div><div><dt>Entrada na fila</dt><dd>#${b.queue_number} · ${esc(b.creator_name)}</dd></div><div><dt>Observações</dt><dd>${esc(b.notes) || "—"}</dd></div></dl><div class="notice neutral-notice">${b.allocations.map((a) => `${esc(a.space_name)} · ${phases[a.phase]}<br>${fmt(a.start_date)} a ${fmt(a.end_date)} · ${esc(resortName(a.resort_id))}${a.resources.length ? `<br>${a.resources.map(resourceName).map(esc).join(" + ")}` : ""}`).join("<hr>")}</div><h3>Histórico da solicitação</h3>${historyMarkup(history)}`,
    actions,
    true,
  );
}
function cancelForm(id, version) {
  if (
    !modal(
      "Cancelar solicitação",
      `<form id="cancel-form"><p>O cancelamento libera todos os espaços e dias desta solicitação. O histórico será preservado e a fila continuará aguardando promoção manual.</p><label>Motivo do cancelamento<textarea name="reason" required maxlength="600"></textarea></label><div class="form-error" role="alert"></div></form>`,
      `${btn("close", "Voltar")}<button type="submit" form="cancel-form" class="btn primary">Confirmar cancelamento</button>`,
    )
  )
    return;
  bindForm("#cancel-form", async (fields) => {
    await request(`/bookings/${id}/cancel`, {
      method: "POST",
      body: { version, reason: fields.get("reason") },
    });
    closeModal(true);
    await refresh();
    toast("Cancelado; nenhum item em espera foi promovido automaticamente.");
  });
}
function confirmBookingForm(id, version) {
  if (
    !modal(
      "Confirmar reserva",
      `<form id="confirmation-form"><p>Esta confirmação bloqueia todos os espaços e dias da solicitação. Se algum espaço já estiver reservado, nada será confirmado.</p><div class="notice">Para composições ainda não validadas, o bloqueio cobre a configuração escolhida. Sobreposições com outras configurações dependem da validação física pela operação.</div><label class="checkbox-line"><input type="checkbox" name="confirmed" required>Confirmo o bloqueio de todos os espaços e dias desta solicitação.</label><div class="form-error" role="alert"></div></form>`,
      `${btn("close", "Voltar")}<button type="submit" form="confirmation-form" class="btn primary">Confirmar reserva</button>`,
    )
  )
    return;
  bindForm("#confirmation-form", async () => {
    await request(`/bookings/${id}/confirm`, {
      method: "POST",
      body: { version },
    });
    closeModal(true);
    await refresh();
    toast("Reserva confirmada; os espaços foram bloqueados no período.");
  });
}
function historyMarkup(history) {
  const names = {
    create: "Solicitação criada",
    update: "Solicitação alterada",
    cancel: "Solicitação cancelada",
    promote: "Opção prioritária concedida",
    classify: "Empreendimento classificado",
    validate_topology: "Composição validada",
    validate: "Recurso físico validado",
    import: "Catálogo importado",
  };
  return `<div class="history-list">${history.map((h) => `<article><strong>${esc(names[h.action] || h.action)}</strong><small>${esc(h.actor_name || "Carga inicial")} · ${new Date(h.occurred_at).toLocaleString("pt-BR")}</small>${h.note ? `<p>${esc(h.note)}</p>` : ""}</article>`).join("") || "<p>Nenhuma alteração registrada.</p>"}</div>`;
}
function authEventsMarkup(events) {
  const names = {
    login: "Entrada",
    logout: "Saída",
    sso_start: "Início do login corporativo",
    sso_callback: "Retorno do login corporativo",
    access_denied: "Acesso negado",
    access_change: "Acesso alterado",
    password_change: "Senha local alterada",
    identity_link: "Identidade vinculada",
  };
  const results = {
    accepted: "Aceito",
    rejected: "Recusado",
    started: "Iniciado",
    rate_limited: "Limite de tentativas",
  };
  return `<div class="history-list">${events.map((e) => `<article><strong>${esc(names[e.event_type] || e.event_type)} · ${esc(results[e.result] || e.result)}</strong><small>${esc(e.user_name || "Pessoa não identificada")} · ${new Date(e.occurred_at).toLocaleString("pt-BR")}</small>${e.reason ? `<p>${esc(e.reason)}</p>` : ""}${e.request_id ? `<small>Referência: ${esc(e.request_id)}</small>` : ""}</article>`).join("") || "<p>Nenhum evento registrado.</p>"}</div>`;
}
function spaceDetail(id) {
  const c = state.catalog.find((c) => c.id === id);
  const technical = Object.entries(c.technical).filter(
    ([, v]) => v && v !== "-",
  );
  modal(
    esc(c.name),
    `<dl class="detail-grid"><div><dt>Empreendimento</dt><dd>${esc(resortName(c.resort_id))}</dd></div><div><dt>Localização</dt><dd>${esc(c.location) || "Não informada"}</dd></div><div><dt>Fonte</dt><dd>Códigos ${c.source_codes.join(", ")}</dd></div><div><dt>Composição</dt><dd>${c.validated ? c.options.map((o) => o.map(resourceName).map(esc).join(" + ")).join("<br>") : "A validar"}</dd></div></dl><div class="notice">${esc(c.notes).replaceAll("\n", "<br>")}</div>${technical.length ? `<h3>Dados técnicos da fonte</h3><p class="form-help">Valores de referência; campos ausentes não foram preenchidos.</p><dl class="detail-grid">${technical.map(([k, v]) => `<div><dt>${esc({ medidas: "Medidas", area_m2: "Área (m²)", pe_direito: "Pé-direito", auditorio: "Auditório", escolar_espinha: "Escolar / Espinha", u: "U", banquete: "Banquete" }[k] || k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>` : ""}`,
    `${btn("new-for-space", "Nova solicitação", `data-id="${id}"`, true)}${state.user.can_catalog ? btn("topology", "Validar composição", `data-id="${id}"`) : ""}`,
    true,
  );
}
function dayDetail(id, d) {
  const c = state.calendar.find((c) => c.id === id);
  const cell = c.days[d];
  const ids = [...new Set([...cell.bookings, ...cell.requests])];
  const data = new Map(
    [...state.occupying, ...state.bookings].map((b) => [b.id, b]),
  );
  modal(
    `${esc(c.name)} · ${fmt(d)}`,
    `${cell.state === "unvalidated" ? '<div class="notice">A composição física ainda não foi validada. Uma nova solicitação ficará pendente, sem garantia de ocupação.</div>' : ""}${cell.restricted ? '<div class="notice">Existe ocupação com detalhes restritos ao seu acesso.</div>' : ""}${bookingList(ids.map((i) => data.get(i)).filter(Boolean))}`,
    btn(
      "new-for-day",
      "Nova solicitação",
      `data-id="${id}" data-day="${d}"`,
      true,
    ),
    true,
  );
}
function classifySelected() {
  const ids = [...document.querySelectorAll("[data-select]:checked")].map(
    (e) => e.dataset.select,
  );
  if (!ids.length) {
    toast("Selecione os espaços na tabela.", true);
    return;
  }
  modal(
    "Classificar empreendimento",
    `<form id="classification-form"><p>Esta alteração mantém os mesmos espaços, bloqueios e histórico.</p><div class="notice neutral-notice">${ids.map((id) => esc(state.catalog.find((c) => c.id === id).name)).join("<br>")}</div><label>Empreendimento<select name="resort_id" required><option value="" disabled selected>Selecione o empreendimento</option>${[
      "cs",
      "rq",
    ]
      .filter((s) => state.user.scopes.includes(s))
      .map((s) => option(s, resorts[s], ""))
      .join(
        "",
      )}</select></label><label>Hotel, ala ou localização<input name="location" maxlength="150"></label><label>Referência / motivo da classificação<textarea name="reason" required maxlength="500"></textarea></label><div class="form-error"></div></form>`,
    `${btn("close", "Cancelar")}<button class="btn primary" form="classification-form" type="submit">Confirmar classificação</button>`,
  );
  bindForm("#classification-form", async (fields) => {
    const body = Object.fromEntries(fields);
    body.changes = ids.map((id) => ({
      id,
      version: state.catalog.find((c) => c.id === id).version,
    }));
    await request("/catalog/classify", { method: "POST", body });
    closeModal(true);
    await refresh();
    toast("Classificação atualizada; os registros foram preservados.");
  });
}
function optionEditor(selected = [], n = 1) {
  return `<fieldset class="resource-option"><legend>Conjunto permitido ${n}</legend>${state.resources.map((r) => `<label><input type="checkbox" value="${r.id}" ${selected.includes(r.id) ? "checked" : ""}>${esc(r.name)} <small>· ${esc(resortName(r.resort_id))}</small></label>`).join("")}</fieldset>`;
}
function topologyForm(id) {
  const c = state.catalog.find((c) => c.id === id);
  const sets = c.options.length
    ? c.options
    : c.suggested_options.length
      ? c.suggested_options
      : [[]];
  modal(
    `Validar composição · ${esc(c.name)}`,
    `<form id="topology-form"><div class="notice">As sugestões da fonte não são homologação. Confirme os recursos físicos com a operação antes de salvar. Opções diferentes devem representar conjuntos realmente permitidos.${c.module_count ? ` Cada conjunto exige ${c.module_count} recursos.` : ""}</div><div id="physical-options">${sets.map((s, i) => optionEditor(s, i + 1)).join("")}</div>${c.kind === "espaco_sem_composicao_explicita" ? "" : btn("add-physical-option", "＋ Outro conjunto permitido")}<label>Referência da validação<textarea name="reason" required maxlength="600" placeholder="Quem confirmou, data e documento ou orientação utilizada"></textarea></label><label class="checkbox-line"><input type="checkbox" name="attested" required>Confirmo que a composição física foi verificada.</label><div class="form-error"></div></form>`,
    `${btn("close", "Cancelar")}<button class="btn primary" form="topology-form" type="submit">Salvar validação</button>`,
    true,
  );
  bindForm("#topology-form", async (fields) => {
    const options = [...document.querySelectorAll(".resource-option")].map(
      (s) => [...s.querySelectorAll("input:checked")].map((i) => i.value),
    );
    await request(`/catalog/${id}/topology`, {
      method: "POST",
      body: {
        version: c.version,
        options,
        attested: fields.get("attested") === "on",
        reason: fields.get("reason"),
      },
    });
    closeModal(true);
    await refresh();
    toast(
      "Composição homologada. Solicitações pendentes não foram promovidas automaticamente.",
    );
  });
}
function resourceForm() {
  modal(
    "Cadastrar recurso físico",
    `<form id="resource-form"><div class="notice">Use apenas o nome identificado pela operação. Não crie uma nova sala para cada variante de climatização ou fase.</div><label>Nome oficial do módulo / recurso<input name="name" required maxlength="200"></label><label>Empreendimento<select name="resort_id" required><option value="" disabled selected>Selecione o empreendimento</option>${Object.entries(
      resorts,
    )
      .filter(([k]) => state.user.scopes.includes(k))
      .map(([k, v]) => option(k, v, ""))
      .join(
        "",
      )}</select></label><label>Localização<input name="location" maxlength="150"></label><label>Referência da identificação<textarea name="evidence" required maxlength="600"></textarea></label><div class="form-error"></div></form>`,
    `${btn("close", "Cancelar")}<button type="submit" form="resource-form" class="btn primary">Cadastrar recurso</button>`,
  );
  bindForm("#resource-form", async (f) => {
    const body = Object.fromEntries(f);
    await request("/resources", { method: "POST", body });
    closeModal(true);
    await refresh();
    toast("Recurso cadastrado para revisão das composições.");
  });
}
function availabilityForm() {
  const r = range();
  modal(
    "Consultar disponibilidade",
    `<form id="availability-form"><div class="form-grid"><label>Primeiro dia<input name="from" type="date" min="2026-01-01" max="2028-12-31" value="${r.from}" required></label><label>Último dia<input name="to" type="date" min="2026-01-01" max="2028-12-31" value="${r.to}" required></label></div><p class="form-help">A consulta separa solicitações sem bloqueio da ocupação efetiva. A fila é verificada ao conceder uma opção.</p><div class="form-error"></div><button class="btn primary" type="submit">Consultar período</button></form><div id="availability-results" class="availability-results"></div>`,
    "",
    true,
  );
  bindForm("#availability-form", async (fields) => {
    const q = new URLSearchParams({
      ...Object.fromEntries(fields),
      resort: state.resort,
    });
    const { results } = await request(`/availability?${q}`);
    $("#availability-results").innerHTML = results
      .map((result) => {
        const requests = [];
        if (result.pending_count)
          requests.push(
            `${result.pending_count} solicitaç${result.pending_count === 1 ? "ão" : "ões"} pendente${result.pending_count === 1 ? "" : "s"}`,
          );
        if (result.waiting_count)
          requests.push(`${result.waiting_count} em espera`);
        const status =
          result.available === null
            ? "Composição a validar"
            : result.available
              ? "Sem ocupação efetiva"
              : "Ocupado no período";
        const periodNames = {
          pending: "Solicitação pendente",
          waiting: "Em espera",
          option: "Opção prioritária",
          confirmed: "Reserva confirmada",
        };
        const periods = (result.periods || [])
          .map(
            (p) =>
              `<small class="availability-period ${["option", "confirmed"].includes(p.status) ? "occupied-period" : ""}">${esc(periodNames[p.status] || p.status)}${p.related ? " em configuração compartilhada" : ""}: ${fmt(p.start_date)}${p.start_date === p.end_date ? "" : ` a ${fmt(p.end_date)}`} · ${esc(phases[p.phase] || p.phase)}</small>`,
          )
          .join("");
        return `<div class="availability-item"><span>${esc(result.name)}${requests.length ? `<small class="availability-request">${esc(requests.join(" · "))} · ainda não bloqueia a sala</small>` : ""}${periods}</span><span class="status-pill ${result.available ? "status-option" : ""}">${status}</span></div>`;
      })
      .join("");
    modalDirty = false;
  });
}
function deleteUserForm(user) {
  if (!user) return;
  modal(
    "Excluir pessoa",
    `<p><strong>${esc(user.name)}</strong> (${esc(user.username)}) perderá o acesso imediatamente e sairá da lista de pessoas.</p><p>As solicitações e o histórico de auditoria serão preservados. Esta ação não pode ser desfeita.</p>`,
    `${btn("close", "Voltar")}<button type="button" class="btn danger" data-action="confirm-delete-user" data-id="${user.id}">Confirmar exclusão</button>`,
  );
}
function userForm(user = null) {
  const scope = user?.scopes || ["cs", "rq"];
  modal(
    user ? "Ajustar acesso" : "Adicionar pessoa",
    `<form id="user-form">${!user ? '<div class="form-grid"><label>Nome<input name="name" required maxlength="120"></label><label>Usuário<input name="username" required minlength="3" maxlength="64"></label>' + (state.authMode === "entra" ? '<label>Object ID no Microsoft Entra ID<input name="entra_object_id" required placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"></label>' : passwordField("Senha inicial individual", "password", "new-password", 15, 128)) + '<label>Equipe<select name="team_id"><option value="commercial">Comercial MICE</option><option value="operations">Operacional</option></select></label></div>' : `<p class="review-name">${esc(user.name)}</p><label class="checkbox-line"><input type="checkbox" name="active" ${user.active ? "checked" : ""}>Conta ativa</label>`}<h3>Escopo de consulta</h3>${Object.entries(
      resorts,
    )
      .map(
        ([s, label]) =>
          `<label class="checkbox-line"><input type="checkbox" name="scopes" value="${s}" ${scope.includes(s) ? "checked" : ""}>${label}</label>`,
      )
      .join(
        "",
      )}<h3>Responsabilidades adicionais</h3><div class="permission-grid">${[
      ["can_catalog", "Revisar cadastros e composições"],
      ["can_schedule", "Conceder prioridade na fila"],
    ]
      .map(
        ([k, l]) =>
          `<label class="checkbox-line"><input type="checkbox" name="${k}" ${user?.[k] ? "checked" : ""}>${l}</label>`,
      )
      .join(
        "",
      )}</div><div class="access-admin-choice"><label class="checkbox-line"><input type="checkbox" name="can_manage_users" ${user?.can_manage_users ? "checked" : ""}>Administrador de acessos</label><p>Pode adicionar pessoas, conceder ou revogar acessos e excluir membros. Este papel também pode designar outros administradores.</p></div><div class="notice">A responsabilidade pela fila permite conceder a opção prioritária a outra equipe. Ela não permite editar o evento nem cancelar o bloqueio dessa equipe.</div><div class="form-error"></div></form>`,
    `${user ? `<button type="button" class="btn danger delete-user-modal" data-action="delete-user" data-id="${user.id}">Excluir pessoa</button>` : ""}${btn("close", "Cancelar")}<button class="btn primary" form="user-form" type="submit">Salvar acesso</button>`,
    true,
  );
  bindForm("#user-form", async (f) => {
    const body = { ...Object.fromEntries(f), scopes: f.getAll("scopes") };
    for (const k of [
      "can_catalog",
      "can_schedule",
      "can_manage_users",
      "active",
    ])
      body[k] = f.get(k) === "on";
    if (user) body.version = user.version;
    await request(user ? `/users/${user.id}` : "/users", {
      method: user ? "PUT" : "POST",
      body,
    });
    closeModal(true);
    await refresh();
    toast("Acesso salvo.");
  });
}
function passwordForm() {
  modal(
    "Alterar minha senha",
    `<form id="password-form">${passwordField("Senha atual", "current_password", "current-password", 0, 256)}${passwordField("Nova senha", "password", "new-password", 15, 128)}<p class="form-help">A nova senha deve ter de 15 a 128 caracteres.</p><div class="form-error"></div></form>`,
    `${btn("close", "Cancelar")}<button type="submit" form="password-form" class="btn primary">Alterar senha</button>`,
  );
  bindForm("#password-form", async (f) => {
    await request("/password", { method: "POST", body: Object.fromEntries(f) });
    closeModal(true);
    toast("Senha alterada. Outras sessões precisarão entrar novamente.");
  });
}
function printReport() {
  const rows = state.bookings.flatMap((b) =>
    (b.matched_allocations || b.allocations).map(
      (a) =>
        `<tr><td>${esc(b.title)}</td><td>${esc(resortName(a.resort_id))}</td><td>${esc(a.space_name)}</td><td>${phases[a.phase]}</td><td>${fmt(a.start_date)} — ${fmt(a.end_date)}</td><td>${statusNames[b.status]}</td><td>${esc(b.team_name)} / ${esc(b.responsible)}</td></tr>`,
    ),
  );
  $("#print-area").innerHTML =
    `<header>Costa do Sauípe & Rio Quente · Agenda de espaços</header><h1>Relatório de bloqueios</h1><p class="report-meta">${fmt(state.reportFrom)} a ${fmt(state.reportTo)} · ${state.resort === "all" ? "Todos os empreendimentos" : resortName(state.resort)} · ${state.status ? statusNames[state.status] : "Todas as situações"}${state.search ? ` · Pesquisa: ${esc(state.search)}` : ""}</p><p>${rows.length} períodos encontrados.</p><table><thead><tr>${["Evento", "Empreendimento", "Espaço", "Fase", "Período", "Situação", "Equipe / responsável"].map((t) => `<th>${t}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
  window.print();
}
async function importForm() {
  modal(
    "Revisar importação da lista",
    `<p>A importação valida a lista inteira antes de gravar e preserva o cadastro já revisado.</p><input id="catalog-file" type="file" accept=".json,application/json"><div id="import-preview"></div>`,
  );
  $("#catalog-file").onchange = async (e) => {
    try {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 3 * 1024 * 1024)
        throw new Error("O arquivo deve ter até 3 MB.");
      const catalog = JSON.parse(await file.text());
      const result = await request("/catalog/import", {
        method: "POST",
        body: { catalog },
      });
      $("#import-preview").innerHTML =
        `<div class="notice neutral-notice">${result.items} itens · ${result.new} novos · 2 serviços mantidos apenas como referência.</div>${btn("confirm-import", result.already_imported ? "Catálogo já importado" : "Confirmar carga", result.already_imported ? "disabled" : "", true)}`;
      $("#import-preview button").onclick = async () => {
        try {
          await request("/catalog/import", {
            method: "POST",
            body: { catalog, confirm: true },
          });
          closeModal(true);
          await refresh();
          toast("Catálogo importado sem duplicação.");
        } catch (error) {
          errorView(error);
        }
      };
    } catch (error) {
      errorView(error);
    }
  };
}
async function handleAction(target) {
  const { action, id } = target.dataset;
  switch (action) {
    case "toggle-password": {
      const input = document.getElementById(
        target.getAttribute("aria-controls"),
      );
      if (!input) return;
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      target.textContent = visible ? "Ocultar" : "Mostrar";
      target.setAttribute(
        "aria-label",
        visible ? "Ocultar senha" : "Mostrar senha",
      );
      target.setAttribute("aria-pressed", String(visible));
      return;
    }
    case "retry":
      return boot();
    case "close":
      return closeModal();
    case "refresh":
      return refresh();
    case "logout":
      if ($("#editor").open && !closeModal()) return;
      await repository.logout();
      state.user = null;
      return boot();
    case "navigate":
      if ($("#editor").open && !closeModal()) return;
      state.view = target.dataset.view;
      state.status = "";
      state.search = "";
      return refresh();
    case "mode":
      state.mode = target.dataset.mode;
      return render();
    case "prev-month":
    case "next-month": {
      const next = new Date(
        state.year,
        state.month + (action === "next-month" ? 1 : -1),
        1,
      );
      if (next.getFullYear() < 2026 || next.getFullYear() > 2028) return;
      state.year = next.getFullYear();
      state.month = next.getMonth();
      return refresh();
    }
    case "new-booking":
      return bookingForm();
    case "new-for-space":
      return bookingForm(null, id);
    case "new-for-day":
      return bookingForm(null, id, target.dataset.day);
    case "booking-detail":
      return bookingDetail(id);
    case "edit-booking": {
      const { booking } = await request(`/bookings/${id}`);
      return bookingForm(booking);
    }
    case "cancel-booking":
      return cancelForm(id, Number(target.dataset.version));
    case "confirm-booking":
      return confirmBookingForm(id, Number(target.dataset.version));
    case "promote":
      target.disabled = true;
      await request(`/bookings/${id}/promote`, {
        method: "POST",
        body: { version: Number(target.dataset.version) },
      });
      closeModal(true);
      await refresh();
      return toast("Opção prioritária concedida para todo o conjunto.");
    case "space-detail":
      return spaceDetail(id);
    case "day":
      return dayDetail(id, target.dataset.day);
    case "add-allocation": {
      const first = readAllocations()[0] || {};
      $("#allocations").insertAdjacentHTML(
        "beforeend",
        allocMarkup({
          start_date: first.start_date || range().from,
          end_date: first.end_date || range().from,
        }),
      );
      wireAllocations();
      $("#booking-form").dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    case "remove-allocation":
      if (document.querySelectorAll("[data-allocation]").length <= 1) {
        toast("Mantenha ao menos um período.", true);
        return;
      }
      target.closest("[data-allocation]").remove();
      $("#booking-form").dispatchEvent(new Event("input", { bubbles: true }));
      return;
    case "classify-selected":
      return classifySelected();
    case "topology":
      return topologyForm(id);
    case "add-physical-option":
      $("#physical-options").insertAdjacentHTML(
        "beforeend",
        optionEditor(
          [],
          document.querySelectorAll(".resource-option").length + 1,
        ),
      );
      modalDirty = true;
      return;
    case "add-resource":
      return resourceForm();
    case "availability":
      return availabilityForm();
    case "new-user":
      return userForm();
    case "edit-user":
      return userForm(state.users.find((user) => user.id === id));
    case "delete-user":
      return deleteUserForm(state.users.find((user) => user.id === id));
    case "confirm-delete-user": {
      const user = state.users.find((person) => person.id === id);
      if (!user) return;
      target.disabled = true;
      await request(`/users/${id}`, {
        method: "DELETE",
        body: { version: user.version },
      });
      closeModal(true);
      await refresh();
      return toast("Pessoa excluída e acesso encerrado.");
    }
    case "password":
      return passwordForm();
    case "report-apply":
      state.reportFrom = $("#report-from").value;
      state.reportTo = $("#report-to").value;
      return refresh();
    case "csv": {
      const response = await fetch(`/api/reports.csv?${queryString()}`, {
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error((await response.json()).error);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "calendario-salas.csv";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return;
    }
    case "print":
      return printReport();
    case "import":
      return importForm();
    case "catalog-history": {
      const data = await request("/audit/catalog");
      return modal(
        "Histórico cadastral",
        historyMarkup(data.history),
        "",
        true,
      );
    }
    case "auth-history": {
      const data = await request("/audit/auth");
      return modal(
        "Histórico de acessos",
        authEventsMarkup(data.events),
        "",
        true,
      );
    }
    case "sources": {
      const data = await request("/catalog/sources");
      return modal(
        "125 itens da fonte",
        `<div class="notice">Linhas de origem não equivalem a espaços físicos independentes. Serviços não são reserváveis.</div><div class="catalog-scroll"><table class="catalog-table"><thead><tr><th>Código</th><th>Nome original</th><th>Tratamento</th></tr></thead><tbody>${data.items.map((item) => `<tr><td>${item.code}</td><td>${esc(item.name)}</td><td>${item.kind === "servico" ? "Serviço · fora da agenda" : item.kind === "variante_utilizacao_arena" ? "Variante de utilização" : item.kind === "combinacao_ou_configuracao" ? "Configuração" : "Espaço candidato"}</td></tr>`).join("")}</tbody></table></div>`,
        "",
        true,
      );
    }
    default:
      return;
  }
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target || target.disabled) return;
  try {
    await handleAction(target);
  } catch (error) {
    errorView(error);
  } finally {
    if (target.isConnected) target.disabled = false;
  }
});
window.addEventListener("beforeunload", (e) => {
  if (modalDirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
window.addEventListener("focus", () => refresh(true));
setInterval(() => refresh(true), 20000);
await boot();
