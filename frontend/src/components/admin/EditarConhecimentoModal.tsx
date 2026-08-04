import { useEffect, useState } from "react";
import type { KnowledgeEntry } from "../../lib/types";
import AnimatedOverlay from "../modal/AnimatedOverlay";
import { formatarDataHora } from "../../lib/formatarData";

interface EditarConhecimentoModalProps {
  entrada: KnowledgeEntry | null;
  onFechar: () => void;
  onSalvar: (patch: { titulo: string; conteudo: string; categoria: string }) => Promise<void>;
}

export default function EditarConhecimentoModal({ entrada, onFechar, onSalvar }: EditarConhecimentoModalProps) {
  const [titulo, setTitulo] = useState("");
  const [categoria, setCategoria] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (entrada) {
      setTitulo(entrada.titulo);
      setCategoria(entrada.categoria);
      setConteudo(entrada.conteudo);
    }
  }, [entrada]);

  async function salvar() {
    setSalvando(true);
    try {
      await onSalvar({ titulo: titulo.trim(), conteudo, categoria: categoria.trim() });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <AnimatedOverlay aberto={entrada !== null} onFechar={onFechar}>
      <h3>{entrada?.status === "aprovado" ? "Editar entrada aprovada" : "Revisar entrada pendente"}</h3>
      {entrada && (
        <p className="dica">
          Enviado por {entrada.criado_por} em {formatarDataHora(entrada.criado_em || "")}.
        </p>
      )}
      <div className="campo">
        <label htmlFor="k-titulo">Título</label>
        <input id="k-titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="k-categoria">Categoria</label>
        <input id="k-categoria" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="k-conteudo">Conteúdo completo</label>
        <textarea
          id="k-conteudo"
          style={{ minHeight: 280, fontFamily: "ui-monospace, Consolas, monospace", fontSize: "0.82rem" }}
          value={conteudo}
          onChange={(e) => setConteudo(e.target.value)}
        />
      </div>
      <div className="acoes">
        <button className="btn-sec" onClick={onFechar}>Cancelar</button>
        <button className="btn-primario" onClick={salvar} disabled={salvando}>Salvar</button>
      </div>
    </AnimatedOverlay>
  );
}
