import './settings.css';

export function SelectField({
  label,
  value,
  onChange,
  options,
  description,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  description?: string;
}) {
  return (
    <label className="settingsField">
      <div className="settingsField__labelRow">
        <span className="settingsField__label">{label}</span>
        {description ? <span className="settingsField__desc">{description}</span> : null}
      </div>
      <select className="settingsField__input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

