import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/layout/Header";
import Sidebar from "../components/chat/Sidebar";
import MessageBubble from "../components/chat/MessageBubble";
import ResumoBox from "../components/chat/ResumoBox";
import ChatInput from "../components/chat/ChatInput";
import SearchModal from "../components/chat/SearchModal";
import HelpModal from "../components/chat/HelpModal";
import FollowUpChips from "../components/chat/FollowUpChips";
import PerfilModal from "../components/modal/PerfilModal";
import EmptyState from "../components/common/EmptyState";
import { IconAjuda, IconBuscar, IconExportar, IconMensagem, IconSeta } from "../components/icons/Icons";
import { useAuthContext } from "../context/AuthContext";
import { use401Redirect } from "../hooks/use401Redirect";
import { useChatStream } from "../hooks/useChatStream";
import { extrairImagensDoConteudo } from "../lib/markdown";
import { exportarSessaoComoMarkdown } from "../lib/exportSession";
import {
  ApiError,
  buscarSessao,
  compactarSessao,
  criarSessao,
  excluirMensagemEResto,
  excluirSessao,
  fixarSessao,
  listarSessoes,
  logout,
  regenerarUltimaResposta,
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
  msgId?: number;
  papel: "user" | "assistant";
  texto: string;
  imagens?: string[];
  vazio?: boolean;
  erro?: boolean;
  criadoEm?: string;
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
  const [buscaAberta, setBuscaAberta] = useState(false);
  const [ajudaAberta, setAjudaAberta] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [mostrarFollowUp, setMostrarFollowUp] = useState(false);
  const [naoSeguindo, setNaoSeguindo] = useState(false);

  const chatRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const idCounter = useRef(0);
  const novoId = () => idCounter.current++;
  // Auto-scroll só acompanha o fim da conversa enquanto o usuário estiver lá —
  // se ele rolar pra cima pra reler algo durante o streaming, os próximos
  // chunks não devem "puxá-lo" de volta.
  const seguindoRef = useRef(true);

  useEffect(() => {
    if (seguindoRef.current) {
      chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight });
    }
  }, [mensagens, resumo]);

  function onScrollChat() {
    const el = chatRef.current;
    if (!el) return;
    const seguindo = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    seguindoRef.current = seguindo;
    setNaoSeguindo(!seguindo);
  }

  function irParaOFim() {
    seguindoRef.current = true;
    setNaoSeguindo(false);
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }

  function mapearMensagens(msgs: { id?: number; papel: "user" | "assistant"; conteudo: string; criado_em?: string }[]): MensagemUI[] {
    return msgs.map((m) => {
      if (m.papel === "user") {
        const { texto, imagens } = extrairImagensDoConteudo(m.conteudo);
        return { id: novoId(), msgId: m.id, papel: "user" as const, texto, imagens, criadoEm: m.criado_em };
      }
      return { id: novoId(), msgId: m.id, papel: "assistant" as const, texto: m.conteudo, criadoEm: m.criado_em };
    });
  }

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
      seguindoRef.current = true;
      setNaoSeguindo(false);
      setSessaoAtivaId(id);
      setResumo(data.resumo || "");
      setMensagens(mapearMensagens(data.mensagens));
      setMostrarFollowUp(data.mensagens.length > 0 && data.mensagens[data.mensagens.length - 1].papel === "assistant");
    } catch (err) {
      tratar401(err);
    }
  }

  async function novaSessao() {
    try {
      const s = await criarSessao();
      seguindoRef.current = true;
      setNaoSeguindo(false);
      setSessaoAtivaId(s.id);
      setMensagens([]);
      setResumo("");
      setMostrarFollowUp(false);
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

  // Atalhos de teclado globais: Ctrl+K busca, Ctrl+N nova sessão, "/" foca o
  // input (quando não se está digitando em outro campo), Esc fecha a busca.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const alvo = e.target as HTMLElement;
      const digitando = alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.isContentEditable;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setBuscaAberta(true);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        novaSessao();
        return;
      }
      if (e.key === "/" && !digitando) {
        e.preventDefault();
        inputRef.current?.focus();
        return;
      }
      if (e.key === "?" && !digitando) {
        e.preventDefault();
        setAjudaAberta(true);
        return;
      }
      if (e.key === "Escape") {
        if (buscaAberta) setBuscaAberta(false);
        if (ajudaAberta) setAjudaAberta(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAberta, ajudaAberta]);

  async function handleRenomear(id: number, titulo: string) {
    try {
      await renomearSessao(id, titulo);
      await carregarSessoes();
    } catch (err) {
      tratar401(err);
    }
  }

  async function handleFixar(id: number, pinned: boolean) {
    try {
      await fixarSessao(id, pinned);
      await carregarSessoes();
    } catch (err) {
      tratar401(err);
    }
  }

  async function handleExcluir(id: number) {
    const sessao = sessoes.find((s) => s.id === id);
    const mensagemConfirm = sessao?.pinned
      ? "Esta sessão está fixada. Excluir mesmo assim, junto com todo o histórico?"
      : "Excluir esta sessão e todo o seu histórico?";
    if (!confirm(mensagemConfirm)) return;
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

    setMostrarFollowUp(false);
    setMensagens((prev) => [...prev, { id: novoId(), papel: "user", texto, imagens }]);
    const agentId = novoId();
    setMensagens((prev) => [...prev, { id: agentId, papel: "assistant", texto: "", vazio: true }]);

    try {
      await enviar(sessaoAtivaId, texto, imagens, (chunk) => {
        setMensagens((prev) =>
          prev.map((m) => (m.id === agentId ? { ...m, texto: m.texto + chunk, vazio: false } : m)),
        );
      });
      // Busca os ids/timestamps reais do backend (necessários pra editar/
      // regenerar) e só "cola" nas mensagens já renderizadas, por posição —
      // NUNCA substitui o array por objetos com `id` (key do React) novos,
      // senão a lista inteira desmonta/remonta e a animação de entrada
      // replay em tudo, dando a impressão de que o chat "recarregou".
      const data = await buscarSessao(sessaoAtivaId);
      setResumo(data.resumo || "");
      setMensagens((prev) =>
        prev.map((m, i) => {
          const real = data.mensagens[i];
          return real ? { ...m, msgId: real.id, criadoEm: real.criado_em } : m;
        }),
      );
    } catch (err) {
      if (tratar401(err)) return;
      const msg = err instanceof ApiError ? `⚠️ ${err.message}` : "⚠️ Falha de conexão com o backend.";
      setMensagens((prev) => prev.map((m) => (m.id === agentId ? { ...m, texto: msg, vazio: false, erro: true } : m)));
    } finally {
      carregarSessoes();
    }
  }

  async function onRegenerar() {
    if (!sessaoAtivaId) return;
    try {
      const data = await regenerarUltimaResposta(sessaoAtivaId);
      setMensagens((prev) => prev.slice(0, -2));
      setMostrarFollowUp(false);
      await onEnviarChat(data.pergunta, []);
    } catch (err) {
      tratar401(err);
    }
  }

  async function onEditarMensagem(msgId: number | undefined, novoTexto: string) {
    if (!sessaoAtivaId || !msgId) return;
    try {
      await excluirMensagemEResto(sessaoAtivaId, msgId);
      const idx = mensagens.findIndex((m) => m.msgId === msgId);
      if (idx >= 0) setMensagens((prev) => prev.slice(0, idx));
      await onEnviarChat(novoTexto, []);
    } catch (err) {
      tratar401(err);
    }
  }

  function onExportar() {
    if (!sessaoAtivaId) return;
    const sessaoAtual = sessoes.find((s) => s.id === sessaoAtivaId);
    exportarSessaoComoMarkdown(
      sessaoAtual?.titulo || "conversa",
      mensagens.map((m) => ({ papel: m.papel, conteudo: m.texto, criado_em: m.criadoEm })),
    );
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

  const ultimaAssistantId = [...mensagens].reverse().find((m) => m.papel === "assistant" && !m.vazio)?.id;

  return (
    <>
      <Header marca="Assistente Engenharia">
        <span className="user-info">
          <strong>{usuario.email}</strong>
          <span className="nivel-badge">{NIVEL_LABEL[usuario.nivel] || usuario.nivel}</span>
        </span>
        {usuario.role === "admin" && (
          <Link className="btn-sec" to="/admin">Admin</Link>
        )}
        <button className="btn-icone" title="Buscar em conversas (Ctrl+K)" onClick={() => setBuscaAberta(true)}>
          <IconBuscar />
        </button>
        <button className="btn-icone" title="Atalhos e comandos" onClick={() => setAjudaAberta(true)}>
          <IconAjuda />
        </button>
        <button className="btn-icone" title="Exportar conversa em Markdown" onClick={onExportar} disabled={!mensagens.length}>
          <IconExportar />
        </button>
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
          onFixar={handleFixar}
        />

        <div className="main">
          <div id="chat" ref={chatRef} onScroll={onScrollChat}>
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
                  <MessageBubble
                    key={m.id}
                    papel={m.papel}
                    texto={m.texto}
                    imagens={m.imagens}
                    vazio={m.vazio}
                    erro={m.erro}
                    criadoEm={m.criadoEm}
                    isUltimaAssistant={m.id === ultimaAssistantId}
                    onRegenerar={m.id === ultimaAssistantId ? onRegenerar : undefined}
                    onEditar={m.papel === "user" && m.msgId ? (novo) => onEditarMensagem(m.msgId, novo) : undefined}
                  />
                ))}
                {mostrarFollowUp && !enviando && (
                  <FollowUpChips onEscolher={(texto) => onEnviarChat(texto, [])} />
                )}
              </>
            )}
          </div>
          {naoSeguindo && !carregando && (
            <button className="scroll-to-bottom" onClick={irParaOFim}>
              <IconSeta /> Novas mensagens
            </button>
          )}
          <ChatInput ref={inputRef} enviando={enviando} onEnviar={onEnviarChat} />
        </div>
      </div>

      <PerfilModal
        aberto={perfilAberto}
        memoriaAtual={usuario.memoria}
        onFechar={() => setPerfilAberto(false)}
        onSalvar={handleSalvarMemoria}
      />
      <SearchModal aberto={buscaAberta} onFechar={() => setBuscaAberta(false)} onAbrirSessao={selecionarSessao} />
      <HelpModal aberto={ajudaAberta} onFechar={() => setAjudaAberta(false)} />
    </>
  );
}
