import { Check } from 'lucide-react';

export function OptionCard({ label, selected, onClick }) {
  return (
    <button className={`option-card ${selected ? 'selected' : ''}`} type="button" onClick={onClick}>
      <span>{label}</span>
      {selected && <Check size={18} />}
    </button>
  );
}

