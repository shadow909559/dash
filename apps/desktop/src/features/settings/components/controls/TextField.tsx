import './settings.css';

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  description,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  description?: string;
}) {
  return (
    <label className="settingsField">
      <div className="settingsField__labelRow">
        <span className="settingsField__label">{label}</span>
        {description ? <span className="settingsField__desc">{description}</span> : null}
      </div>
      <input
        className="settingsField__input"
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

