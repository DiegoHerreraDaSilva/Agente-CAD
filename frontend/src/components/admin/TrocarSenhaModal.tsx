import { useState } from "react";
import type { AdminUsuario } from "../../lib/types";
import AnimatedOverlay from "../modal/AnimatedOverlay";

interface TrocarSenhaModalProps {
  usuario: AdminUsuario | null;
  onFechar: () => void;
  onSalvar: (senha: string) => Promise<void>;
}

export default function TrocarSenhaModal({ usuario, onFechar, onSalvar }: TrocarSenhaModalProps) {
  const [senha, setSenha] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar() {
    setSalvando(true);
    try {
      await onSalvar(senha);
      setSenha("");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <AnimatedOverlay aberto={usuario !== null} onFechar={onFechar}>
      <h3>Trocar senha</h3>
      <div className="campo">
        <label htmlFor="s-senha">Nova senha</label>
        <input
          id="s-senha"
          type="password"
          placeholder="mín. 8 caracteres"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
        />
      </div>
      <div className="acoes">
        <button className="btn-sec" onClick={onFechar}>Cancelar</button>
        <button className="btn-primario" onClick={salvar} disabled={salvando}>Salvar</button>
      </div>
    </AnimatedOverlay>
  );
}
