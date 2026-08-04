import { useEffect, useRef, useState } from "react";
import AnimatedOverlay from "../modal/AnimatedOverlay";
import { buscarConversas } from "../../lib/api";
import type { BuscaResposta } from "../../lib/types";

interface SearchModalProps {
  aberto: boolean;
  onFechar: () => void;
  onAbrirSessao: (id: number) => void;
}

export default function SearchModal({ aberto, onFechar, onAbrirSessao }: SearchModalProps) {
  const [termo, setTermo] = useState("");
  const [resultado, setResultado] = useState<BuscaResposta | null>(null);
  const [carregando, setCarregando] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (aberto) {
      setTermo("");
      setResultado(null);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [aberto]);

  useEffect(() => {
    const t = termo.trim();
    if (t.length < 2) {
      setResultado(null);
      return;
    }
    setCarregando(true);
    const timeout = setTimeout(() => {
      buscarConversas(t)
        .then(setResultado)
        .finally(() => setCarregando(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [termo]);

  function abrir(id: number) {
    onAbrirSessao(id);
    onFechar();
  }

  return (
    <AnimatedOverlay aberto={aberto} onFechar={onFechar}>
      <div className="search-modal">
        <input
          ref={inputRef}
          className="search-input"
          placeholder="Buscar em conversas anteriores..."
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && onFechar()}
        />
        <div className="search-resultados">
          {carregando && <p className="sub">Buscando...</p>}
          {!carregando && termo.trim().length >= 2 && resultado &&
            resultado.sessoes.length === 0 && resultado.mensagens.length === 0 && (
              <p className="sub">Nenhum resultado para "{termo}".</p>
          )}
          {resultado?.sessoes.map((s) => (
            <div key={"s" + s.id} className="search-item" onClick={() => abrir(s.id)}>
              <span className="search-item-titulo">{s.titulo}</span>
              <span className="search-item-tag">sessão</span>
            </div>
          ))}
          {resultado?.mensagens.map((m) => (
            <div key={"m" + m.message_id} className="search-item" onClick={() => abrir(m.session_id)}>
              <span className="search-item-titulo">{m.session_titulo}</span>
              <span className="search-item-trecho">{m.trecho}</span>
            </div>
          ))}
        </div>
      </div>
    </AnimatedOverlay>
  );
}
