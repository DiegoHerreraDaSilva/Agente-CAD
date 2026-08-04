import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ApiError, changePassword } from "../lib/api";
import { useAuthContext } from "../context/AuthContext";

export default function ChangePasswordPage() {
  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [senhaConfirma, setSenhaConfirma] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const { refetch } = useAuthContext();
  const navigate = useNavigate();

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    if (senhaNova.length < 8) {
      setErro("A nova senha deve ter ao menos 8 caracteres.");
      return;
    }
    if (senhaNova !== senhaConfirma) {
      setErro("As senhas não coincidem.");
      return;
    }
    setEnviando(true);
    try {
      await changePassword(senhaAtual, senhaNova);
      await refetch();
      navigate("/", { replace: true });
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
        <h1>Troque sua senha</h1>
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
            <label htmlFor="senha-atual">Senha atual</label>
            <input
              id="senha-atual"
              type="password"
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor="senha-nova">Nova senha</label>
            <input
              id="senha-nova"
              type="password"
              placeholder="mín. 8 caracteres"
              value={senhaNova}
              onChange={(e) => setSenhaNova(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor="senha-confirma">Confirme a nova senha</label>
            <input
              id="senha-confirma"
              type="password"
              value={senhaConfirma}
              onChange={(e) => setSenhaConfirma(e.target.value)}
              required
            />
          </div>
          <motion.button className="btn-entrar" type="submit" disabled={enviando} whileTap={{ scale: 0.98 }}>
            {enviando ? "Salvando..." : "Salvar e continuar"}
          </motion.button>
        </form>
      </motion.div>
    </div>
  );
}
