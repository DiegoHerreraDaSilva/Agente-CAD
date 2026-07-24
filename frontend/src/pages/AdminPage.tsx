import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import Header from "../components/layout/Header";
import UsersTab from "../components/admin/UsersTab";
import CacheTab from "../components/admin/CacheTab";
import KnowledgeTab from "../components/admin/KnowledgeTab";
import { logout } from "../lib/api";
import { IconBase, IconEconomia, IconUsuarios } from "../components/icons/Icons";

type Aba = "usuarios" | "cache" | "conhecimento";

export default function AdminPage() {
  const [aba, setAba] = useState<Aba>("usuarios");
  const [aviso, setAviso] = useState<{ msg: string; tipo: "ok" | "erro" } | null>(null);

  function mostrarAviso(msg: string, tipo: "ok" | "erro") {
    setAviso({ msg, tipo });
  }

  async function sair() {
    try {
      await logout();
    } finally {
      window.location.href = "/login";
    }
  }

  return (
    <>
      <Header marca="Administração">
        <Link className="btn-sec" to="/">← Voltar ao chat</Link>
        <button className="btn-sec" onClick={sair}>Sair</button>
      </Header>

      <main>
        {aviso && (
          <motion.div
            key={aviso.msg + aviso.tipo}
            className={"aviso " + aviso.tipo}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            {aviso.msg}
          </motion.div>
        )}

        <div className="tabs">
          <button className={"tab" + (aba === "usuarios" ? " ativa" : "")} onClick={() => setAba("usuarios")}>
            <IconUsuarios /> Gestão de usuários
          </button>
          <button className={"tab" + (aba === "cache" ? " ativa" : "")} onClick={() => setAba("cache")}>
            <IconEconomia /> Economia de prompt caching
          </button>
          <button className={"tab" + (aba === "conhecimento" ? " ativa" : "")} onClick={() => setAba("conhecimento")}>
            <IconBase /> Base de conhecimento
          </button>
        </div>

        <motion.div
          key={aba}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
        >
          {aba === "usuarios" && <UsersTab onAviso={mostrarAviso} />}
          {aba === "cache" && <CacheTab />}
          {aba === "conhecimento" && <KnowledgeTab onAviso={mostrarAviso} />}
        </motion.div>
      </main>
    </>
  );
}
