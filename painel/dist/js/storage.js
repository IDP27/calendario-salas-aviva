// Calendar persistence is central. localStorage is reserved for display preferences.
let csrf = '';
export async function request(path, { method = 'GET', body, key } = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, { method, credentials: 'same-origin', cache: 'no-store',
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-CSRF-Token': csrf } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },
      body: body ? JSON.stringify(body) : undefined });
  } catch { throw new Error('Sem conexão com o servidor. O salvamento não foi confirmado; seu formulário foi preservado.'); }
  let result;
  try { result = await response.json(); } catch { throw new Error('O servidor não confirmou a operação. Tente novamente.'); }
  if (!response.ok) { const error = new Error(result.error || 'Não foi possível concluir.'); error.status = response.status; error.details = result.details; throw error; }
  if (result.csrf) csrf = result.csrf;
  return result;
}
export const repository = {
  session: () => request('/session'), login: body => request('/login', { method: 'POST', body }),
  logout: () => request('/logout', { method: 'POST', body: {} }), catalog: () => request('/catalog'),
  save: (body, id, key) => request(id ? `/bookings/${id}` : '/bookings', { method: id ? 'PUT' : 'POST', body, key }),
};
