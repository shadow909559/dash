import { ReactNode } from 'react';
import './settings.css';

export function SettingsLayout({
  nav,
  children,
}: {
  nav: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="settings">
      <aside className="settings__nav">{nav}</aside>
      <main className="settings__main">{children}</main>
    </div>
  );
}

