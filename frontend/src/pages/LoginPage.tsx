import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ApiError, login } from "../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const navigate = useNavigate();

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const resp = await login(email.trim(), senha);
      navigate(resp.must_change_senha ? "/change-password" : "/", { replace: true });
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Falha de conexão com o backend.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="pagina-auth">
      <motion.div
        className="cartao-auth card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        <div className="logo-wrap">
          <img src="/logo.png" alt="Schwaben Engineering" />
        </div>
        <h1>Assistente Engenharia</h1>
        {erro && (
          <motion.div
            className="erro"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            transition={{ duration: 0.15 }}
          >
            {erro}
          </motion.div>
        )}
        <form onSubmit={enviar}>
          <div className="campo">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              placeholder="voce@empresa.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor="senha">Senha</label>
            <input
              id="senha"
              type="password"
              placeholder="••••••••"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
          </div>
          <motion.button className="btn-entrar" type="submit" disabled={enviando} whileTap={{ scale: 0.98 }}>
            {enviando ? "Entrando..." : "Entrar"}
          </motion.button>
        </form>
        <p className="rodape">Não tem conta? Peça a um administrador (TI).</p>
      </motion.div>
    </div>
  );
}
