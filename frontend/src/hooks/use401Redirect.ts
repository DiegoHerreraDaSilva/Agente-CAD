import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";

// Toda página autenticada precisa reagir a uma sessão expirada (401) do
// mesmo jeito: mandar de volta pro /login. Usado tanto no ChatPage quanto
// no AdminPage.
export function use401Redirect() {
  const navigate = useNavigate();
  return useCallback(
    (err: unknown): boolean => {
      if (err instanceof ApiError && err.status === 401) {
        navigate("/login", { replace: true });
        return true;
      }
      return false;
    },
    [navigate],
  );
}
