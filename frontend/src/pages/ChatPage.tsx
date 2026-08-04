import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/layout/Header";
import Sidebar from "../components/chat/Sidebar";
import MessageBubble from "../components/chat/MessageBubble";
import ResumoBox from "../components/chat/ResumoBox";
import ChatInput from "../components/chat/ChatInput";
import PerfilModal from "../components/modal/PerfilModal";
import EmptyState from "../components/common/EmptyState";
import { IconMensagem } from "../components/icons/Icons";
import { useAuthContext } from "../context/AuthContext";
import { use401Redirect } from "../hooks/use401Redirect";
import { useChatStream } from "../hooks/useChatStream";
import { extrairImagensDoConteudo } from "../lib/markdown";
import {
  ApiError,
  buscarSessao,
  compactarSessao,
  criarSessao,
  excluirSessao,
  listarSessoes,
  logout,
  renomearSessao,
  salvarMemoria,
} from "../lib/api";
import type { SessaoResumo } from "../lib/types";

const NIVEL_LABEL: Record<string, string> = {
  estagiario: "Estagiário",
  junior: "Júnior",
  pleno: "Pleno",
  senior: "Sênior",
};

interface MensagemUI {
  id: number;
  papel: "user" | "assistant";
  texto: string;
  imagens?: string[];
  vazio?: boolean;
  erro?: boolean;
}

export default function ChatPage() {
  const { usuario, refetch } = useAuthContext();
  const tratar401 = use401Redirect();
  const { enviando, enviar } = useChatStream();

  const [sessoes, setSessoes] = useState<SessaoResumo[]>([]);
  const [sessaoAtivaId, setSessaoAtivaId] = useState<number | null>(null);
  const [mensagens, setMensagens] = useState<MensagemUI[]>([]);
  const [resumo, setResumo] = useState("");
  const [perfilAberto, setPerfilAberto] = useState(false);
  const [carregando, setCarregando] = useState(true);

  const chatRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);
  const novoId = () => idCounter.current++;

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight });
  }, [mensagens, resumo]);

  async function carregarSessoes() {
    try {
      const data = await listarSessoes();
      setSessoes(data.sessions);
    } catch (err) {
      tratar401(err);
    }
  }

  async function selecionarSessao(id: number) {
    try {
      const data = await buscarSessao(id);
      setSessaoAtivaId(id);
      setResumo(data.resumo || "");
      setMensagens(
        data.mensagens.map((m) => {
          if (m.papel === "user") {
            const { texto, imagens } = extrairImagensDoConteudo(m.conteudo);
            return { id: novoId(), papel: "user" as const, texto, imagens };
          }
          return { id: novoId(), papel: "assistant" as const, texto: m.conteudo };
        }),
      );
    } catch (err) {
      tratar401(err);
    }
  }

  async function novaSessao() {
    try {
      const s = await criarSessao();
      setSessaoAtivaId(s.id);
      setMensagens([]);
      setResumo("");
      await carregarSessoes();
    } catch (err) {
      tratar401(err);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const data = await listarSessoes();
        setSessoes(data.sessions);
        if (data.sessions.length) await selecionarSessao(data.sessions[0].id);
        else await novaSessao();
      } catch (err) {
        tratar401(err);
      } finally {
        setCarregando(false);
      }
    })();
    // roda uma única vez, ao montar a página
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRenomear(id: number, titulo: string) {
    try {
      await renomearSessao(id, titulo);
      await carregarSessoes();
    } catch (err) {
      tratar401(err);
    }
  }

  async function handleExcluir(id: number) {
    if (!confirm("Excluir esta sessão e todo o seu histórico?")) return;
    try {
      await excluirSessao(id);
    } catch (err) {
      if (tratar401(err)) return;
    }
    const eraAtiva = id === sessaoAtivaId;
    await carregarSessoes();
    if (eraAtiva) {
      setSessaoAtivaId(null);
      setMensagens([]);
      setResumo("");
      try {
        const data = await listarSessoes();
        if (data.sessions.length) await selecionarSessao(data.sessions[0].id);
        else await novaSessao();
      } catch (err) {
        tratar401(err);
      }
    }
  }

  async function onCompactar() {
    if (!sessaoAtivaId) return;
    const avisoId = novoId();
    setMensagens((prev) => [...prev, { id: avisoId, papel: "assistant", texto: "🗜️ Compactando a conversa…" }]);
    try {
      const data = await compactarSessao(sessaoAtivaId);
      if (data.ok) {
        await selecionarSessao(sessaoAtivaId);
        await carregarSessoes();
      } else {
        setMensagens((prev) =>
          prev.map((m) => (m.id === avisoId ? { ...m, texto: data.mensagem || "Não foi possível compactar.", erro: true } : m)),
        );
      }
    } catch (err) {
      if (tratar401(err)) return;
      setMensagens((prev) => prev.map((m) => (m.id === avisoId ? { ...m, texto: "Falha de conexão ao compactar.", erro: true } : m)));
    }
  }

  async function onEnviarChat(texto: string, imagens: string[]) {
    if (texto === "/compact" && imagens.length === 0) {
      onCompactar();
      return;
    }
    if (!sessaoAtivaId) return;

    setMensagens((prev) => [...prev, { id: novoId(), papel: "user", texto, imagens }]);
    const agentId = novoId();
    setMensagens((prev) => [...prev, { id: agentId, papel: "assistant", texto: "", vazio: true }]);

    try {
      await enviar(sessaoAtivaId, texto, imagens, (chunk) => {
        setMensagens((prev) =>
          prev.map((m) => (m.id === agentId ? { ...m, texto: m.texto + chunk, vazio: false } : m)),
        );
      });
    } catch (err) {
      if (tratar401(err)) return;
      const msg = err instanceof ApiError ? `⚠️ ${err.message}` : "⚠️ Falha de conexão com o backend.";
      setMensagens((prev) => prev.map((m) => (m.id === agentId ? { ...m, texto: msg, vazio: false, erro: true } : m)));
    } finally {
      carregarSessoes();
    }
  }

  async function handleSalvarMemoria(memoria: string) {
    await salvarMemoria(memoria);
    await refetch();
  }

  async function sair() {
    try {
      await logout();
    } finally {
      window.location.href = "/login";
    }
  }

  return (
    <>
      <Header marca="Agente CAD/NX">
        <span className="user-info">
          <strong>{usuario.email}</strong>
          <span className="nivel-badge">{NIVEL_LABEL[usuario.nivel] || usuario.nivel}</span>
        </span>
        {usuario.role === "admin" && (
          <Link className="btn-sec" to="/admin">Admin</Link>
        )}
        <button className="btn-sec" title="Resumir a conversa e liberar contexto" onClick={onCompactar}>
          Compactar
        </button>
        <button className="btn-sec" onClick={() => setPerfilAberto(true)}>Perfil</button>
        <button className="btn-sec" onClick={sair}>Sair</button>
      </Header>

      <div className="content">
        <Sidebar
          sessoes={sessoes}
          sessaoAtiva={sessaoAtivaId}
          carregando={carregando}
          onSelecionar={selecionarSessao}
          onNova={novaSessao}
          onRenomear={handleRenomear}
          onExcluir={handleExcluir}
        />

        <div className="main">
          <div id="chat" ref={chatRef}>
            {carregando ? (
              <>
                <div className="skeleton skeleton-msg" />
                <div className="skeleton skeleton-msg user" />
                <div className="skeleton skeleton-msg" />
              </>
            ) : (
              <>
                {resumo.trim() && <ResumoBox texto={resumo} />}
                {!mensagens.length && !resumo.trim() && (
                  <EmptyState
                    icone={<IconMensagem />}
                    titulo="Comece a conversa"
                    texto="Pergunte algo sobre CAD/NX — o agente responde com base no seu nível e na base de conhecimento da equipe."
                  />
                )}
                {mensagens.map((m) => (
                  <MessageBubble key={m.id} papel={m.papel} texto={m.texto} imagens={m.imagens} vazio={m.vazio} erro={m.erro} />
                ))}
              </>
            )}
          </div>
          <ChatInput enviando={enviando} onEnviar={onEnviarChat} />
        </div>
      </div>

      <PerfilModal
        aberto={perfilAberto}
        memoriaAtual={usuario.memoria}
        onFechar={() => setPerfilAberto(false)}
        onSalvar={handleSalvarMemoria}
      />
    </>
  );
}
