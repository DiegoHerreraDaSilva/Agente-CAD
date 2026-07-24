import { useCallback, useState } from "react";
import { enviarMensagem } from "../lib/api";

// Encapsula o streaming SSE de uma resposta do /chat — unidade pequena e
// autocontida (não depende de estado de sessões/sidebar), por isso vive
// separada da página.
export function useChatStream() {
  const [enviando, setEnviando] = useState(false);

  const enviar = useCallback(
    async (sessionId: number, pergunta: string, imagens: string[], onChunk: (texto: string) => void) => {
      setEnviando(true);
      try {
        await enviarMensagem(sessionId, pergunta, imagens, onChunk);
      } finally {
        setEnviando(false);
      }
    },
    [],
  );

  return { enviando, enviar };
}
