/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_DASH_VERSION: string;
  readonly VITE_DASH_DOWNLOAD_URL: string;
  readonly VITE_DASH_RELEASE_URL: string;
  readonly VITE_DASH_DOCS_URL: string;
  readonly VITE_DASH_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
