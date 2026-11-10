/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // En développement, l'API FastAPI tourne sur le port 8000 : pas de souci de CORS.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Fuseau fixe : les tests de périodes (« hier », changement d'heure) donnent le même
    // résultat sur toutes les machines et en CI.
    env: { TZ: "Europe/Brussels" },
  },
});
