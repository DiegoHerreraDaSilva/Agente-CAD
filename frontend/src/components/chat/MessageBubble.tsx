import { useState } from "react";
import { motion } from "framer-motion";
import { renderMarkdown } from "../../lib/markdown";
import { copiarTexto } from "../../lib/clipboard";
import TypingDots from "./TypingDots";
import { IconCopiado, IconCopiar } from "../icons/Icons";

interface MessageBubbleProps {
  papel: "user" | "assistant";
  texto: string;
  imagens?: string[];
  vazio?: boolean;
  erro?: boolean;
}

export default function MessageBubble({ papel, texto, imagens, vazio, erro }: MessageBubbleProps) {
  const [copiado, setCopiado] = useState(false);
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

  if (papel === "user") {
    return (
      <motion.div className={classe} {...entrada}>
        {texto}
        {imagens?.map((url, i) => <img key={i} src={url} alt="imagem colada" />)}
      </motion.div>
    );
  }

  if (vazio) {
    return (
      <motion.div className={classe} {...entrada}>
        <TypingDots />
      </motion.div>
    );
  }

  // Mensagens do agente (e erros) são Markdown renderizado, com botão de copiar.
  return (
    <motion.div className={classe} {...entrada}>
      {!erro && (
        <button className="btn-copiar" title="Copiar mensagem" onClick={copiar}>
          {copiado ? <IconCopiado /> : <IconCopiar />}
        </button>
      )}
      <div dangerouslySetInnerHTML={{ __html: erro ? texto : renderMarkdown(texto) }} />
    </motion.div>
  );
}
