import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../../context/AuthContext";

// Espelha a dependência admin_atual() do backend — 403 lá vira redirect pra "/" aqui.
export default function RequireAdmin() {
  const { usuario } = useAuthContext();
  if (usuario.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}
