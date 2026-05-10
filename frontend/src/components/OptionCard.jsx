import { Check } from 'lucide-react';

export function OptionCard({ description, label, selected, onClick }) {
  return (
    <button
      aria-pressed={selected}
      className={`option-card${selected ? ' selected' : ''}`}
      type="button"
      onClick={onClick}
    >
      <span className="option-card-border top" aria-hidden="true" />
      <span className="option-card-border right" aria-hidden="true" />
      <span className="option-card-border bottom" aria-hidden="true" />
      <span className="option-card-border left" aria-hidden="true" />
      <span className="option-card-title">{label}</span>
      {description && <span className="option-card-desc">{description}</span>}
      <span className="option-card-indicator" aria-hidden="true">
        {selected && <Check size={10} strokeWidth={3} />}
      </span>
    </button>
  );
}
