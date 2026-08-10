import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTheme } from "next-themes";
import ThemeToggle from "./ThemeToggle";

interface HeaderProps {
  marca: string;
  children?: ReactNode;
}

export default function Header({ marca, children }: HeaderProps) {
  const { resolvedTheme } = useTheme();
  // Mesma guarda de montagem do ThemeToggle: resolvedTheme só vem do tema
  // salvo/preferido do sistema depois do mount — antes disso, usa a logo
  // escura (o padrão do app) para não trocar de imagem visivelmente ao carregar.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);
  const logoClara = montado && resolvedTheme === "light";

  return (
    <header>
      <img src={logoClara ? "/logo-light.png" : "/logo.png"} alt="Schwaben Engineering" className="logo" />
      <span className="sep" aria-hidden="true"></span>
      <span className="marca">{marca}</span>
      <span className="spacer"></span>
      <ThemeToggle />
      {children}
    </header>
  );
}
