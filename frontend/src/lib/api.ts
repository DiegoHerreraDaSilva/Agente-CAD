import type {
  AdminUsuario,
  BuscaResposta,
  CacheStats,
  DashboardStats,
  KnowledgeEntry,
  KnowledgeStatus,
  LoginResposta,
  Mensagem,
  Nivel,
  Role,
  SessaoDetalhe,
  SessaoResumo,
  Snippet,
  Usuario,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: init?.body
      ? { "Content-Type": "application/json", ...(init?.headers || {}) }
      : init?.headers,
  });
  if (!resp.ok) {
    let detail = `Erro ${resp.status}`;
    try {
      const j = await resp.json();
      detail = j.detail || detail;
    } catch {
      /* corpo não era JSON */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

// ---------------------------------------------------------------------------
// Autenticação
// ---------------------------------------------------------------------------
export const login = (email: string, senha: string) =>
  req<LoginResposta>("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) });

export const logout = () => req<{ ok: boolean }>("/auth/logout", { method: "POST" });

export const me = () => req<Usuario>("/auth/me");

export const changePassword = (senha_atual: string, senha_nova: string) =>
  req<{ ok: boolean }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ senha_atual, senha_nova }),
  });

export const salvarMemoria = (memoria: string) =>
  req<{ ok: boolean }>("/auth/me/memoria", { method: "PUT", body: JSON.stringify({ memoria }) });

// ---------------------------------------------------------------------------
// Sessões de chat
// ---------------------------------------------------------------------------
export const listarSessoes = () => req<{ sessions: SessaoResumo[] }>("/sessions");

export const criarSessao = () => req<{ id: number; titulo: string }>("/sessions", { method: "POST" });

export const buscarSessao = (id: number) => req<SessaoDetalhe>(`/sessions/${id}`);

export const renomearSessao = (id: number, titulo: string) =>
  req<{ id: number; titulo: string }>(`/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ titulo }),
  });

export const excluirSessao = (id: number) => req<{ ok: boolean }>(`/sessions/${id}`, { method: "DELETE" });

export const compactarSessao = (id: number) =>
  req<{ ok: boolean; resumo?: string; mensagem?: string }>(`/sessions/${id}/compact`, { method: "POST" });

export const fixarSessao = (id: number, pinned: boolean) =>
  req<{ ok: boolean; pinned: boolean }>(`/sessions/${id}/pin`, {
    method: "PATCH",
    body: JSON.stringify({ pinned }),
  });

export const regenerarUltimaResposta = (id: number) =>
  req<{ ok: boolean; pergunta: string }>(`/sessions/${id}/regenerate`, { method: "POST" });

export const excluirMensagemEResto = (sessionId: number, messageId: number) =>
  req<{ ok: boolean }>(`/sessions/${sessionId}/messages/${messageId}/rest`, { method: "DELETE" });

export const buscarConversas = (q: string) =>
  req<BuscaResposta>(`/sessions/search?q=${encodeURIComponent(q)}`);

// ---------------------------------------------------------------------------
// Templates de prompt pessoais
// ---------------------------------------------------------------------------
export const listarSnippets = () => req<{ snippets: Snippet[] }>("/snippets");

export const criarSnippet = (titulo: string, conteudo: string) =>
  req<Snippet>("/snippets", { method: "POST", body: JSON.stringify({ titulo, conteudo }) });

export const excluirSnippet = (id: number) =>
  req<{ ok: boolean }>(`/snippets/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Chat (streaming SSE)
// ---------------------------------------------------------------------------
export async function enviarMensagem(
  sessionId: number,
  pergunta: string,
  imagens: string[],
  onTexto: (chunk: string) => void,
): Promise<void> {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, pergunta, imagens }),
  });
  if (resp.status === 401) throw new ApiError(401, "Não autenticado");
  if (!resp.ok || !resp.body) throw new ApiError(resp.status, `Backend respondeu ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const partes = buffer.split("\n\n");
    buffer = partes.pop() ?? "";

    for (const parte of partes) {
      const linha = parte.trim();
      if (!linha.startsWith("data:")) continue;
      const dados = linha.slice("data:".length).trim();
      if (dados === "[DONE]") continue;
      try {
        const obj = JSON.parse(dados);
        if (obj.text) onTexto(obj.text);
      } catch {
        /* fragmento incompleto — ignora */
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Base de conhecimento compartilhada (visão do usuário comum)
// ---------------------------------------------------------------------------
export const listarConhecimento = () => req<{ entries: KnowledgeEntry[] }>("/knowledge");

// ---------------------------------------------------------------------------
// Admin — usuários
// ---------------------------------------------------------------------------
export const adminListarUsuarios = () => req<{ users: AdminUsuario[] }>("/admin/users");

export const adminCriarUsuario = (email: string, senha: string, nivel: Nivel, role: Role) =>
  req<{ id: number; email: string; nivel: Nivel; role: Role }>("/admin/users", {
    method: "POST",
    body: JSON.stringify({ email, senha, nivel, role }),
  });

export const adminEditarUsuario = (
  id: number,
  patch: { email?: string; nivel?: Nivel; role?: Role },
) => req<{ ok: boolean }>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) });

export const adminTrocarSenha = (id: number, senha: string) =>
  req<{ ok: boolean }>(`/admin/users/${id}/senha`, { method: "POST", body: JSON.stringify({ senha }) });

export const adminExcluirUsuario = (id: number) =>
  req<{ ok: boolean }>(`/admin/users/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Admin — economia de prompt caching
// ---------------------------------------------------------------------------
export const adminCacheStats = (usuarioId?: number) =>
  req<CacheStats>(
    usuarioId ? `/admin/cache-stats?usuario_id=${encodeURIComponent(usuarioId)}` : "/admin/cache-stats",
  );

export const adminDashboard = (dias = 30) =>
  req<DashboardStats>(`/admin/dashboard?dias=${dias}`);

// ---------------------------------------------------------------------------
// Admin — fila de aprovação da base de conhecimento
// ---------------------------------------------------------------------------
export const adminListarConhecimento = (status?: KnowledgeStatus | "") =>
  req<{ entries: KnowledgeEntry[] }>(
    status ? `/admin/knowledge?status=${encodeURIComponent(status)}` : "/admin/knowledge",
  );

export const adminCriarConhecimento = (patch: { titulo: string; conteudo: string; categoria: string }) =>
  req<{ id: number }>("/admin/knowledge", { method: "POST", body: JSON.stringify(patch) });

export const adminAprovarConhecimento = (id: number) =>
  req<{ ok: boolean }>(`/admin/knowledge/${id}/aprovar`, { method: "POST" });

export const adminRejeitarConhecimento = (id: number) =>
  req<{ ok: boolean }>(`/admin/knowledge/${id}/rejeitar`, { method: "POST" });

export const adminEditarConhecimento = (
  id: number,
  patch: { titulo?: string; conteudo?: string; categoria?: string },
) => req<{ ok: boolean }>(`/admin/knowledge/${id}`, { method: "PATCH", body: JSON.stringify(patch) });

export const adminExcluirConhecimento = (id: number) =>
  req<{ ok: boolean }>(`/admin/knowledge/${id}`, { method: "DELETE" });

export type { Mensagem };
