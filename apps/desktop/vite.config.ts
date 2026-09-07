import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import electron from "vite-plugin-electron";
import path from "node:path";

export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        entry: "electron/main.ts",
        onstart(options) {
          options.startup();
        },
        vite: {
          build: {
            outDir: "dist-electron",
            rollupOptions: {
              external: ["electron", "electron-updater"],
            },
          },
        },
      },
      {
        entry: "electron/preload.ts",
        onstart(args) {
          args.reload();
        },
        vite: {
          build: {
            outDir: "dist-electron",
            rollupOptions: {
              external: ["electron"],
            },
          },
        },
      },
]),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  // Remove invalid platform configuration
  // platform: "browser", // This was causing the warning
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Code splitting and optimization
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        orb: path.resolve(__dirname, "orb.html"),
      },
      output: {
manualChunks: {
          // Split vendor code
          "react-vendor": ["react", "react-dom"],
          "framer-motion": ["framer-motion"],
          "zustand": ["zustand"],
          "lucide-react": ["lucide-react"],
          "r3f": ["@react-three/fiber", "@react-three/drei", "@react-three/postprocessing", "postprocessing"],
        },
      },
    },
    // Optimize chunk size
    chunkSizeWarningLimit: 1000,
  },
// Optimize dependencies
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "framer-motion",
      "zustand",
      "lucide-react",
      "three",
      "@react-three/fiber",
      "@react-three/drei",
      "@react-three/postprocessing",
      "postprocessing",
    ],
  },
  // Performance hints
  server: {
    hmr: {
      overlay: false,
    },
  },
});