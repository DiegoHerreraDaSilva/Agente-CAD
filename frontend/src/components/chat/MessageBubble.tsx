import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { renderMarkdown } from "../../lib/markdown";
import { copiarTexto } from "../../lib/clipboard";
import TypingDots from "./TypingDots";
import { IconCopiado, IconCopiar, IconLapis, IconRegenerar } from "../icons/Icons";

interface MessageBubbleProps {
  papel: "user" | "assistant";
  texto: string;
  imagens?: string[];
  vazio?: boolean;
  erro?: boolean;
  criadoEm?: string;
  isUltimaAssistant?: boolean;
  onRegenerar?: () => void;
  onEditar?: (novoTexto: string) => void;
}

function formatarHora(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function MessageBubble({
  papel,
  texto,
  imagens,
  vazio,
  erro,
  criadoEm,
  isUltimaAssistant,
  onRegenerar,
  onEditar,
}: MessageBubbleProps) {
  const [copiado, setCopiado] = useState(false);
  const [editando, setEditando] = useState(false);
  const [rascunho, setRascunho] = useState(texto);
  const [mostrarAvisoDemora, setMostrarAvisoDemora] = useState(false);

  // Sem noção de tempo, os pontinhos de "digitando" não distinguem "vai
  // responder já já" de "travou" — um aviso depois de alguns segundos ajuda.
  useEffect(() => {
    if (!vazio) {
      setMostrarAvisoDemora(false);
      return;
    }
    const timeout = setTimeout(() => setMostrarAvisoDemora(true), 6000);
    return () => clearTimeout(timeout);
  }, [vazio]);
  const classe =
    "msg " +
    (papel === "user" ? "user" : "agent") +
    (erro ? " erro" : "");

  const entrada = {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.22, ease: "easeOut" as const },
  };

  async function copiar() {
    const ok = await copiarTexto(texto);
    if (ok) {
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    }
  }

  function confirmarEdicao() {
    const novo = rascunho.trim();
    setEditando(false);
    if (novo && novo !== texto && onEditar) onEditar(novo);
  }

  function onKeyDownEdicao(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      confirmarEdicao();
    } else if (e.key === "Escape") {
      setEditando(false);
      setRascunho(texto);
    }
  }

  if (papel === "user") {
    if (editando) {
      return (
        <motion.div className={classe} {...entrada}>
          <textarea
            className="msg-editar-textarea"
            autoFocus
            rows={Math.min(6, rascunho.split("\n").length + 1)}
            value={rascunho}
            onChange={(e) => setRascunho(e.target.value)}
            onKeyDown={onKeyDownEdicao}
          />
          <div className="msg-editar-acoes">
            <button className="btn-sec" onClick={() => { setEditando(false); setRascunho(texto); }}>Cancelar</button>
            <button className="btn-primario" onClick={confirmarEdicao}>Salvar e reenviar</button>
          </div>
        </motion.div>
      );
    }
    return (
      <motion.div className={classe} {...entrada}>
        {onEditar && (
          <button className="btn-copiar btn-editar-msg" title="Editar e reenviar" onClick={() => setEditando(true)}>
            <IconLapis />
          </button>
        )}
        {texto}
        {imagens?.map((url, i) => <img key={i} src={url} alt="imagem colada" />)}
        {criadoEm && <span className="msg-timestamp">{formatarHora(criadoEm)}</span>}
      </motion.div>
    );
  }

  if (vazio) {
    return (
      <motion.div className={classe} {...entrada}>
        <TypingDots />
        {mostrarAvisoDemora && <div className="aviso-demora">Ainda processando…</div>}
      </motion.div>
    );
  }

  // Mensagens do agente (e erros) são Markdown renderizado, com botão de copiar.
  return (
    <motion.div className={classe} {...entrada}>
      {!erro && (
        <div className="msg-acoes">
          <button className="btn-copiar" title="Copiar mensagem" onClick={copiar}>
            {copiado ? <IconCopiado /> : <IconCopiar />}
          </button>
          {isUltimaAssistant && onRegenerar && (
            <button className="btn-copiar" title="Regenerar resposta" onClick={onRegenerar}>
              <IconRegenerar />
            </button>
          )}
        </div>
      )}
      <div dangerouslySetInnerHTML={{ __html: erro ? texto : renderMarkdown(texto) }} />
      {criadoEm && <span className="msg-timestamp">{formatarHora(criadoEm)}</span>}
    </motion.div>
  );
}
