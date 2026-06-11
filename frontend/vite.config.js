// frontend/vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/schools': 'http://localhost:8000',
      '/districts': 'http://localhost:8000',
      '/anomalies': 'http://localhost:8000',
      '/pulse': 'http://localhost:8000',
      '/reports': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/whatsapp': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          maps: ['leaflet'],
          utils: ['axios', 'date-fns', 'lucide-react'],
        },
      },
    },
  },
});
