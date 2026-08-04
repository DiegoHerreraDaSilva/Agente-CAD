const SUGESTOES = [
  "Pode detalhar mais esse ponto?",
  "Tem um exemplo prático disso?",
  "Resume isso em tópicos.",
];

interface FollowUpChipsProps {
  onEscolher: (texto: string) => void;
}

export default function FollowUpChips({ onEscolher }: FollowUpChipsProps) {
  return (
    <div className="followup-chips">
      {SUGESTOES.map((s) => (
        <button key={s} className="chip" onClick={() => onEscolher(s)}>
          {s}
        </button>
      ))}
    </div>
  );
}
