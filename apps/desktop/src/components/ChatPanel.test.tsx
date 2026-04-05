import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';

import { ChatPanel } from './ChatPanel';
import { useUiStore } from '../store/uiStore';

const ok = (data: unknown) => ({ ok: true, json: async () => data });

beforeEach(() => {
  useUiStore.setState({
    orchestratorOn: true,
    selectedProjectId: 1,
    selectedChatId: 1,
    selectedModelNames: ['m1'],
    executionMode: 'independent',
  } as any);

  (global as any).fetch = vi.fn((url: string) => {
    if (url.includes('/messages?')) return Promise.resolve(ok([]));
    if (url.includes('/assets/chat/')) return Promise.resolve(ok([]));
    if (url.includes('/orchestration/runs?')) return Promise.resolve(ok([{ id: 3, status: 'completed', graph_name: 'g', started_at: 'now' }]));
    if (url.includes('/orchestration/runs/3')) return Promise.resolve(ok({ run: { id: 3, status: 'completed' }, steps: [], final_message: null }));
    return Promise.resolve(ok({}));
  });
});

test('renders orchestration section', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ChatPanel />
    </QueryClientProvider>
  );

  expect(await screen.findByText(/Orchestration Detail/i)).toBeTruthy();
});
