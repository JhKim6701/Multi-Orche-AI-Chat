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
    if (url.includes('/messages?')) return Promise.resolve(ok({ items: [], scope_meta: { scope: 'active', active_segment_id: 1, selected_segment_id: 1, segment_boundaries: [] } }));
    if (url.includes('/assets/chat/')) return Promise.resolve(ok([]));
    if (url.includes('/segments?')) return Promise.resolve(ok([{ id: 1, topic_label: 'general', topic_summary: 'summary', is_active: true, parent_segment_id: null, branch_from_message_id: null }]));
    if (url.includes('/orchestration/runs?')) return Promise.resolve(ok([{ id: 3, status: 'completed', graph_name: 'g', started_at: 'now' }]));
    if (url.includes('/models/role-preferences')) return Promise.resolve(ok([
      { role: 'reviewer', preferred_model_names: ['m-review'], default_model_name: 'm-review', fallback_model_names: [] },
      { role: 'critic', preferred_model_names: ['m-critic'], default_model_name: 'm-critic', fallback_model_names: [] },
      { role: 'specialist', preferred_model_names: ['m-special'], default_model_name: 'm-special', fallback_model_names: [] },
      { role: 'orchestrator', preferred_model_names: ['m-orch'], default_model_name: 'm-orch', fallback_model_names: [] },
    ]));
    if (url.includes('/orchestration/runs/3')) return Promise.resolve(ok({ run: { id: 3, status: 'completed', routing_reason: 'test-route', reviewer_decision: 'approve', critic_model: 'm-critic', specialist_model: 'm-special' }, steps: [], final_message: { model_name: 'm-final' } }));
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
  expect(await screen.findByText(/Role mapping check/i)).toBeTruthy();
});
