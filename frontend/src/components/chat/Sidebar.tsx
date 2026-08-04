import { useState } from "react";
import type { KeyboardEvent } from "react";
import { motion } from "framer-motion";
import type { SessaoResumo } from "../../lib/types";
import { IconEstrela, IconLapis, IconLixeira } from "../icons/Icons";

interface SidebarProps {
  sessoes: SessaoResumo[];
  sessaoAtiva: number | null;
  carregando?: boolean;
  onSelecionar: (id: number) => void;
  onNova: () => void;
  onRenomear: (id: number, titulo: string) => void;
  onExcluir: (id: number) => void;
  onFixar: (id: number, pinned: boolean) => void;
}

export default function Sidebar({ sessoes, sessaoAtiva, carregando, onSelecionar, onNova, onRenomear, onExcluir, onFixar }: SidebarProps) {
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [rascunho, setRascunho] = useState("");

  function iniciarEdicao(s: SessaoResumo) {
    setEditandoId(s.id);
    setRascunho(s.titulo);
  }

  function confirmarEdicao(s: SessaoResumo) {
    setEditandoId(null);
    const novo = rascunho.trim() || s.titulo;
    if (novo !== s.titulo) onRenomear(s.id, novo);
  }

  function onKeyDownEdicao(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      (e.target as HTMLInputElement).blur();
    } else if (e.key === "Escape") {
      setEditandoId(null);
    }
  }

  const fixadas = sessoes.filter((s) => s.pinned);
  const outras = sessoes.filter((s) => !s.pinned);

  function renderSessao(s: SessaoResumo) {
    return (
      <motion.div
        key={s.id}
        className={"sessao-item" + (s.id === sessaoAtiva ? " ativa" : "")}
        onClick={() => onSelecionar(s.id)}
        whileHover={{ x: 2 }}
        whileTap={{ scale: 0.98 }}
        transition={{ duration: 0.12 }}
      >
        {s.id === sessaoAtiva && (
          <motion.div className="barra-ativa" layoutId="sessao-barra-ativa" transition={{ duration: 0.2 }} />
        )}
        {editandoId === s.id ? (
          <input
            className="titulo-input"
            autoFocus
            value={rascunho}
            onChange={(e) => setRascunho(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onBlur={() => confirmarEdicao(s)}
            onKeyDown={onKeyDownEdicao}
          />
        ) : (
          <span className="titulo" onDoubleClick={(e) => { e.stopPropagation(); iniciarEdicao(s); }}>
            {s.titulo}
          </span>
        )}
        <button
          className={"acao fixar" + (s.pinned ? " ativo" : "")}
          title={s.pinned ? "Desafixar sessão" : "Fixar sessão"}
          onClick={(e) => { e.stopPropagation(); onFixar(s.id, !s.pinned); }}
        >
          <IconEstrela />
        </button>
        <button
          className="acao editar"
          title="Renomear sessão"
          onClick={(e) => { e.stopPropagation(); iniciarEdicao(s); }}
        >
          <IconLapis />
        </button>
        <button
          className="acao lixeira"
          title="Excluir sessão"
          onClick={(e) => { e.stopPropagation(); onExcluir(s.id); }}
        >
          <IconLixeira />
        </button>
      </motion.div>
    );
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <motion.button className="btn-nova" onClick={onNova} whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }}>
          + Nova sessão
        </motion.button>
      </div>
      <div className="sessao-lista">
        {carregando && !sessoes.length ? (
          <>
            <div className="skeleton skeleton-sessao" />
            <div className="skeleton skeleton-sessao" />
            <div className="skeleton skeleton-sessao" />
          </>
        ) : (
          <>
            {fixadas.length > 0 && (
              <>
                <div className="sessao-lista-titulo">Fixadas</div>
                {fixadas.map(renderSessao)}
                <div className="sessao-lista-titulo">Recentes</div>
              </>
            )}
            {outras.map(renderSessao)}
          </>
        )}
      </div>
    </aside>
  );
}
