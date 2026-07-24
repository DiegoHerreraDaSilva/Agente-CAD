import { useEffect, useState } from "react";
import AnimatedOverlay from "./AnimatedOverlay";

interface PerfilModalProps {
  aberto: boolean;
  memoriaAtual: string;
  onFechar: () => void;
  onSalvar: (memoria: string) => Promise<void>;
}

export default function PerfilModal({ aberto, memoriaAtual, onFechar, onSalvar }: PerfilModalProps) {
  const [rascunho, setRascunho] = useState(memoriaAtual);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (aberto) setRascunho(memoriaAtual);
  }, [aberto, memoriaAtual]);

  async function salvar() {
    setSalvando(true);
    try {
      await onSalvar(rascunho);
      onFechar();
    } finally {
      setSalvando(false);
    }
  }

  return (
    <AnimatedOverlay aberto={aberto} onFechar={onFechar}>
      <h2>Memória pessoal</h2>
      <p className="dica">
        Anote preferências, projetos e contexto seu. O agente usa isso para personalizar as respostas.
      </p>
      <textarea
        value={rascunho}
        onChange={(e) => setRascunho(e.target.value)}
        placeholder="Ex.: Prefiro respostas curtas e diretas. Trabalho com peças de chapa e suportes estruturais..."
      />
      <div className="acoes">
        <button className="btn-sec" onClick={onFechar}>Cancelar</button>
        <button className="salvar" onClick={salvar} disabled={salvando}>Salvar</button>
      </div>
    </AnimatedOverlay>
  );
}
