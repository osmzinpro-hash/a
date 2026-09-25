// Vercel: todas as rotas /api/* chegam aqui (veja vercel.json) e usam a mesma lógica do servidor local.
// O banco é o Postgres ligado ao projeto (DATABASE_URL ou POSTGRES_URL, criado pela integração Neon).
import { createApi } from '../lib/app.js';

const api = createApi();

export default function handler(req, res) {
  return api.handle(req, res);
}
