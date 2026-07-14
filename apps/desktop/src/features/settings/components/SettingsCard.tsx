import React from 'react';
import './settings.css';

type SettingsCardProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
};

export function SettingsCard({ title, description, children }: SettingsCardProps) {
  return (
    <div className="settingsCard">
      <div className="settingsCard__header">
        <div className="settingsCard__title">{title}</div>
        {description ? <div className="settingsCard__desc">{description}</div> : null}
      </div>
      <div className="settingsCard__body">{children}</div>
    </div>
  );
}




