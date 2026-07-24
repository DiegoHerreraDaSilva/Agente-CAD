import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import RequireSenhaAtualizada from "./components/auth/RequireSenhaAtualizada";
import RequireAdmin from "./components/auth/RequireAdmin";
import LoginPage from "./pages/LoginPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";

// AdminPage é usado só por quem tem role=admin — carregar sob demanda evita
// incluir o bundle inteiro do painel (tabelas, modais, 3 abas) no carregamento
// do chat, que é a tela usada por todo mundo.
const ChatPage = lazy(() => import("./pages/ChatPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route path="/change-password" element={<ChangePasswordPage />} />

          <Route element={<RequireSenhaAtualizada />}>
            <Route path="/" element={<ChatPage />} />

            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<AdminPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
