// Renderizador de Markdown leve (subconjunto usado pelo modelo), portado 1:1
// da versão em JS puro que usávamos em index.html. Sem dependência externa:
// o conteúdo é sempre gerado pelo próprio Claude ou por resumos internos, e
// os testes manuais já cobrem exatamente esta sintaxe (incluindo a extensão
// de imagem em data: URL usada pelos anexos colados/anexados no chat).

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inline(s: string): string {
  // negrito antes de itálico; código inline por último
  return s
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

export function renderMarkdown(raw: string): string {
  // blocos de código ```...``` extraídos primeiro (não sofrem inline)
  const fences: string[] = [];
  let text = raw.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, (_, code) => {
    fences.push(code);
    return "@@F" + (fences.length - 1) + "@@";
  });
  text = escapeHtml(text);

  const linhas = text.split("\n");
  let html = "";
  let lista: "ul" | "ol" | null = null;
  const fecharLista = () => {
    if (lista) {
      html += "</" + lista + ">";
      lista = null;
    }
  };

  for (const linha of linhas) {
    const fence = linha.match(/^@@F(\d+)@@$/);
    if (fence) {
      fecharLista();
      html += "<pre><code>" + escapeHtml(fences[+fence[1]]) + "</code></pre>";
      continue;
    }
    const imagem = linha.match(/^!\[([^\]]*)\]\((data:image\/[a-zA-Z+]+;base64,[^)]+)\)$/);
    if (imagem) {
      fecharLista();
      html += '<img src="' + imagem[2] + '" alt="' + escapeHtml(imagem[1]) + '">';
      continue;
    }
    const titulo = linha.match(/^(#{1,6})\s+(.*)$/);
    if (titulo) {
      fecharLista();
      html += '<div class="md-h">' + inline(titulo[2]) + "</div>";
      continue;
    }
    if (/^\s*(---+|\*\*\*+)\s*$/.test(linha)) {
      fecharLista();
      html += "<hr>";
      continue;
    }
    let item = linha.match(/^\s*[-*]\s+(.*)$/);
    if (item) {
      if (lista !== "ul") {
        fecharLista();
        html += "<ul>";
        lista = "ul";
      }
      html += "<li>" + inline(item[1]) + "</li>";
      continue;
    }
    item = linha.match(/^\s*\d+\.\s+(.*)$/);
    if (item) {
      if (lista !== "ol") {
        fecharLista();
        html += "<ol>";
        lista = "ol";
      }
      html += "<li>" + inline(item[1]) + "</li>";
      continue;
    }
    if (linha.trim() === "") {
      fecharLista();
      continue;
    }
    fecharLista();
    html += "<p>" + inline(linha) + "</p>";
  }
  fecharLista();
  return html;
}

// Extrai as imagens (![](data:...)) embutidas numa mensagem persistida e
// devolve o texto restante — usado ao reidratar o histórico de sessão, já
// que o backend guarda pergunta + anexos concatenados no mesmo campo.
export function extrairImagensDoConteudo(conteudo: string): { texto: string; imagens: string[] } {
  const imgRe = /!\[[^\]]*\]\((data:image\/[a-zA-Z+]+;base64,[^)]+)\)/g;
  const imagens: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = imgRe.exec(conteudo))) imagens.push(match[1]);
  const texto = conteudo.replace(imgRe, "").trim();
  return { texto, imagens };
}
