import { seedData, validateData } from './model.js';
export const STORAGE_KEY = 'prisma.workspace.v1';
const SESSION_KEY = 'prisma.demo.session';
let lastSaved = null;
export const repository = {
  load() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) { const data = seedData(); this.save(data); return data; }
    try { const data = validateData(JSON.parse(raw)); lastSaved = raw; return data; }
    catch { throw new Error('Não foi possível ler os dados salvos. Eles foram preservados. Importe um backup válido para recuperar o painel.'); }
  },
  save(data, { overwrite = false } = {}) {
    validateData(data);
    const current = localStorage.getItem(STORAGE_KEY);
    if (!overwrite && lastSaved !== null && current !== lastSaved) throw new Error('Os dados foram alterados em outra aba. Exporte seu rascunho como backup e recarregue antes de continuar.');
    const serialized = JSON.stringify(data);
    try { localStorage.setItem(STORAGE_KEY, serialized); lastSaved = serialized; }
    catch { throw new Error('Não foi possível salvar no navegador. O armazenamento pode estar cheio ou bloqueado. Exporte seu rascunho como backup.'); }
  },
  import(text) { return validateData(JSON.parse(text)); },
  login(user, password) {
    if (user.trim() !== 'admin' || password !== 'admin123') throw new Error('Usuário ou senha incorretos.');
    sessionStorage.setItem(SESSION_KEY, 'admin');
  },
  loggedIn() { return sessionStorage.getItem(SESSION_KEY) === 'admin'; },
  logout() { sessionStorage.removeItem(SESSION_KEY); }
};
