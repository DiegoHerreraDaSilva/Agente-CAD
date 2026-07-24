import { useCallback, useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { me } from "../../lib/api";
import type { Usuario } from "../../lib/types";
import { AuthContext } from "../../context/AuthContext";

// Porta a lógica de carregarUsuario()/guard() que existia em cada HTML
// (index.html, admin.html): busca /auth/me uma vez e disponibiliza o
// usuário via contexto para as rotas aninhadas, sem refazer o fetch a cada
// página.
export default function RequireAuth() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [status, setStatus] = useState<"carregando" | "ok" | "nao-autenticado">("carregando");
  const location = useLocation();

  const carregar = useCallback(async () => {
    try {
      const u = await me();
      setUsuario(u);
      setStatus("ok");
    } catch {
      setStatus("nao-autenticado");
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (status === "carregando") return null;
  if (status === "nao-autenticado") {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <AuthContext.Provider value={{ usuario: usuario!, refetch: carregar }}>
      <Outlet />
    </AuthContext.Provider>
  );
}
