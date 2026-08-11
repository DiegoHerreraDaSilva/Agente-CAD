import { useEffect, useState } from "react";
import type { AdminUsuario, Role } from "../../lib/types";
import AnimatedOverlay from "../modal/AnimatedOverlay";

interface EditarUsuarioModalProps {
  usuario: AdminUsuario | null;
  onFechar: () => void;
  onSalvar: (patch: { email: string; role: Role }) => Promise<void>;
}

export default function EditarUsuarioModal({ usuario, onFechar, onSalvar }: EditarUsuarioModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("engineer");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (usuario) {
      setEmail(usuario.email);
      setRole(usuario.role);
    }
  }, [usuario]);

  async function salvar() {
    setSalvando(true);
    try {
      await onSalvar({ email: email.trim(), role });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <AnimatedOverlay aberto={usuario !== null} onFechar={onFechar}>
      <h3>Editar usuário</h3>
      <div className="campo">
        <label htmlFor="e-email">Email</label>
        <input id="e-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="e-role">Papel</label>
        <select id="e-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          <option value="engineer">Engenheiro</option>
          <option value="admin">Admin (TI)</option>
        </select>
      </div>
      <div className="acoes">
        <button className="btn-sec" onClick={onFechar}>Cancelar</button>
        <button className="btn-primario" onClick={salvar} disabled={salvando}>Salvar</button>
      </div>
    </AnimatedOverlay>
  );
}
