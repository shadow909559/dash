import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ChatPage } from './features/chat/ChatPage';
import { SettingsPage } from './features/settings/SettingsPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/chat" replace />} />

        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}


