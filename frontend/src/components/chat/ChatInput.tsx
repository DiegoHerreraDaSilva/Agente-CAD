import { useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { IconClipe, IconEnviar, IconLoader } from "../icons/Icons";

const MAX_IMAGENS = 4;

interface Anexo {
  id: number;
  url: string;
}

interface ChatInputProps {
  enviando: boolean;
  onEnviar: (pergunta: string, imagens: string[]) => void;
}

export default function ChatInput({ enviando, onEnviar }: ChatInputProps) {
  const [pergunta, setPergunta] = useState("");
  const [imagens, setImagens] = useState<Anexo[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const idCounter = useRef(0);

  function adicionarImagem(file: File) {
    if (imagens.length >= MAX_IMAGENS) return;
    const reader = new FileReader();
    reader.onload = () => {
      const id = idCounter.current++;
      setImagens((prev) => [...prev, { id, url: reader.result as string }]);
    };
    reader.readAsDataURL(file);
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

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files ?? []).forEach((f) => {
      if (f.type?.startsWith("image/")) adicionarImagem(f);
    });
    e.target.value = "";
  }

  function remover(id: number) {
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
    }
  }

  return (
    <>
      <div id="anexos" className={imagens.length ? "tem-itens" : ""}>
        {imagens.map((anexo) => (
          <motion.div
            className="anexo-item"
            key={anexo.id}
            layout
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.15 }}
          >
            <img src={anexo.url} alt="" />
            <button className="remover" title="Remover imagem" onClick={() => remover(anexo.id)}>×</button>
          </motion.div>
        ))}
      </div>
      <div id="barra">
        <input
          type="file"
          ref={fileInputRef}
          accept="image/png,image/jpeg,image/gif,image/webp"
          multiple
          hidden
          onChange={handleFileChange}
        />
        <button
          id="btn-anexar"
          type="button"
          aria-label="Anexar imagem"
          title="Anexar imagem"
          onClick={() => fileInputRef.current?.click()}
        >
          <IconClipe />
        </button>
        <textarea
          id="pergunta"
          rows={2}
          placeholder="Faça uma pergunta sobre CAD/NX... (cole uma imagem com Ctrl+V ou anexe pelo clipe)"
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
}
