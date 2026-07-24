import type { ReactNode } from "react";

interface HeaderProps {
  marca: string;
  children?: ReactNode;
}

export default function Header({ marca, children }: HeaderProps) {
  return (
    <header>
      <img src="/logo.png" alt="Schwaben Engineering" className="logo" />
      <span className="sep" aria-hidden="true"></span>
      <span className="marca">{marca}</span>
      <span className="spacer"></span>
      {children}
    </header>
  );
}
