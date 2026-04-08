import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';

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
    if (url.includes('/assets/chat/') && url.includes('retrieval-preview')) return Promise.resolve(ok({ hits: [{ chunk_id: 1, asset_id: 9, filename: 'doc.pdf', chunk_index: 0, page: 1, snippet: 'sample', score: 0.9, retrieval_mode: 'hybrid', vector_score: 0.8, lexical_score: 0.7 }], packed_context: 'context', packed_meta: { retrieval_mode: 'hybrid', used_chunk_ids: [1], ocr_used: false }, scope: { project_id: 1, chat_thread_id: 1 } }));
    if (url.includes('/assets/chat/')) return Promise.resolve(ok([{ id: 9, original_filename: 'doc.pdf', source_type: 'user_upload', derived_metadata_json: { ingest_status: 'indexed', chunk_count: 2, ingest_pipeline: { failed: false } } }]));
    if (url.includes('/segments?')) return Promise.resolve(ok([{ id: 1, topic_label: 'general', topic_summary: 'summary', is_active: true, parent_segment_id: null, branch_from_message_id: null }]));
    if (url.includes('/orchestration/runs?')) return Promise.resolve(ok([{ id: 3, status: 'completed', graph_name: 'g', started_at: 'now' }]));
    if (url.includes('/models/role-preferences')) return Promise.resolve(ok([
      { role: 'reviewer', preferred_model_names: ['m-review'], default_model_name: 'm-review', fallback_model_names: [] },
      { role: 'critic', preferred_model_names: ['m-critic'], default_model_name: 'm-critic', fallback_model_names: [] },
      { role: 'specialist', preferred_model_names: ['m-special'], default_model_name: 'm-special', fallback_model_names: [] },
      { role: 'orchestrator', preferred_model_names: ['m-orch'], default_model_name: 'm-orch', fallback_model_names: [] },
      { role: 'final_responder', preferred_model_names: ['m-final'], default_model_name: 'm-final', fallback_model_names: [] },
    ]));
    if (url.includes('/system/health')) return Promise.resolve(ok({ status: 'ok', mode: 'desktop', unresolved_dependencies: [], checks: { db: { ok: true }, qdrant: { ok: false } } }));
    if (url.includes('/orchestration/runs/3')) return Promise.resolve(ok({
      run: { id: 3, status: 'approval_pending', approval_status: 'pending', routing_reason: 'test-route', reviewer_decision: 'approve', critic_model: 'm-critic', specialist_model: 'm-special', final_publish_status: 'pending' },
      steps: [{ id: 11, step_name: 'reviewer', assigned_role: 'reviewer', status: 'running', model_name: 'm-review', routing_reason: 'policy', reviewer_decision: 'approve', retry_count: 1, fallback_model_name: 'm-fallback', fallback_reason: 'timeout', used_asset_ids: [9], used_chunk_ids: [1], approval_status: 'pending', step_metadata: { node: 'reviewer' } }],
      final_message: { model_name: 'm-final', content_markdown: 'done' }
    }));
    return Promise.resolve(ok({}));
  });
});

test('renders orchestration detail with role mapping regression fields', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ChatPanel />
    </QueryClientProvider>
  );

  expect(await screen.findByText(/Orchestration Detail/i)).toBeTruthy();
  expect(await screen.findByText(/Role mapping check/i)).toBeTruthy();
  expect(await screen.findByText(/status=approval_pending/i)).toBeTruthy();
  expect(await screen.findByText(/Final responder model=m-final/i)).toBeTruthy();
});

test('opens visual drawer and renders step metadata', async () => {
  render(<QueryClientProvider client={new QueryClient()}><ChatPanel /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: /#3 completed/i }));
  expect(await screen.findByText(/Orchestration Visual Panel/i)).toBeTruthy();
  expect(await screen.findByText(/routing=test-route/i)).toBeTruthy();
  expect(await screen.findByText(/retry=1 · fallback=m-fallback/i)).toBeTruthy();
});

test('renders approval pending alert and status badges', async () => {
  render(<QueryClientProvider client={new QueryClient()}><ChatPanel /></QueryClientProvider>);
  expect(await screen.findByText(/승인 전 draft/i)).toBeTruthy();
  expect(await screen.findByText(/approval=pending/i)).toBeTruthy();
  expect(await screen.findByText(/publish=pending/i)).toBeTruthy();
});

test('toggles diagnostics and retrieval preview', async () => {
  render(<QueryClientProvider client={new QueryClient()}><ChatPanel /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: /Show Diagnostics/i }));
  expect(await screen.findByText(/status=ok · mode=desktop/i)).toBeTruthy();

  fireEvent.change(screen.getByPlaceholderText('Type message...'), { target: { value: 'query for retrieval' } });
  fireEvent.click(screen.getByRole('button', { name: /Show Retrieval Preview/i }));
  expect(await screen.findByText(/doc.pdf/i)).toBeTruthy();
  expect(await screen.findByText(/packed context preview/i)).toBeTruthy();
});
