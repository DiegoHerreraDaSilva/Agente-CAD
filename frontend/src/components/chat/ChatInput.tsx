import { forwardRef, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { IconArquivo, IconEnviar, IconLoader, IconTemplate } from "../icons/Icons";
import SnippetsMenu from "./SnippetsMenu";

interface ChatInputProps {
  enviando: boolean;
  onEnviar: (pergunta: string, imagens: string[]) => void;
}

const EXTENSOES_TEXTO_ACEITAS = [".txt", ".log", ".md", ".csv", ".json", ".xml"];

const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(function ChatInput(
  { enviando, onEnviar },
  ref,
) {
  const [pergunta, setPergunta] = useState("");
  const [snippetsAberto, setSnippetsAberto] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const arquivoRef = useRef<HTMLInputElement>(null);

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
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      enviar();
    }
  }

  function onEscolherSnippet(conteudo: string) {
    setPergunta((prev) => (prev.trim() ? prev + "\n" + conteudo : conteudo));
    setSnippetsAberto(false);
  }

  function processarArquivoTexto(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      const conteudo = String(reader.result ?? "");
      const bloco = `Arquivo anexado: ${file.name}\n\`\`\`\n${conteudo}\n\`\`\`\n`;
      setPergunta((prev) => (prev ? prev + "\n\n" + bloco : bloco));
    };
    reader.readAsText(file);
  }

  function onArquivoTextoSelecionado(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processarArquivoTexto(file);
    e.target.value = "";
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastando(true);
  }

  function onDragLeave(e: DragEvent<HTMLDivElement>) {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setArrastando(false);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setArrastando(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const nomeMinusculo = file.name.toLowerCase();
    if (!EXTENSOES_TEXTO_ACEITAS.some((ext) => nomeMinusculo.endsWith(ext))) return;
    processarArquivoTexto(file);
  }

  return (
    <div className="chat-input-area">
      <div className="input-toolbar">
        <input
          ref={arquivoRef}
          type="file"
          accept={EXTENSOES_TEXTO_ACEITAS.join(",")}
          style={{ display: "none" }}
          onChange={onArquivoTextoSelecionado}
        />
        <button
          type="button"
          className="btn-icone"
          title="Anexar arquivo de texto (.txt, .log...) — ou solte o arquivo aqui"
          onClick={() => arquivoRef.current?.click()}
        >
          <IconArquivo />
        </button>
        <div style={{ position: "relative" }}>
          <button
            type="button"
            className="btn-icone"
            title="Templates de prompt"
            onClick={() => setSnippetsAberto((v) => !v)}
          >
            <IconTemplate />
          </button>
          {snippetsAberto && (
            <SnippetsMenu
              perguntaAtual={pergunta}
              onEscolher={onEscolherSnippet}
              onFechar={() => setSnippetsAberto(false)}
            />
          )}
        </div>
      </div>
      <div id="barra" className={arrastando ? "arrastando" : undefined} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
        <textarea
          id="pergunta"
          ref={ref}
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
    </div>
  );
});

export default ChatInput;
