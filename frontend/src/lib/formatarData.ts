// Timestamps vêm do Postgres como TIMESTAMPTZ (offset UTC explícito, ex.:
// "...+00:00") — Date() os interpreta corretamente e toLocaleString converte
// pro fuso horário local do navegador, no formato brasileiro (DD/MM/AAAA).
export function formatarDataHora(isoDataHora: string): string {
  if (!isoDataHora) return "";
  const d = new Date(isoDataHora);
  if (Number.isNaN(d.getTime())) return isoDataHora;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Datas "puras" sem hora (ex.: uma coluna DATE) não têm timezone — formatar
// via Date as trataria como UTC meia-noite e poderia "voltar" um dia no fuso
// local. Recorta os componentes direto da string ISO (AAAA-MM-DD) em vez disso.
export function formatarData(isoData: string): string {
  const [ano, mes, dia] = isoData.split("-");
  if (!ano || !mes || !dia) return isoData;
  return `${dia}/${mes}/${ano}`;
}
