/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute Rasa REST base URL. Unset in dev, where the Vite proxy is used. */
  readonly VITE_RASA_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
