import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { TopBar } from './TopBar';

global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ cpu_percent: 1, memory_percent: 2, disk_percent: 3, gpu_available: false }) }) as any;

test('renders hardware labels', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TopBar />
    </QueryClientProvider>
  );
  expect(await screen.findByText(/CPU/i)).toBeInTheDocument();
});
