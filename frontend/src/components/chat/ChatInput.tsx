import { useState } from "react";
import type { KeyboardEvent } from "react";
import { IconEnviar, IconLoader } from "../icons/Icons";

interface ChatInputProps {
  enviando: boolean;
  onEnviar: (pergunta: string, imagens: string[]) => void;
}

export default function ChatInput({ enviando, onEnviar }: ChatInputProps) {
  const [pergunta, setPergunta] = useState("");

  function enviar() {
    const texto = pergunta.trim();
    if (!texto || enviando) return;
    onEnviar(texto, []);
    setPergunta("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  }

  return (
    <div id="barra">
      <textarea
        id="pergunta"
        rows={2}
        placeholder="Faça uma pergunta sobre CAD/NX..."
        value={pergunta}
        onChange={(e) => setPergunta(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button id="enviar" aria-label="Enviar pergunta" disabled={enviando} onClick={enviar}>
        {enviando ? <IconLoader /> : <IconEnviar />}
        <span>{enviando ? "Enviando..." : "Enviar"}</span>
      </button>
    </div>
  );
}
