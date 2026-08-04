import { useEffect, useRef, useState } from "react";
import { criarSnippet, excluirSnippet, listarSnippets } from "../../lib/api";
import type { Snippet } from "../../lib/types";
import { IconLixeira, IconMais } from "../icons/Icons";

interface SnippetsMenuProps {
  perguntaAtual: string;
  onEscolher: (conteudo: string) => void;
  onFechar: () => void;
}

export default function SnippetsMenu({ perguntaAtual, onEscolher, onFechar }: SnippetsMenuProps) {
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [tituloNovo, setTituloNovo] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listarSnippets().then((d) => setSnippets(d.snippets)).catch(() => {});
  }, []);

  useEffect(() => {
    function onClickFora(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onFechar();
    }
    document.addEventListener("mousedown", onClickFora);
    return () => document.removeEventListener("mousedown", onClickFora);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function salvarAtual() {
    const titulo = tituloNovo.trim();
    if (!titulo || !perguntaAtual.trim()) return;
    const s = await criarSnippet(titulo, perguntaAtual.trim());
    setSnippets((prev) => [s, ...prev]);
    setTituloNovo("");
    setSalvando(false);
  }

  async function remover(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    await excluirSnippet(id);
    setSnippets((prev) => prev.filter((s) => s.id !== id));
  }

  return (
    <div className="snippets-menu card" ref={ref}>
      <div className="snippets-cabecalho">Templates de prompt</div>
      {snippets.length === 0 && !salvando && (
        <p className="snippets-vazio">Nenhum template salvo ainda.</p>
      )}
      <div className="snippets-lista">
        {snippets.map((s) => (
          <div key={s.id} className="snippet-item" onClick={() => onEscolher(s.conteudo)}>
            <span className="snippet-titulo">{s.titulo}</span>
            <button className="acao lixeira" title="Excluir template" onClick={(e) => remover(s.id, e)}>
              <IconLixeira />
            </button>
          </div>
        ))}
      </div>
      {salvando ? (
        <div className="snippet-salvar">
          <input
            autoFocus
            placeholder="Nome do template"
            value={tituloNovo}
            onChange={(e) => setTituloNovo(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && salvarAtual()}
          />
          <button className="btn-primario" onClick={salvarAtual}>Salvar</button>
        </div>
      ) : (
        <button
          className="btn-sec snippet-btn-novo"
          disabled={!perguntaAtual.trim()}
          title={perguntaAtual.trim() ? "Salvar o texto atual do input como template" : "Escreva algo no input para salvar como template"}
          onClick={() => setSalvando(true)}
        >
          <IconMais /> Salvar texto atual como template
        </button>
      )}
    </div>
  );
}
