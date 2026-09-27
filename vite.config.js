import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    watch: {
      // asset builds write here constantly; reload the page manually to pick up new models
      // build artefacts only — never ignore source (an ignored src file is served stale from cache)
      ignored: ['**/renders/**', '**/tools/blender/**', '**/tools/audio/_raw/**', '**/docs/**'],
    },
  },
  build: { chunkSizeWarningLimit: 2000 },
});
