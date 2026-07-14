import './settings.css';

export function SliderField({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  description,
  formatValue,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  description?: string;
  formatValue?: (value: number) => string;
}) {
  return (
    <label className="settingsField">
      <div className="settingsField__labelRow">
        <span className="settingsField__label">{label}</span>
        {description ? <span className="settingsField__desc">{description}</span> : null}
      </div>
      <div className="settingsSliderRow">
        <input
          className="settingsSlider"
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className="settingsSliderValue">{formatValue ? formatValue(value) : value}</span>
      </div>
    </label>
  );
}

