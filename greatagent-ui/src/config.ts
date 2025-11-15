const trim = (value?: string) => value?.trim() ?? "";

export const API_BASE =
  trim(import.meta.env.VITE_API_BASE) || "http://localhost:8077";

export const ENVIRONMENT_NAME = trim(import.meta.env.VITE_ENV_NAME) || "greatagent";
