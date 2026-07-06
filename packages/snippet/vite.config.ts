import { defineConfig } from "vite";
import { resolve } from "path";

// Build target: a single <50KB gzipped file, zero runtime dependencies.
export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "MemoraAgent",
      fileName: () => "agent.js",
      formats: ["iife"],
    },
    minify: "esbuild",
    sourcemap: true,
  },
});
