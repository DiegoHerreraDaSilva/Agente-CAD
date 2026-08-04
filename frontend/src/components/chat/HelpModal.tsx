import AnimatedOverlay from "../modal/AnimatedOverlay";

interface HelpModalProps {
  aberto: boolean;
  onFechar: () => void;
}

const ATALHOS = [
  { tecla: "Ctrl+K", desc: "Buscar em conversas anteriores" },
  { tecla: "Ctrl+N", desc: "Criar uma nova sessão" },
  { tecla: "/", desc: "Focar no campo de pergunta" },
  { tecla: "?", desc: "Abrir esta ajuda" },
  { tecla: "Esc", desc: "Fechar a busca ou um modal aberto" },
  { tecla: "Enter", desc: "Enviar a mensagem" },
  { tecla: "Shift+Enter", desc: "Quebrar linha sem enviar" },
];

const COMANDOS = [
  { comando: "/compact", desc: "Resume a conversa atual e libera contexto, enviando o resumo para aprovação na base de conhecimento" },
];

export default function HelpModal({ aberto, onFechar }: HelpModalProps) {
  return (
    <AnimatedOverlay aberto={aberto} onFechar={onFechar}>
      <h2 style={{ marginTop: 0 }}>Atalhos e comandos</h2>

      <h3 className="ajuda-subtitulo">Atalhos de teclado</h3>
      <table className="ajuda-tabela">
        <tbody>
          {ATALHOS.map((a) => (
            <tr key={a.tecla}>
              <td><kbd>{a.tecla}</kbd></td>
              <td>{a.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="ajuda-subtitulo">Comandos no chat</h3>
      <table className="ajuda-tabela">
        <tbody>
          {COMANDOS.map((c) => (
            <tr key={c.comando}>
              <td><kbd>{c.comando}</kbd></td>
              <td>{c.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
        <button className="btn-primario" onClick={onFechar}>Fechar</button>
      </div>
    </AnimatedOverlay>
  );
}
