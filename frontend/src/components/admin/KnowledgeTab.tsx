import { useEffect, useState } from "react";
import {
  adminAprovarConhecimento,
  adminCriarConhecimento,
  adminEditarConhecimento,
  adminExcluirConhecimento,
  adminListarConhecimento,
  adminRejeitarConhecimento,
  ApiError,
} from "../../lib/api";
import type { KnowledgeEntry, KnowledgeStatus } from "../../lib/types";
import { use401Redirect } from "../../hooks/use401Redirect";
import { IconAprovado, IconBase, IconBuscar, IconLapis, IconLixeira, IconMais } from "../icons/Icons";
import EmptyState from "../common/EmptyState";
import EditarConhecimentoModal from "./EditarConhecimentoModal";
import { formatarDataHora } from "../../lib/formatarData";
import NovaConhecimentoModal from "./NovaConhecimentoModal";

interface KnowledgeTabProps {
  onAviso: (msg: string, tipo: "ok" | "erro") => void;
}

export default function KnowledgeTab({ onAviso }: KnowledgeTabProps) {
  const tratar401 = use401Redirect();
  const [status, setStatus] = useState<KnowledgeStatus | "">("pendente");
  const [entradas, setEntradas] = useState<KnowledgeEntry[]>([]);
  const [editando, setEditando] = useState<KnowledgeEntry | null>(null);
  const [criando, setCriando] = useState(false);
  const [busca, setBusca] = useState("");

  const termo = busca.trim().toLowerCase();
  const entradasFiltradas = termo
    ? entradas.filter(
        (e) =>
          e.titulo.toLowerCase().includes(termo) ||
          e.conteudo.toLowerCase().includes(termo) ||
          e.categoria.toLowerCase().includes(termo) ||
          e.criado_por.toLowerCase().includes(termo),
      )
    : entradas;

  async function carregar() {
    try {
      const data = await adminListarConhecimento(status);
      setEntradas(data.entries);
    } catch (err) {
      tratar401(err);
    }
  }

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  function mensagemErro(err: unknown) {
    return err instanceof ApiError ? err.message : "Falha de conexão com o backend.";
  }

  async function decidir(id: number, acao: "aprovar" | "rejeitar") {
    try {
      if (acao === "aprovar") await adminAprovarConhecimento(id);
      else await adminRejeitarConhecimento(id);
      onAviso(acao === "aprovar" ? "Entrada aprovada." : "Entrada rejeitada e removida.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  async function salvarEdicao(patch: { titulo: string; conteudo: string; categoria: string }) {
    if (!editando) return;
    try {
      await adminEditarConhecimento(editando.id, patch);
      setEditando(null);
      onAviso("Entrada atualizada.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  async function criarEntrada(patch: { titulo: string; conteudo: string; categoria: string }) {
    try {
      await adminCriarConhecimento(patch);
      setCriando(false);
      onAviso("Entrada criada.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  async function excluirAprovada(id: number) {
    if (!confirm("Excluir esta entrada da base de conhecimento? Ela sai do prompt do chat imediatamente.")) return;
    try {
      await adminExcluirConhecimento(id);
      onAviso("Entrada excluída.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  return (
    <>
      <h1 style={{ marginTop: 0 }}>Base de conhecimento</h1>
      <p className="sub">
        Resumos de sessão (via /compact) e outras contribuições entram aqui como pendentes. Só depois de aprovadas
        passam a fazer parte do prompt do chat.
      </p>
      <button
        className="btn-primario"
        style={{ display: "inline-flex", alignItems: "center", gap: 6, whiteSpace: "nowrap", marginBottom: 16 }}
        onClick={() => setCriando(true)}
      >
        <IconMais style={{ width: 16, height: 16 }} /> Nova entrada
      </button>

      <div className="filtro-linha">
        <div className="campo">
          <label htmlFor="conhecimento-filtro-status">Status</label>
          <select id="conhecimento-filtro-status" value={status} onChange={(e) => setStatus(e.target.value as KnowledgeStatus | "")}>
            <option value="pendente">Pendentes</option>
            <option value="aprovado">Aprovados</option>
            <option value="">Todos</option>
          </select>
        </div>
        <div className="campo" style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="conhecimento-busca">Buscar</label>
          <div style={{ position: "relative" }}>
            <IconBuscar style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--slate-500)" }} />
            <input
              id="conhecimento-busca"
              placeholder="Título, conteúdo, categoria ou autor..."
              style={{ paddingLeft: 32 }}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>
        </div>
      </div>

      {entradasFiltradas.length === 0 ? (
        <EmptyState
          icone={<IconBase />}
          titulo={termo ? "Nada encontrado" : "Nada por aqui"}
          texto={
            termo
              ? "Nenhuma entrada bate com essa busca — tente outro termo."
              : "Assim que uma sessão for compactada ou alguém contribuir, a entrada aparece aqui para revisão."
          }
        />
      ) : (
      <table>
        <thead>
          <tr>
            <th>Título</th><th>Categoria</th><th>Conteúdo</th><th>Enviado por</th><th>Quando</th><th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {entradasFiltradas.map((e) => (
            <tr key={e.id}>
              <td>{e.titulo}</td>
              <td>{e.categoria}</td>
              <td style={{ maxWidth: 320 }} title={e.conteudo}>
                {e.conteudo.length > 140 ? e.conteudo.slice(0, 140) + "…" : e.conteudo}
              </td>
              <td>{e.criado_por}</td>
              <td>{formatarDataHora(e.criado_em || "")}</td>
              <td>
                <div className="acoes">
                  <button className="btn-icone" title="Ver e editar conteúdo completo" onClick={() => setEditando(e)}>
                    <IconLapis />
                  </button>
                  {e.status === "pendente" ? (
                    <>
                      <button className="btn-primario" onClick={() => decidir(e.id, "aprovar")}>Aprovar</button>
                      <button className="btn-sec" onClick={() => decidir(e.id, "rejeitar")}>Rejeitar</button>
                    </>
                  ) : (
                    <>
                      <span className="badge"><IconAprovado /> Aprovado</span>
                      <button className="btn-icone perigo" title="Excluir da base" onClick={() => excluirAprovada(e.id)}>
                        <IconLixeira />
                      </button>
                    </>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      )}

      <EditarConhecimentoModal entrada={editando} onFechar={() => setEditando(null)} onSalvar={salvarEdicao} />
      <NovaConhecimentoModal aberto={criando} onFechar={() => setCriando(false)} onSalvar={criarEntrada} />
    </>
  );
}
