// Copia texto pra área de transferência com fallback: a Clipboard API
// moderna exige contexto seguro/permissão e falha em alguns ambientes
// restritos; document.execCommand("copy") funciona numa gama maior de
// navegadores/contextos como plano B.
export async function copiarTexto(texto: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return true;
    } catch {
      /* cai pro fallback abaixo */
    }
  }
  try {
    const el = document.createElement("textarea");
    el.value = texto;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.focus();
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}
