import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Model } from '../types/domain';

export function ModelPanel() {
  const qc = useQueryClient();
  const orchestratorOn = useUiStore((s) => s.orchestratorOn);
  const toggleOrchestrator = useUiStore((s) => s.toggleOrchestrator);
  const executionMode = useUiStore((s) => s.executionMode);
  const setExecutionMode = useUiStore((s) => s.setExecutionMode);
  const selectedModelNames = useUiStore((s) => s.selectedModelNames);
  const toggleSelectedModel = useUiStore((s) => s.toggleSelectedModel);
  const orchestratorModelName = useUiStore((s) => s.orchestratorModelName);
  const setOrchestratorModelName = useUiStore((s) => s.setOrchestratorModelName);

  const { data: models = [], isLoading, error } = useQuery({ queryKey: ['models'], queryFn: () => api.get<Model[]>('/models') });
  const { data: runtimeInfo, refetch: refetchRuntime } = useQuery({
    queryKey: ['runtime-info'],
    queryFn: () => api.get<{ env: string; mode: string; data_root: string; upload_root: string; database_url: string; qdrant_url: string; ollama_base_url: string; gpu_enabled: boolean }>('/system/runtime-info'),
    refetchInterval: 15000,
  });

  const syncMutation = useMutation({ mutationFn: () => api.post<Model[]>('/models/sync'), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const pullMutation = useMutation({ mutationFn: (modelName: string) => api.post('/models/pull', { model_name: modelName }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const toggleMutation = useMutation({ mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => api.patch(`/models/${id}/toggle`, { enabled }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const sortMutation = useMutation({ mutationFn: ({ id, sortOrder }: { id: number; sortOrder: number }) => api.patch(`/models/${id}/sort`, { sort_order: sortOrder }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });

  const selectedModelsOrdered = useMemo(
    () => models.filter((m) => selectedModelNames.includes(m.model_name)).sort((a, b) => a.sort_order - b.sort_order),
    [models, selectedModelNames]
  );

  const runnableModels = models.filter((m) => m.downloaded && m.enabled);

  return (
    <aside style={{ padding: 8, height: '100%', overflow: 'auto', borderLeft: '1px solid #eee' }}>
      <h3 style={{ margin: '4px 0' }}>Models</h3>
      <button onClick={() => toggleOrchestrator()} style={{ fontSize: 12, marginBottom: 6 }}>
        Orchestrator: {orchestratorOn ? 'ON' : 'OFF'}
      </button>

      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 12 }}>Manual Execution Mode </label>
        <select value={executionMode} onChange={(e) => setExecutionMode(e.target.value as any)} style={{ fontSize: 12 }}>
          <option value="independent">independent</option>
          <option value="chained">chained</option>
          <option value="ordered">ordered</option>
        </select>
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 12 }}>Orchestrator Model </label>
        <select
          value={orchestratorModelName ?? ''}
          onChange={(e) => setOrchestratorModelName(e.target.value || undefined)}
          style={{ fontSize: 12 }}
        >
          <option value="">(auto fallback)</option>
          {runnableModels.map((m) => (
            <option key={m.id} value={m.model_name}>{m.model_name}</option>
          ))}
        </select>
      </div>

      <button onClick={() => syncMutation.mutate()} style={{ fontSize: 12 }}>Sync Ollama</button>
      {syncMutation.error && <p style={{ color: '#b42318', fontSize: 12 }}>Ollama model sync 실패: {(syncMutation.error as Error).message}</p>}

      {isLoading ? <p>Loading models...</p> : null}
      {error ? (
        <p style={{ color: '#b42318', fontSize: 12 }}>
          모델 목록 로딩 실패. API 연결 상태를 확인하고 다시 시도하세요.
          <button style={{ marginLeft: 6, fontSize: 11 }} onClick={() => qc.invalidateQueries({ queryKey: ['models'] })}>Retry</button>
        </p>
      ) : null}

      {models.map((m) => (
        <div key={m.id} style={{ borderBottom: '1px solid #efefef', padding: '6px 0' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
            <input type="checkbox" checked={selectedModelNames.includes(m.model_name)} onChange={() => toggleSelectedModel(m.model_name)} />
            {m.model_name}
          </label>
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            {!m.downloaded && <button style={{ fontSize: 11 }} onClick={() => pullMutation.mutate(m.model_name)}>Download</button>}
            <button style={{ fontSize: 11 }} onClick={() => toggleMutation.mutate({ id: m.id, enabled: !m.enabled })}>{m.enabled ? 'Disable' : 'Enable'}</button>
            <button style={{ fontSize: 11 }} onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order - 1 })}>↑</button>
            <button style={{ fontSize: 11 }} onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order + 1 })}>↓</button>
          </div>
          <small>{m.downloaded ? 'downloaded' : 'not downloaded'} / {m.enabled ? 'enabled' : 'disabled'} / order {m.sort_order}</small>
        </div>
      ))}

      <hr />
      <div style={{ fontSize: 12 }}>
        <strong>Manual Execution Order (sort_order)</strong>
        {selectedModelsOrdered.length === 0 ? <div>none</div> : selectedModelsOrdered.map((m, idx) => <div key={m.id}>{idx + 1}. {m.model_name}</div>)}
      </div>
      <hr />
      <div style={{ fontSize: 11, lineHeight: 1.5 }}>
        <strong>Runtime Settings (read-only)</strong>
        <div>mode={runtimeInfo?.mode ?? '-'}</div>
        <div>env={runtimeInfo?.env ?? '-'}</div>
        <div>data_root={runtimeInfo?.data_root ?? '-'}</div>
        <div>upload_root={runtimeInfo?.upload_root ?? '-'}</div>
        <div>database={runtimeInfo?.database_url ?? '-'}</div>
        <div>qdrant={runtimeInfo?.qdrant_url ?? '-'}</div>
        <div>ollama={runtimeInfo?.ollama_base_url ?? '-'}</div>
        <button style={{ fontSize: 11, marginTop: 4 }} onClick={() => refetchRuntime()}>Refresh runtime info</button>
      </div>
    </aside>
  );
}
