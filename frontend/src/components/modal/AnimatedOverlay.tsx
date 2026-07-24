import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface AnimatedOverlayProps {
  aberto: boolean;
  onFechar: () => void;
  children: ReactNode;
}

// Overlay + card de modal compartilhado. Só anima a ENTRADA (fade + leve
// scale) — animação de saída via AnimatePresence foi tentada e descartada:
// com overlay+card aninhados, o exit do pai fica esperando o exit do filho
// terminar e o conjunto nunca desmonta (trava com opacity:0 para sempre).
// Fechar é instantâneo, que é um comportamento seguro e comum em UIs reais.
export default function AnimatedOverlay({ aberto, onFechar, children }: AnimatedOverlayProps) {
  if (!aberto) return null;
  return (
    <motion.div
      className="overlay"
      onClick={(e) => e.target === e.currentTarget && onFechar()}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
    >
      <motion.div
        className="modal"
        role="dialog"
        aria-modal="true"
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}
