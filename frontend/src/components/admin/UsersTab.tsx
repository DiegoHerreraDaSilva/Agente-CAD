import { useEffect, useState } from "react";
import {
  adminCriarUsuario,
  adminEditarUsuario,
  adminExcluirUsuario,
  adminListarUsuarios,
  adminTrocarSenha,
  ApiError,
} from "../../lib/api";
import type { AdminUsuario, Role } from "../../lib/types";
import { use401Redirect } from "../../hooks/use401Redirect";
import { useAuthContext } from "../../context/AuthContext";
import EditarUsuarioModal from "./EditarUsuarioModal";
import TrocarSenhaModal from "./TrocarSenhaModal";
import { IconLapis, IconLixeira, IconSenha } from "../icons/Icons";

interface UsersTabProps {
  onAviso: (msg: string, tipo: "ok" | "erro") => void;
}

export default function UsersTab({ onAviso }: UsersTabProps) {
  const tratar401 = use401Redirect();
  const { usuario: eu } = useAuthContext();
  const [usuarios, setUsuarios] = useState<AdminUsuario[]>([]);
  const [editando, setEditando] = useState<AdminUsuario | null>(null);
  const [trocandoSenha, setTrocandoSenha] = useState<AdminUsuario | null>(null);

  const [novoEmail, setNovoEmail] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [novoRole, setNovoRole] = useState<Role>("engineer");
  const [criando, setCriando] = useState(false);

  async function carregar() {
    try {
      const data = await adminListarUsuarios();
      setUsuarios(data.users);
    } catch (err) {
      tratar401(err);
    }
  }

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function mensagemErro(err: unknown) {
    return err instanceof ApiError ? err.message : "Falha de conexão com o backend.";
  }

  async function criarUsuario() {
    setCriando(true);
    try {
      await adminCriarUsuario(novoEmail.trim(), novaSenha, novoRole);
      onAviso("Usuário criado.", "ok");
      setNovoEmail("");
      setNovaSenha("");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    } finally {
      setCriando(false);
    }
  }

  async function salvarEdicao(patch: { email: string; role: Role }) {
    if (!editando) return;
    try {
      await adminEditarUsuario(editando.id, patch);
      setEditando(null);
      onAviso("Usuário atualizado.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  async function excluir(u: AdminUsuario) {
    if (!confirm(`Excluir a conta de ${u.email}? Sessões e histórico de chat dele(a) somem junto. Isso não pode ser desfeito.`)) return;
    try {
      await adminExcluirUsuario(u.id);
      onAviso("Usuário excluído.", "ok");
      await carregar();
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  async function salvarSenha(senha: string) {
    if (!trocandoSenha) return;
    try {
      await adminTrocarSenha(trocandoSenha.id, senha);
      setTrocandoSenha(null);
      onAviso("Senha atualizada.", "ok");
    } catch (err) {
      if (!tratar401(err)) onAviso(mensagemErro(err), "erro");
    }
  }

  return (
    <>
      <h1 style={{ marginTop: 0 }}>Gestão de usuários</h1>
      <p className="sub">Criar contas, editar email/papel e redefinir senhas.</p>

      <div className="card">
        <h2>Novo usuário</h2>
        <div className="form-linha">
          <div className="campo">
            <label htmlFor="n-email">Email</label>
            <input id="n-email" type="email" placeholder="voce@empresa.com" value={novoEmail} onChange={(e) => setNovoEmail(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="n-senha">Senha</label>
            <input id="n-senha" type="password" placeholder="mín. 8 caracteres" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="n-role">Papel</label>
            <select id="n-role" value={novoRole} onChange={(e) => setNovoRole(e.target.value as Role)}>
              <option value="engineer">Engenheiro</option>
              <option value="admin">Admin (TI)</option>
            </select>
          </div>
          <button className="btn-primario" onClick={criarUsuario} disabled={criando}>Criar</button>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Email</th><th>Papel</th><th>Criado em</th><th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.id}>
              <td>{u.email}</td>
              <td><span className={"badge" + (u.role === "admin" ? "" : " eng")}>{u.role === "admin" ? "Admin" : "Engenheiro"}</span></td>
              <td>{(u.criado_em || "").slice(0, 10)}</td>
              <td>
                <div className="acoes">
                  <button className="btn-icone" title="Editar usuário" onClick={() => setEditando(u)}><IconLapis /></button>
                  <button className="btn-icone" title="Trocar senha" onClick={() => setTrocandoSenha(u)}><IconSenha /></button>
                  {u.id !== eu.id && (
                    <button className="btn-icone perigo" title="Excluir usuário" onClick={() => excluir(u)}><IconLixeira /></button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <EditarUsuarioModal usuario={editando} onFechar={() => setEditando(null)} onSalvar={salvarEdicao} />
      <TrocarSenhaModal usuario={trocandoSenha} onFechar={() => setTrocandoSenha(null)} onSalvar={salvarSenha} />
    </>
  );
}
