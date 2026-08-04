import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // Evita mismatch de hidratação: só renderiza o ícone certo depois do mount,
  // quando next-themes já resolveu o tema salvo/preferido do sistema.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  if (!montado) return <span className="theme-toggle" aria-hidden />;

  const escuro = resolvedTheme === "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={escuro ? "Mudar para tema claro" : "Mudar para tema escuro"}
      title={escuro ? "Tema claro" : "Tema escuro"}
      onClick={() => setTheme(escuro ? "light" : "dark")}
    >
      {escuro ? <Sun /> : <Moon />}
    </button>
  );
}
