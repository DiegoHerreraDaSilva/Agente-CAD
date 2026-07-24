import { renderMarkdown } from "../../lib/markdown";

export default function ResumoBox({ texto }: { texto: string }) {
  return (
    <div className="resumo-box">
      <div className="rotulo">🗜️ Resumo da conversa</div>
      <div dangerouslySetInnerHTML={{ __html: renderMarkdown(texto) }} />
    </div>
  );
}
