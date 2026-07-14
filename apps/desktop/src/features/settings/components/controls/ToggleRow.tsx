import './settings.css';

export function ToggleRow({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
}) {
  return (
    <label className="settingsToggle">
      <input
        className="settingsToggle__input"
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="settingsToggle__box" aria-hidden="true" />
      <span className="settingsToggle__content">
        <span className="settingsToggle__label">{label}</span>
        {description ? <span className="settingsToggle__desc">{description}</span> : null}
      </span>
    </label>
  );
}

