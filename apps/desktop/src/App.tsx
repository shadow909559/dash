import { APP_NAME, API_ROUTES } from '@dash/shared';
import { DashClient } from '@dash/sdk';
import './App.css';

const backendUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
const client = new DashClient({ baseUrl: backendUrl });

export default function App() {
  const platform = window.dash?.platform ?? 'unknown';

  return (
    <main className="app">
      <header className="app__header">
        <h1>{APP_NAME}</h1>
        <p className="app__subtitle">AI Desktop Assistant</p>
      </header>

      <section className="app__card">
        <h2>Foundation Milestone</h2>
        <ul>
          <li>
            <strong>Platform:</strong> {platform}
          </li>
          <li>
            <strong>Backend:</strong> {backendUrl}
          </li>
          <li>
            <strong>Health endpoint:</strong> {API_ROUTES.HEALTH}
          </li>
          <li>
            <strong>WebSocket:</strong> {API_ROUTES.WEBSOCKET}
          </li>
          <li>
            <strong>Client version:</strong> {client.version}
          </li>
        </ul>
      </section>
    </main>
  );
}
