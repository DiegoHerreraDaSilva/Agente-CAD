import type { Mensagem } from "./types";

export function exportarSessaoComoMarkdown(titulo: string, mensagens: Mensagem[]): void {
  const linhas = [`# ${titulo}`, ""];
  for (const m of mensagens) {
    const autor = m.papel === "user" ? "**Engenheiro**" : "**Consultor**";
    linhas.push(autor + (m.criado_em ? ` (${new Date(m.criado_em).toLocaleString("pt-BR")})` : ""), "", m.conteudo, "");
  }
  const blob = new Blob([linhas.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${titulo.replace(/[^\w\-À-ÿ ]/g, "").trim() || "conversa"}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
