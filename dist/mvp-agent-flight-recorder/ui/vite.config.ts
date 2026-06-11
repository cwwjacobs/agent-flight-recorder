import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend mirrors its API under /api specifically for this proxy and for
// same-origin production serving from ui/dist.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8700",
    },
  },
});
