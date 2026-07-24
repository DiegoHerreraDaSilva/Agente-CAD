import { useState } from "react";
import AnimatedOverlay from "../modal/AnimatedOverlay";

interface NovaConhecimentoModalProps {
  aberto: boolean;
  onFechar: () => void;
  onSalvar: (patch: { titulo: string; conteudo: string; categoria: string }) => Promise<void>;
}

export default function NovaConhecimentoModal({ aberto, onFechar, onSalvar }: NovaConhecimentoModalProps) {
  const [titulo, setTitulo] = useState("");
  const [categoria, setCategoria] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [salvando, setSalvando] = useState(false);

  function limpar() {
    setTitulo("");
    setCategoria("");
    setConteudo("");
  }

  async function salvar() {
    setSalvando(true);
    try {
      await onSalvar({ titulo: titulo.trim(), conteudo: conteudo.trim(), categoria: categoria.trim() });
      limpar();
    } finally {
      setSalvando(false);
    }
  }

  function fechar() {
    limpar();
    onFechar();
  }

  const valido = titulo.trim() && categoria.trim() && conteudo.trim();

  return (
    <AnimatedOverlay aberto={aberto} onFechar={fechar}>
      <h3>Nova entrada na base de conhecimento</h3>
      <p className="dica">Entra direto como aprovada — já passa a valer no prompt do chat na próxima mensagem.</p>
      <div className="campo">
        <label htmlFor="k-novo-titulo">Título</label>
        <input id="k-novo-titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="k-novo-categoria">Categoria</label>
        <input id="k-novo-categoria" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="k-novo-conteudo">Conteúdo</label>
        <textarea
          id="k-novo-conteudo"
          style={{ minHeight: 280, fontFamily: "ui-monospace, Consolas, monospace", fontSize: "0.82rem" }}
          value={conteudo}
          onChange={(e) => setConteudo(e.target.value)}
        />
      </div>
      <div className="acoes">
        <button className="btn-sec" onClick={fechar}>Cancelar</button>
        <button className="btn-primario" onClick={salvar} disabled={salvando || !valido}>Criar entrada</button>
      </div>
    </AnimatedOverlay>
  );
}
