import { Fragment, useEffect, useState } from "react";
import { adminDashboard } from "../../lib/api";
import type { DashboardStats } from "../../lib/types";
import { use401Redirect } from "../../hooks/use401Redirect";
import { IconBase, IconEconomia, IconMonitorado, IconUsuarios } from "../icons/Icons";
import EmptyState from "../common/EmptyState";
import { formatarData, formatarDataHora } from "../../lib/formatarData";

const fmt = (n: number) => new Intl.NumberFormat("pt-BR").format(n);
const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

export default function DashboardTab() {
  const tratar401 = use401Redirect();
  const [periodo, setPeriodo] = useState(30);
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    adminDashboard(periodo)
      .then(setStats)
      .catch((err) => tratar401(err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo]);

  const maxVolume = stats ? Math.max(1, ...stats.volume_diario.map((v) => v.mensagens)) : 1;
  const maxHeatmap = stats ? Math.max(1, ...stats.heatmap.map((h) => h.mensagens)) : 1;
  const heatmapMap = new Map(stats?.heatmap.map((h) => [`${h.dia_semana}-${h.hora}`, h.mensagens]) ?? []);

  return (
    <>
      <div className="filtro-linha" style={{ justifyContent: "space-between" }}>
        <h1 style={{ marginTop: 0, marginBottom: 0 }}>Dashboard de uso</h1>
        <div className="campo" style={{ maxWidth: 220, flexShrink: 0 }}>
          <label htmlFor="dashboard-periodo">Período</label>
          <select id="dashboard-periodo" style={{ minWidth: 0, width: "100%" }} value={periodo} onChange={(e) => setPeriodo(Number(e.target.value))}>
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={90}>Últimos 90 dias</option>
          </select>
        </div>
      </div>

      <div className="dashboard-cards">
        <div className="stat-card card">
          <div className="icone-rotulo"><IconMonitorado /><span className="rotulo">Total de mensagens</span></div>
          <div className="valor">{stats ? fmt(stats.total_mensagens) : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconUsuarios /><span className="rotulo">Usuários ativos</span></div>
          <div className="valor">{stats ? fmt(stats.usuarios_ativos) : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconEconomia /><span className="rotulo">Média de mensagens/dia</span></div>
          <div className="valor">{stats ? stats.media_mensagens_dia : "—"}</div>
        </div>
        <div className="stat-card card">
          <div className="icone-rotulo"><IconBase /><span className="rotulo">Tokens de saída</span></div>
          <div className="valor">{stats ? fmt(stats.tokens_output) : "—"}</div>
        </div>
      </div>

      <div className="dashboard-grid" style={{ marginBottom: 20 }}>
        <div className="dashboard-secao card" style={{ padding: 16 }}>
          <h2>Volume de mensagens ao longo do tempo</h2>
          {stats && stats.volume_diario.length === 0 ? (
            <EmptyState icone={<IconMonitorado />} titulo="Sem dados no período" texto="Ainda não há mensagens registradas nesse intervalo." />
          ) : (
            <div className="volume-chart-wrap">
              <div className="volume-eixo-y">
                <span>{fmt(maxVolume)}</span>
                <span>{fmt(Math.round(maxVolume / 2))}</span>
                <span>0</span>
              </div>
              <div className="volume-chart-col">
                <div className="volume-chart">
                  {stats?.volume_diario.map((v) => (
                    <div key={v.dia} className="volume-barra-wrap" title={`${formatarData(v.dia)}: ${v.mensagens} mensagem(ns)`}>
                      <div className="volume-barra" style={{ height: `${(v.mensagens / maxVolume) * 100}%` }} />
                    </div>
                  ))}
                </div>
                <div className="volume-eixo-x">
                  {stats?.volume_diario.map((v, i, arr) => {
                    const passo = Math.max(1, Math.ceil(arr.length / 8));
                    const mostrar = i % passo === 0 || i === arr.length - 1;
                    return (
                      <span key={v.dia} className="volume-eixo-x-label">
                        {mostrar ? formatarData(v.dia).slice(0, 5) : ""}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="dashboard-secao card" style={{ padding: 16 }}>
          <h2>Heatmap de horário de pico</h2>
          <div className="heatmap-grid">
            <div />
            {Array.from({ length: 24 }, (_, h) => (
              <div key={h} className="heatmap-label" style={{ justifyContent: "center" }}>{h}</div>
            ))}
            {DIAS_SEMANA.map((label, dia) => (
              <Fragment key={"dia" + dia}>
                <div className="heatmap-label">{label}</div>
                {Array.from({ length: 24 }, (_, hora) => {
                  const v = heatmapMap.get(`${dia}-${hora}`) || 0;
                  const intensidade = v / maxHeatmap;
                  return (
                    <div
                      key={`${dia}-${hora}`}
                      className="heatmap-celula"
                      title={`${label} ${hora}h: ${v} mensagens`}
                      style={v > 0 ? { background: `color-mix(in srgb, var(--accent) ${20 + intensidade * 80}%, var(--surface-2))` } : undefined}
                    />
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-secao card" style={{ padding: 16 }}>
          <h2>Ranking de usuários</h2>
          {stats && stats.ranking.length === 0 ? (
            <EmptyState icone={<IconUsuarios />} titulo="Sem atividade no período" texto="Nenhum usuário enviou mensagens nesse intervalo." />
          ) : (
            <div className="dashboard-tabela-wrap">
              <table>
                <thead>
                  <tr><th>Usuário</th><th>Mensagens</th><th>Tokens</th><th>Última atividade</th></tr>
                </thead>
                <tbody>
                  {stats?.ranking.map((r) => (
                    <tr key={r.email}>
                      <td>{r.email}</td>
                      <td>{fmt(r.mensagens)}</td>
                      <td>{fmt(r.tokens)}</td>
                      <td>{formatarDataHora(r.ultima_atividade || "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="dashboard-secao card" style={{ padding: 16 }}>
          <h2>Sessões mais ativas</h2>
          {stats && stats.sessoes_ativas.length === 0 ? (
            <EmptyState icone={<IconMonitorado />} titulo="Sem sessões no período" texto="Nenhuma sessão teve mensagens nesse intervalo." />
          ) : (
            <div className="dashboard-tabela-wrap">
              <table>
                <thead>
                  <tr><th>Sessão</th><th>Usuário</th><th>Mensagens</th><th>Tokens</th></tr>
                </thead>
                <tbody>
                  {stats?.sessoes_ativas.map((s) => (
                    <tr key={s.id}>
                      <td>{s.titulo}</td>
                      <td>{s.usuario}</td>
                      <td>{fmt(s.mensagens)}</td>
                      <td>{fmt(s.tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
