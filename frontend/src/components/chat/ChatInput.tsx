import { forwardRef, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, DragEvent, KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { IconArquivo, IconClipe, IconEnviar, IconFechar, IconLoader, IconTemplate } from "../icons/Icons";
import SnippetsMenu from "./SnippetsMenu";

interface ChatInputProps {
  enviando: boolean;
  onEnviar: (pergunta: string, imagens: string[]) => void;
}

const EXTENSOES_TEXTO_ACEITAS = [".txt", ".log", ".md", ".csv", ".json", ".xml"];
const TIPOS_IMAGEM_ACEITOS = ["image/png", "image/jpeg", "image/gif", "image/webp"];
const MAX_IMAGENS = 4;

interface Anexo {
  id: number;
  url: string;
}

const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(function ChatInput(
  { enviando, onEnviar },
  ref,
) {
  const [pergunta, setPergunta] = useState("");
  const [imagens, setImagens] = useState<Anexo[]>([]);
  const [snippetsAberto, setSnippetsAberto] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const arquivoRef = useRef<HTMLInputElement>(null);
  const imagemRef = useRef<HTMLInputElement>(null);
  const idCounterImagem = useRef(0);

  function adicionarImagem(file: File) {
    if (imagens.length >= MAX_IMAGENS) return;
    const reader = new FileReader();
    reader.onload = () => {
      const id = idCounterImagem.current++;
      setImagens((prev) => (prev.length >= MAX_IMAGENS ? prev : [...prev, { id, url: reader.result as string }]));
    };
    reader.readAsDataURL(file);
  }

  function removerImagem(id: number) {
    setImagens((prev) => prev.filter((a) => a.id !== id));
  }

  function enviar() {
    const texto = pergunta.trim();
    if ((!texto && !imagens.length) || enviando) return;
    onEnviar(texto, imagens.map((a) => a.url));
    setPergunta("");
    setImagens([]);
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

  function handlePaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const itens = e.clipboardData?.items;
    if (!itens) return;
    let achouImagem = false;
    for (const item of itens) {
      if (item.type?.startsWith("image/")) {
        achouImagem = true;
        const file = item.getAsFile();
        if (file) adicionarImagem(file);
      }
    }
    if (achouImagem) e.preventDefault();
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

  function onImagemSelecionada(e: ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files ?? []).forEach((f) => {
      if (f.type?.startsWith("image/")) adicionarImagem(f);
    });
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
    if (file.type?.startsWith("image/")) {
      adicionarImagem(file);
      return;
    }
    const nomeMinusculo = file.name.toLowerCase();
    if (!EXTENSOES_TEXTO_ACEITAS.some((ext) => nomeMinusculo.endsWith(ext))) return;
    processarArquivoTexto(file);
  }

  return (
    <>
      {imagens.length > 0 && (
        <div className="anexos-preview">
          {imagens.map((anexo) => (
            <motion.div
              className="anexo-item"
              key={anexo.id}
              layout
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.15 }}
            >
              <img src={anexo.url} alt="imagem anexada" />
              <button className="anexo-remover" title="Remover imagem" onClick={() => removerImagem(anexo.id)}>
                <IconFechar />
              </button>
            </motion.div>
          ))}
        </div>
      )}
      <div id="barra" className={arrastando ? "arrastando" : undefined} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
        <input
          ref={arquivoRef}
          type="file"
          accept={EXTENSOES_TEXTO_ACEITAS.join(",")}
          style={{ display: "none" }}
          onChange={onArquivoTextoSelecionado}
        />
        <input
          ref={imagemRef}
          type="file"
          accept={TIPOS_IMAGEM_ACEITOS.join(",")}
          multiple
          style={{ display: "none" }}
          onChange={onImagemSelecionada}
        />
        <button
          type="button"
          className="btn-icone"
          title="Anexar imagem — ou cole com Ctrl+V"
          onClick={() => imagemRef.current?.click()}
        >
          <IconClipe />
        </button>
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
        <textarea
          id="pergunta"
          ref={ref}
          rows={2}
          placeholder="Faça uma pergunta sobre CAD/NX... (cole uma imagem com Ctrl+V)"
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={handleKeyDown}
        />
        <button id="enviar" aria-label="Enviar pergunta" disabled={enviando} onClick={enviar}>
          {enviando ? <IconLoader /> : <IconEnviar />}
          <span>{enviando ? "Enviando..." : "Enviar"}</span>
        </button>
      </div>
    </>
  );
});

export default ChatInput;
