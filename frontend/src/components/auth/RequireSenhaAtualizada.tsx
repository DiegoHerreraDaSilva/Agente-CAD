import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../../context/AuthContext";

// Bloqueia o acesso ao chat/admin enquanto must_change_senha=true — espelha
// a dependência requer_senha_atualizada() do backend.
export default function RequireSenhaAtualizada() {
  const { usuario } = useAuthContext();
  if (usuario.must_change_senha) return <Navigate to="/change-password" replace />;
  return <Outlet />;
}
