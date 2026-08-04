export type Nivel = "estagiario" | "junior" | "pleno" | "senior";
export type Role = "engineer" | "admin";
export type KnowledgeStatus = "pendente" | "aprovado" | "rejeitado";

export interface Usuario {
  id: number;
  email: string;
  nivel: Nivel;
  memoria: string;
  role: Role;
  must_change_senha: boolean;
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
  pinned: boolean;
}

export interface Mensagem {
  id?: number;
  papel: "user" | "assistant";
  conteudo: string;
  criado_em?: string;
}

export interface SessaoDetalhe {
  id: number;
  titulo: string;
  resumo: string;
  mensagens: Mensagem[];
}

export interface Snippet {
  id: number;
  titulo: string;
  conteudo: string;
}

export interface BuscaResultadoSessao {
  id: number;
  titulo: string;
  atualizado_em: string;
}

export interface BuscaResultadoMensagem {
  message_id: number;
  session_id: number;
  session_titulo: string;
  papel: "user" | "assistant";
  trecho: string;
  criado_em: string;
}

export interface BuscaResposta {
  sessoes: BuscaResultadoSessao[];
  mensagens: BuscaResultadoMensagem[];
}

export interface DashboardVolumeDia {
  dia: string;
  mensagens: number;
}

export interface DashboardHeatmapPonto {
  dia_semana: number;
  hora: number;
  mensagens: number;
}

export interface DashboardRankingUsuario {
  email: string;
  mensagens: number;
  tokens: number;
  ultima_atividade: string | null;
}

export interface DashboardSessaoAtiva {
  id: number;
  titulo: string;
  usuario: string;
  mensagens: number;
  tokens: number;
}

export interface DashboardStats {
  periodo_dias: number;
  total_mensagens: number;
  usuarios_ativos: number;
  media_mensagens_dia: number;
  tokens_output: number;
  volume_diario: DashboardVolumeDia[];
  heatmap: DashboardHeatmapPonto[];
  ranking: DashboardRankingUsuario[];
  sessoes_ativas: DashboardSessaoAtiva[];
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
