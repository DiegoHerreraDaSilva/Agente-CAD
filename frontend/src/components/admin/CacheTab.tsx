import { useEffect, useState } from "react";
import { adminCacheStats, adminListarUsuarios } from "../../lib/api";
import type { AdminUsuario, CacheStats } from "../../lib/types";
import { use401Redirect } from "../../hooks/use401Redirect";
import { IconBase, IconEconomia, IconMonitorado } from "../icons/Icons";
import EmptyState from "../common/EmptyState";

const fmt = (n: number) => new Intl.NumberFormat("pt-BR").format(n);

export default function CacheTab() {
  const tratar401 = use401Redirect();
  const [usuarios, setUsuarios] = useState<AdminUsuario[]>([]);
  const [usuarioId, setUsuarioId] = useState<string>("");
  const [stats, setStats] = useState<CacheStats | null>(null);

  useEffect(() => {
    adminListarUsuarios()
      .then((data) => setUsuarios(data.users))
      .catch((err) => tratar401(err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    adminCacheStats(usuarioId ? Number(usuarioId) : undefined)
      .then(setStats)
      .catch((err) => tratar401(err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuarioId]);

  return (
    <>
      <h1 style={{ marginTop: 0 }}>Economia de cache</h1>
      <p className="sub">Tokens do prefixo estável — system prompt (tom + memória + resumo) e histórico da conversa — reaproveitados automaticamente pelo cache da DeepSeek, em vez de reprocessados a cada mensagem. A base de conhecimento não entra aqui: é recuperada por RAG (dinâmica por pergunta) e vai no turno atual, fora do cache.</p>

      <div className="filtro-linha">
        <div className="campo">
          <label htmlFor="cache-filtro-usuario">Filtrar por usuário</label>
          <select id="cache-filtro-usuario" value={usuarioId} onChange={(e) => setUsuarioId(e.target.value)}>
            <option value="">Todos os usuários</option>
            {usuarios.map((u) => (
              <option key={u.id} value={u.id}>{u.email}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card card">
          <div className="icone-rotulo"><IconMonitorado /><span className="rotulo">Mensagens monitoradas</span></div>
          <div className="valor">{stats ? fmt(stats.total_mensagens) : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconBase /><span className="rotulo">Tokens lidos do cache</span></div>
          <div className="valor destaque">{stats ? fmt(stats.cache_read_input_tokens) : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconBase /><span className="rotulo">Tokens escritos no cache</span></div>
          <div className="valor">{stats ? fmt(stats.cache_creation_input_tokens) : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconEconomia /><span className="rotulo">Economia estimada</span></div>
          <div className="valor destaque">{stats ? stats.economia_pct + "%" : "—"}</div>
          <div className="legenda">
            {stats && `≈ US$ ${stats.economia_usd.toFixed(4)} economizados (de US$ ${stats.custo_sem_cache_usd.toFixed(4)})`}
          </div>
        </div>
      </div>

      {stats && stats.recentes.length === 0 ? (
        <EmptyState icone={<IconMonitorado />} titulo="Nenhuma mensagem registrada ainda" texto="Assim que o chat for usado, o consumo de tokens (e a economia de cache) aparece aqui." />
      ) : (
      <table style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Sessão</th><th>Usuário</th><th>Input</th><th>Cache write</th><th>Cache read</th><th>Output</th><th>Quando</th>
          </tr>
        </thead>
        <tbody>
          {stats?.recentes.map((r, i) => (
            <tr key={i}>
              <td>{r.sessao}</td>
              <td>{r.usuario}</td>
              <td>{fmt(r.input_tokens)}</td>
              <td>{fmt(r.cache_creation_input_tokens)}</td>
              <td>{fmt(r.cache_read_input_tokens)}</td>
              <td>{fmt(r.output_tokens)}</td>
              <td>{(r.criado_em || "").replace("T", " ").slice(0, 16)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
    </>
  );
}
