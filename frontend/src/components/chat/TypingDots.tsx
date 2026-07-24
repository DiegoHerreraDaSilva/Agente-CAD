import { motion } from "framer-motion";

const pontoVariants = {
  animar: (i: number) => ({
    y: [0, -4, 0],
    transition: { duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" as const },
  }),
};

export default function TypingDots() {
  return (
    <div className="typing-dots" aria-label="Digitando">
      {[0, 1, 2].map((i) => (
        <motion.span key={i} custom={i} variants={pontoVariants} animate="animar" />
      ))}
    </div>
  );
}
