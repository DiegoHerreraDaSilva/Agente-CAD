import { createContext, useContext } from "react";
import type { Usuario } from "../lib/types";

export interface AuthContextValue {
  usuario: Usuario;
  refetch: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuthContext deve ser usado dentro de <RequireAuth>");
  return ctx;
}
