import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const devApiUrl = "http://127.0.0.1:8000";

function offlineQuicknotesShell() {
  return {
    name: "lamanotes-offline-shell",
    generateBundle(_options, bundle) {
      const files = new Set([
        "/",
        "/index.html",
        "/site.webmanifest",
        "/favicon-32.png",
      ]);
      function include(chunk) {
        if (!chunk || files.has(`/${chunk.fileName}`)) return;
        files.add(`/${chunk.fileName}`);
        for (const path of chunk.imports || []) include(bundle[path]);
      }
      for (const item of Object.values(bundle)) {
        if (
          item.type === "chunk" &&
          ((item.isEntry && item.name === "main") ||
            item.facadeModuleId
              ?.replace(/\\/g, "/")
              .endsWith("/views/Home.vue"))
        )
          include(item);
        if (
          item.type === "asset" &&
          /\.(css|woff2?|ttf|webp|png|svg|ico)$/.test(item.fileName)
        )
          files.add(`/${item.fileName}`);
      }
      const resources = [...files].sort();
      const version = createHash("sha256")
        .update(resources.join("\n"))
        .digest("hex")
        .slice(0, 16);
      this.emitFile({
        type: "asset",
        fileName: "offline-shell.json",
        source: JSON.stringify({ version, resources }),
      });
      this.emitFile({
        type: "asset",
        fileName: "sw.js",
        source: readFileSync(
          new URL("./client/public/sw.js", import.meta.url),
          "utf8",
        ).replace("__LAMANOTES_SHELL_VERSION__", version),
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), offlineQuicknotesShell()],
  root: "client",
  base: "",
  build: {
    rollupOptions: {
      input: {
        main: "client/index.html",
        privateReader: "client/private-reader.html",
      },
    },
  },
  server: {
    // LAMANOTES_PATH_PREFIX is intentionally not applied by the dev server.
    port: 8080,
    proxy: {
      "/api/": {
        target: devApiUrl,
        changeOrigin: true,
      },
      "/attachments/": {
        target: devApiUrl,
        changeOrigin: true,
      },
      "/docs": {
        target: devApiUrl,
        changeOrigin: true,
      },
      "/openapi.json": {
        target: devApiUrl,
        changeOrigin: true,
      },
      "/health": {
        target: devApiUrl,
        changeOrigin: true,
      },
    },
  },
});
