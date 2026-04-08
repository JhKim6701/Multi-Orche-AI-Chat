import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { TopBar } from './TopBar';

beforeEach(() => {
  (global as any).fetch = vi.fn((url: string) => {
    if (url.includes('/system/hardware')) {
      return Promise.resolve({ ok: true, json: async () => ({ cpu_percent: 1, memory_percent: 2, disk_percent: 3, gpu_available: false, gpu_usage: null, gpu_memory: null, gpu_enabled: true }) });
    }
    if (url.includes('/system/runtime-info')) {
      return Promise.resolve({ ok: true, json: async () => ({ env: 'desktop', mode: 'desktop', data_root: '/tmp/data', upload_root: '/tmp/data/uploads', database_url: '***', qdrant_url: '***', ollama_base_url: '***', gpu_enabled: true }) });
    }
    if (url.includes('/system/readiness')) {
      return Promise.resolve({ ok: true, json: async () => ({ ready: false, env: 'desktop', unresolved_dependencies: ['ollama'], doctor_hint: 'run npm run doctor' }) });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({
        status: 'degraded',
        mode: 'desktop',
        env: 'desktop',
        checks: { database: { ok: true }, ollama: { ok: false }, qdrant: { ok: true }, upload_root: { ok: true, path: '/tmp' } },
        unresolved_dependencies: ['ollama'],
        doctor_hint: 'run npm run doctor',
      }),
    });
  });
});

test('renders readiness and recovery hint', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TopBar />
    </QueryClientProvider>
  );

  expect(await screen.findByText(/startup=blocked/i)).toBeTruthy();
  expect(await screen.findByText(/runtime=degraded/i)).toBeTruthy();
  expect(await screen.findByText(/Desktop preflight/i)).toBeTruthy();
  expect(await screen.findByText(/run npm run doctor/i)).toBeTruthy();
});
