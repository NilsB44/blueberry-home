import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			// Built as a single-page app: Caddy serves the files and falls back to index.html.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		// In development the API runs on :8000; proxy so cookies stay same-origin.
		proxy: { '/api': 'http://localhost:8000' }
	}
});
