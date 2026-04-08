import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { ModelPanel, buildRolePreferenceIndex } from './ModelPanel';
import { useUiStore } from '../store/uiStore';

const ok = (data: unknown) => ({ ok: true, json: async () => data });

const models = [
  {
    id: 1,
    model_name: 'm1',
    downloaded: true,
    enabled: true,
    sort_order: 1,
    supports_vision: false,
    supports_reasoning: true,
    supports_embeddings: true,
    preferred_roles_json: ['orchestrator'],
  },
  {
    id: 2,
    model_name: 'm2',
    downloaded: true,
    enabled: true,
    sort_order: 2,
    supports_vision: true,
    supports_reasoning: false,
    supports_embeddings: false,
    preferred_roles_json: ['reviewer'],
  },
];

const rolePrefs = [
  { role: 'orchestrator', preferred_model_names: ['m1', 'm2'], default_model_name: 'm1', fallback_model_names: ['m2'] },
  { role: 'reviewer', preferred_model_names: ['m2'], default_model_name: 'm2', fallback_model_names: [] },
  { role: 'planner', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
  { role: 'context_resolver', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
  { role: 'specialist', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
  { role: 'model_router', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
  { role: 'final_responder', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
  { role: 'critic', preferred_model_names: [], default_model_name: null, fallback_model_names: [] },
];

let failPut = false;

beforeEach(() => {
  failPut = false;
  useUiStore.setState({
    orchestratorOn: true,
    selectedModelNames: ['m1'],
    executionMode: 'independent',
    selectedProjectId: 1,
    selectedChatId: 1,
  } as any);
  (global as any).fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes('/models/role-preferences') && init?.method === 'PUT') {
      if (failPut) return Promise.resolve({ ok: false, statusText: 'bad request', json: async () => ({ detail: 'failed' }) });
      return Promise.resolve(ok({ role: 'orchestrator', preferred_model_names: ['m1'], default_model_name: 'm1', fallback_model_names: [] }));
    }
    if (url.includes('/models/role-preferences')) return Promise.resolve(ok(rolePrefs));
    if (url.includes('/models/role-candidates/')) return Promise.resolve(ok([{ model_name: 'm1', downloaded: true, enabled: true, priority: 0 }]));
    if (url.includes('/system/runtime-info')) return Promise.resolve(ok({ env: 'dev', mode: 'web', data_root: 'd', upload_root: 'u', database_url: 'db', qdrant_url: 'q', ollama_base_url: 'o', gpu_enabled: true }));
    if (url.includes('/models/sync')) return Promise.resolve(ok(models));
    if (url.includes('/models')) return Promise.resolve(ok(models));
    return Promise.resolve(ok({}));
  });
});

test('orchestrator ON일 때 role mapping 섹션을 렌더링한다', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModelPanel />
    </QueryClientProvider>
  );
  expect(await screen.findByText(/Role-based Model Mapping/i)).toBeTruthy();
  expect(await screen.findByText(/orchestrator/i)).toBeTruthy();
  expect(await screen.findByText(/default: m1/i)).toBeTruthy();
});

test('orchestrator OFF일 때 manual execution control을 유지한다', async () => {
  useUiStore.setState({ orchestratorOn: false } as any);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModelPanel />
    </QueryClientProvider>
  );
  expect(await screen.findByText(/Manual Execution Mode/i)).toBeTruthy();
  expect(screen.queryByText(/Role-based Model Mapping/i)).toBeNull();
});

test('role preference update 성공 시 PUT을 호출한다', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModelPanel />
    </QueryClientProvider>
  );
  const checkbox = await screen.findByLabelText('role-orchestrator-m1');
  fireEvent.click(checkbox);
  await waitFor(() => {
    expect((global as any).fetch).toHaveBeenCalledWith(expect.stringContaining('/models/role-preferences/orchestrator'), expect.objectContaining({ method: 'PUT' }));
  });
});

test('role preference update 실패 시 에러를 노출한다', async () => {
  failPut = true;
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModelPanel />
    </QueryClientProvider>
  );
  const checkbox = await screen.findByLabelText('role-orchestrator-m1');
  fireEvent.click(checkbox);
  expect(await screen.findByText(/role preference update 실패/i)).toBeTruthy();
});

test('domain mapping helper regression', () => {
  const index = buildRolePreferenceIndex(rolePrefs as any);
  expect(index.orchestrator.default_model_name).toBe('m1');
  expect(index.reviewer.preferred_model_names[0]).toBe('m2');
});
