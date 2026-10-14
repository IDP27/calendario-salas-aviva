// Read-only markup for the application's main screens.
import {
  btn,
  esc,
  fmt,
  months,
  normalized,
  option,
  pill,
  resorts,
  statusNames,
} from "./calendar-model.js";

export function createViews(state, resortName) {
  function sidebar() {
    const nav = [
      ["calendar", "Calendário"],
      ["queue", "Solicitações & fila"],
      ["catalog", "Salas & espaços"],
      ["reports", "Relatórios"],
    ];
    if (state.user.can_manage_users) nav.push(["users", "Pessoas & acessos"]);
    return `<aside class="agenda-sidebar"><div class="aviva-brand"><img src="/static/assets/aviva-logo.png" alt="Aviva" width="427" height="200"></div><div class="brand-caption">Gestão de espaços</div><div class="resort-wordmark">Costa do Sauípe<br>Rio Quente Resorts</div><nav class="agenda-nav" aria-label="Navegação principal">${nav.map(([id, label]) => `<button data-action="navigate" data-view="${id}" class="${state.view === id ? "current" : ""}" ${state.view === id ? 'aria-current="page"' : ""}>${label}</button>`).join("")}</nav><div class="sidebar-note">Uma base compartilhada.<br>Cada equipe cuida dos seus bloqueios.</div><div class="sidebar-user"><strong>${esc(state.user.name)}</strong><small>${state.user.team_id === "commercial" ? "Comercial MICE" : "Operacional"}</small>${state.authMode === "entra" ? "" : '<button data-action="password">Alterar minha senha</button>'}<button data-action="logout">Sair da agenda ↗</button></div></aside>`;
  }
  function toolbar(withMonth) {
    return `<div class="agenda-toolbar">${withMonth ? `<div class="month-navigation">${btn("prev-month", "‹", 'aria-label="Mês anterior"')}<select id="month" aria-label="Mês">${months.map((m, i) => option(i, m, state.month)).join("")}</select><select id="year" class="year-select" aria-label="Ano">${[2026, 2027, 2028].map((y) => option(y, y, state.year)).join("")}</select>${btn("next-month", "›", 'aria-label="Próximo mês"')}</div>` : ""}<label>Empreendimento<select id="resort">${option("all", "Todos", state.resort)}${Object.entries(
      resorts,
    )
      .map(([k, v]) => option(k, v, state.resort))
      .join(
        "",
      )}</select></label><label>Situação<select id="status">${option("", "Todas", state.status)}${Object.entries(
      statusNames,
    )
      .map(([k, v]) => option(k, v, state.status))
      .join(
        "",
      )}</select></label><label class="grow">Pesquisa<input id="search" type="search" placeholder="Espaço, evento ou responsável…" value="${esc(state.search)}"></label>${withMonth ? `<div class="view-toggle">${["grid", "list"].map((v) => `<button data-action="mode" data-mode="${v}" class="${state.mode === v ? "selected" : ""}">${v === "grid" ? "Grade" : "Lista"}</button>`).join("")}</div>` : ""}</div>`;
  }
  function calendarView() {
    const relevant = new Set(
      state.bookings.flatMap((b) =>
        b.allocations.map((a) => a.configuration_id),
      ),
    );
    const rows = state.calendar.filter(
      (c) =>
        !state.search ||
        normalized(c.name).includes(normalized(state.search)) ||
        relevant.has(c.id),
    );
    return `<section class="agenda-card">${toolbar(true)}<div class="calendar-caption"><strong>${months[state.month]} de ${state.year}</strong><span>${rows.length} espaços/configurações · selecione um dia para consultar</span></div>${
      state.mode === "list"
        ? bookingList(state.bookings)
        : rows.length
          ? `<div class="calendar-scroll"><table class="calendar-grid"><caption class="sr-only">Ocupação por espaço e dia. A validar não significa livre.</caption><thead><tr><th class="space-cell">Espaço / configuração</th>${state.days
              .map((d) => {
                const dt = new Date(`${d}T12:00:00`);
                return `<th class="${[0, 6].includes(dt.getDay()) ? "weekend" : ""}">${Number(d.slice(-2))}<small>${dt.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")}</small></th>`;
              })
              .join("")}</tr></thead><tbody>${rows
              .map(
                (c) =>
                  `<tr><td class="space-cell"><button data-action="space-detail" data-id="${c.id}">${esc(c.name).replaceAll("+", "+<wbr>")}</button><small>${c.validated ? esc(resortName(c.resort_id)) : "○ Composição a validar"}</small></td>${state.days
                    .map((d) => {
                      const cell = c.days[d];
                      return `<td class="${cell.state}"><button class="day-button ${cell.state}" data-action="day" data-id="${c.id}" data-day="${d}" aria-label="${esc(c.name)}, ${fmt(d)}, ${cell.state === "unvalidated" ? "a validar" : cell.state === "available" ? "sem ocupação efetiva" : cell.state === "partial" ? "ocupação parcial das opções" : "ocupado"}${cell.requests.length ? `, ${cell.requests.length} solicitações` : ""}">${cell.state === "occupied" ? "●" : cell.state === "partial" ? "◐" : ""}${cell.requests.length ? `<span class="request-count">${cell.requests.length}</span>` : ""}</button></td>`;
                    })
                    .join("")}</tr>`,
              )
              .join("")}</tbody></table></div>`
          : '<div class="empty-state"><h3>Nenhum espaço neste filtro</h3><p>Ajuste o empreendimento ou a pesquisa para ver outros espaços.</p></div>'
    }<div class="legend"><span>▧ Composição a validar</span><span>● Ocupação efetiva</span><span>◐ Algumas composições ocupadas</span><span>Contador amarelo: solicitações pendentes / em espera</span></div></section>`;
  }
  function bookingList(items) {
    if (!items.length)
      return '<div class="empty-state"><h3>Nenhuma solicitação neste período</h3><p>Ajuste os filtros ou registre uma nova solicitação.</p></div>';
    return `<div class="booking-list">${items
      .map((b) => {
        const a = b.matched_allocations || b.allocations;
        return `<article class="booking-row"><div><h3>${esc(b.title)}</h3><small>${esc(b.responsible)} · ${esc(b.team_name)}</small><small>Entrada #${b.queue_number}</small></div><div><p>${[...new Set(a.map((x) => x.space_name))].map(esc).join("<br>")}</p></div><div><p>${fmt(a.map((x) => x.start_date).sort()[0])}<br>até ${fmt(
          a
            .map((x) => x.end_date)
            .sort()
            .at(-1),
        )}</p></div><div class="row-status">${pill(b.status)}</div>${btn("booking-detail", "Consultar", `data-id="${b.id}"`)}</article>`;
      })
      .join("")}</div>`;
  }
  function catalogView() {
    const rows = state.catalog.filter(
      (c) =>
        (state.resort === "all" || c.resort_id === state.resort) &&
        (!state.search ||
          normalized(c.name).includes(normalized(state.search)) ||
          c.source_codes.join(",").includes(state.search)),
    );
    return `<section class="agenda-card">${toolbar(false)}<div class="calendar-caption"><strong>${rows.length} espaços/configurações</strong><span>${state.sourceCount} itens de origem · 2 serviços excluídos da agenda</span></div>${state.user.can_catalog ? `<div class="legend">${btn("sources", "Ver itens de origem")}${btn("import", "Revisar importação")}${btn("catalog-history", "Histórico cadastral")}</div>` : ""}<div class="catalog-scroll"><table class="catalog-table"><thead><tr>${state.user.can_catalog ? "<th>Selecionar</th>" : ""}<th>Espaço / código de origem</th><th>Empreendimento</th><th>Validação física</th><th>Ações</th></tr></thead><tbody>${rows.map((c) => `<tr>${state.user.can_catalog ? `<td class="selection"><input type="checkbox" data-select="${c.id}" aria-label="Selecionar ${esc(c.name)}"></td>` : ""}<td><strong>${esc(c.name)}</strong><small>Cód. ${c.source_codes.join(", ")} · ${esc(c.group_name || "Outros espaços")}</small></td><td>${esc(resortName(c.resort_id))}<small>${esc(c.location)}</small></td><td>${c.validated ? '<span class="status-pill status-option">Validada</span>' : '<span class="status-pill">A validar</span>'}</td><td><div class="catalog-actions">${btn("space-detail", "Detalhes", `data-id="${c.id}"`)}${state.user.can_catalog ? btn("topology", "Validar composição", `data-id="${c.id}"`) : ""}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }
  function reportsView() {
    return `<section class="agenda-card">${toolbar(false)}<div class="report-filters"><label>De<input id="report-from" type="date" value="${state.reportFrom}" min="2026-01-01" max="2028-12-31"></label><label>Até<input id="report-to" type="date" value="${state.reportTo}" min="2026-01-01" max="2028-12-31"></label>${btn("report-apply", "Aplicar período")}${btn("csv", "Exportar CSV")}${btn("print", "Imprimir / PDF")}</div>${bookingList(state.bookings)}</section>`;
  }
  function usersView() {
    return `<section class="agenda-card users-table"><div class="legend">${btn("auth-history", "Histórico de acessos")}</div><p class="form-help">Para definir quem pode adicionar pessoas, conceder acessos e excluir membros, abra Ajustar acesso e marque Administrador de acessos.</p>${state.users
      .map(
        (u) =>
          `<article><div><strong>${esc(u.name)}</strong><p class="form-help">${esc(u.username)} · ${u.team_id === "commercial" ? "Comercial MICE" : "Operacional"} · ${u.active ? "Ativo" : "Desativado"}<br>${
            u.scopes
              .filter((s) => resorts[s])
              .map((s) => esc(resorts[s]))
              .join(" · ") || "Nenhum empreendimento"
          }<br>${[u.can_catalog ? "Cadastro" : "", u.can_schedule ? "Responsável da fila" : "", u.can_manage_users ? "Administrador de acessos" : ""].filter(Boolean).join(" · ") || "Consulta e edição da própria equipe"}</p></div>${u.id !== state.user.id ? `<div class="user-actions">${btn("edit-user", "Ajustar acesso", `data-id="${u.id}"`)}<button type="button" class="btn danger" data-action="delete-user" data-id="${u.id}">Excluir pessoa</button></div>` : ""}</article>`,
      )
      .join("")}</section>`;
  }

  return {
    sidebar,
    toolbar,
    calendarView,
    bookingList,
    catalogView,
    reportsView,
    usersView,
  };
}
