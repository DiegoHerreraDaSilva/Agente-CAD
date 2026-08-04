export type Nivel = "estagiario" | "junior" | "pleno" | "senior";
export type Role = "engineer" | "admin";
export type KnowledgeStatus = "pendente" | "aprovado" | "rejeitado";
export type LlmProvider = "deepseek" | "anthropic";

export interface Usuario {
  id: number;
  email: string;
  nivel: Nivel;
  memoria: string;
  role: Role;
  must_change_senha: boolean;
  // Provider de LLM ativo no backend (config global, não por usuário) —
  // usado pra decidir se a feature de anexar imagem aparece no chat (não
  // suportada sob DeepSeek).
  provider: LlmProvider;
}

export interface LoginResposta {
  email: string;
  nivel: Nivel;
  must_change_senha: boolean;
}

export interface SessaoResumo {
  id: number;
  titulo: string;
  atualizado_em: string;
}

export interface Mensagem {
  papel: "user" | "assistant";
  conteudo: string;
}

export interface SessaoDetalhe {
  id: number;
  titulo: string;
  resumo: string;
  mensagens: Mensagem[];
}

export interface AdminUsuario {
  id: number;
  email: string;
  nivel: Nivel;
  role: Role;
  criado_em: string;
}

export interface CacheStatsRecente {
  sessao: string;
  usuario: string;
  input_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  output_tokens: number;
  provider: LlmProvider;
  criado_em: string;
}

export interface CacheStats {
  total_mensagens: number;
  input_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  output_tokens: number;
  custo_real_usd: number;
  custo_sem_cache_usd: number;
  economia_usd: number;
  economia_pct: number;
  recentes: CacheStatsRecente[];
}

export interface KnowledgeEntry {
  id: number;
  titulo: string;
  conteudo: string;
  categoria: string;
  criado_por: string;
  status: KnowledgeStatus;
  criado_em: string;
}
