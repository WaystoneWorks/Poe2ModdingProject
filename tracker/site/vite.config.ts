/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// One index.html with the script and the styles inline, so the site also opens from a file:// URL
// (module scripts and fetch do not work there). data.js, written by `cargo xtask tracker build`,
// is a classic script next to it.
function inlineAssets(): Plugin {
  return {
    name: 'inline-assets',
    enforce: 'post',
    generateBundle(_, bundle) {
      const html = Object.values(bundle).find((f) => f.type === 'asset' && f.fileName === 'index.html');
      if (!html || html.type !== 'asset') return;
      let text = String(html.source);
      for (const [name, file] of Object.entries(bundle)) {
        if (file.type === 'chunk' && name.endsWith('.js')) {
          const re = new RegExp(`<script[^>]*src="[^"]*${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*></script>`);
          text = text.replace(re, () => `<script type="module">${file.code.replace(/<\/script/g, '<\\/script')}</script>`);
          delete bundle[name];
        } else if (file.type === 'asset' && name.endsWith('.css')) {
          const re = new RegExp(`<link[^>]*href="[^"]*${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>`);
          text = text.replace(re, () => `<style>${String(file.source)}</style>`);
          delete bundle[name];
        }
      }
      html.source = text;
    },
  };
}

export default defineConfig({
  plugins: [svelte(), inlineAssets()],
  base: './',
  build: {
    outDir: process.env.TRACKER_OUT ?? 'dist',
    emptyOutDir: true,
    sourcemap: false,
    modulePreload: false,
  },
  test: { include: ['src/**/*.test.ts'] },
});
