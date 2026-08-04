// Ícones usados no app — via lucide-react (biblioteca de ícones do design
// system Schwaben). Reexportados com os nomes em português já usados nos
// componentes, para não precisar tocar em cada ponto de uso.

import { Loader2 } from "lucide-react";

export {
  SendHorizontal as IconEnviar,
  Trash2 as IconLixeira,
  Pencil as IconLapis,
  Paperclip as IconClipe,
  Inbox as IconInbox,
  MessageSquareText as IconMensagem,
  CheckCircle2 as IconAprovado,
  Clock as IconPendente,
  Users as IconUsuarios,
  Database as IconBase,
  Sparkles as IconEconomia,
  Gauge as IconMonitorado,
  KeyRound as IconSenha,
  Copy as IconCopiar,
  Check as IconCopiado,
  Search as IconBuscar,
  Plus as IconMais,
  Star as IconEstrela,
  RotateCw as IconRegenerar,
  Download as IconExportar,
  FileText as IconArquivo,
  X as IconFechar,
  LayoutTemplate as IconTemplate,
  BarChart3 as IconDashboard,
  HelpCircle as IconAjuda,
  ArrowDown as IconSeta,
} from "lucide-react";

export function IconLoader() {
  return <Loader2 className="spin" />;
}
