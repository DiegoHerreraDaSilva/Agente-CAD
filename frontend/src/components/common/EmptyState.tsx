import type { ReactNode } from "react";
import { motion } from "framer-motion";

interface EmptyStateProps {
  icone: ReactNode;
  titulo: string;
  texto?: string;
}

export default function EmptyState({ icone, titulo, texto }: EmptyStateProps) {
  return (
    <motion.div
      className="empty-state"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      {icone}
      <div className="titulo">{titulo}</div>
      {texto && <div className="texto">{texto}</div>}
    </motion.div>
  );
}
