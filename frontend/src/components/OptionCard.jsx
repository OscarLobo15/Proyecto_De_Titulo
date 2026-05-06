import { Check } from 'lucide-react';

export function OptionCard({ description, label, selected, onClick }) {
  return (
    <button className={`option-card ${selected ? 'selected' : ''}`} type="button" onClick={onClick}>
      <span>
        {label}
        {description && <small>{description}</small>}
      </span>
      {selected && <Check size={18} />}
    </button>
  );
}
