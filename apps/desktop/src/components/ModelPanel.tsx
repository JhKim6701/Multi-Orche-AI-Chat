import { useMemo } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Model, OrchestrationRole, RoleCandidate, RolePreference } from '../types/domain';

const ORCHESTRATION_ROLES: OrchestrationRole[] = [
  'planner',
  'context_resolver',
  'specialist',
  'model_router',
  'final_responder',
  'reviewer',
  'critic',
  'orchestrator',
];

export function buildRolePreferenceIndex(preferences: RolePreference[]) {
  return preferences.reduce<Record<string, RolePreference>>((acc, pref) => {
    acc[pref.role] = pref;
    return acc;
  }, {});
}

function Badge({ label }: { label: string }) {
  return (
    <span style={{ border: '1px solid #ddd', borderRadius: 8, padding: '0 6px', fontSize: 10, background: '#fafafa' }}>
      {label}
    </span>
  );
}

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
  const { data: rolePreferencesRaw = [] } = useQuery({
    queryKey: ['role-preferences'],
    queryFn: () => api.get<RolePreference[]>('/models/role-preferences'),
    enabled: orchestratorOn,
  });
  const rolePreferences = Array.isArray(rolePreferencesRaw) ? rolePreferencesRaw : [];
  const roleCandidateQueries = useQueries({
    queries: ORCHESTRATION_ROLES.map((role) => ({
      queryKey: ['role-candidates', role],
      queryFn: () => api.get<RoleCandidate[]>(`/models/role-candidates/${role}`),
      enabled: orchestratorOn,
    })),
  });
  const roleCandidatesByRole = useMemo(() => {
    const map: Record<string, RoleCandidate[]> = {};
    ORCHESTRATION_ROLES.forEach((role, index) => {
      const raw = roleCandidateQueries[index].data as unknown;
      map[role] = Array.isArray(raw) ? (raw as RoleCandidate[]) : [];
    });
    return map;
  }, [roleCandidateQueries]);
  const rolePreferenceIndex = useMemo(() => buildRolePreferenceIndex(rolePreferences), [rolePreferences]);

  const { data: runtimeInfo, refetch: refetchRuntime } = useQuery({
    queryKey: ['runtime-info'],
    queryFn: () => api.get<{ env: string; mode: string; data_root: string; upload_root: string; database_url: string; qdrant_url: string; ollama_base_url: string; gpu_enabled: boolean }>('/system/runtime-info'),
    refetchInterval: 15000,
  });

  const syncMutation = useMutation({ mutationFn: () => api.post<Model[]>('/models/sync'), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const pullMutation = useMutation({ mutationFn: (modelName: string) => api.post('/models/pull', { model_name: modelName }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const toggleMutation = useMutation({ mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => api.patch(`/models/${id}/toggle`, { enabled }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const sortMutation = useMutation({ mutationFn: ({ id, sortOrder }: { id: number; sortOrder: number }) => api.patch(`/models/${id}/sort`, { sort_order: sortOrder }), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) });
  const updateRolePreferenceMutation = useMutation({
    mutationFn: ({ role, preferredModelNames }: { role: OrchestrationRole; preferredModelNames: string[] }) =>
      api.put<RolePreference>(`/models/role-preferences/${role}`, { preferred_model_names: preferredModelNames }),
    onMutate: async ({ role, preferredModelNames }) => {
      await qc.cancelQueries({ queryKey: ['role-preferences'] });
      const previous = qc.getQueryData<RolePreference[]>(['role-preferences']) ?? [];
      const next = previous.map((item) =>
        item.role === role
          ? {
              ...item,
              preferred_model_names: preferredModelNames,
              default_model_name: preferredModelNames[0] ?? null,
              fallback_model_names: preferredModelNames.slice(1),
            }
          : item,
      );
      qc.setQueryData(['role-preferences'], next);
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        qc.setQueryData(['role-preferences'], context.previous);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['role-preferences'] });
      ORCHESTRATION_ROLES.forEach((role) => qc.invalidateQueries({ queryKey: ['role-candidates', role] }));
      qc.invalidateQueries({ queryKey: ['models'] });
    },
  });

  const selectedModelsOrdered = useMemo(
    () => models.filter((m) => selectedModelNames.includes(m.model_name)).sort((a, b) => a.sort_order - b.sort_order),
    [models, selectedModelNames]
  );

  const runnableModels = models.filter((m) => m.downloaded && m.enabled);

  const updateRoleSelection = (role: OrchestrationRole, modelName: string) => {
    const current = rolePreferenceIndex[role]?.preferred_model_names ?? [];
    const exists = current.includes(modelName);
    const next = exists ? current.filter((name) => name !== modelName) : [...current, modelName];
    updateRolePreferenceMutation.mutate({ role, preferredModelNames: next });
  };

  return (
    <aside style={{ padding: 8, height: '100%', overflow: 'auto', borderLeft: '1px solid #eee' }}>
      <h3 style={{ margin: '4px 0' }}>Models</h3>
      <button onClick={() => toggleOrchestrator()} style={{ fontSize: 12, marginBottom: 6 }}>
        Orchestrator: {orchestratorOn ? 'ON' : 'OFF'}
      </button>

      {!orchestratorOn && (
        <div style={{ marginBottom: 8, border: '1px solid #ececec', padding: 6, borderRadius: 6, background: '#fff' }}>
          <label style={{ fontSize: 12 }}>Manual Execution Mode </label>
          <select value={executionMode} onChange={(e) => setExecutionMode(e.target.value as any)} style={{ fontSize: 12 }}>
            <option value="independent">independent</option>
            <option value="chained">chained</option>
            <option value="ordered">ordered</option>
          </select>
        </div>
      )}

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
          <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
            <Badge label={m.downloaded ? 'downloaded' : 'not-downloaded'} />
            <Badge label={m.enabled ? 'enabled' : 'disabled'} />
            <Badge label={m.supports_vision ? 'vision' : 'no-vision'} />
            <Badge label={m.supports_reasoning ? 'reasoning' : 'no-reasoning'} />
            <Badge label={m.supports_embeddings ? 'embeddings' : 'no-embeddings'} />
            {m.preferred_roles_json?.length ? <Badge label={`preferred:${m.preferred_roles_json.join(',')}`} /> : null}
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            {!m.downloaded && <button style={{ fontSize: 11 }} onClick={() => pullMutation.mutate(m.model_name)}>Download</button>}
            <button style={{ fontSize: 11 }} onClick={() => toggleMutation.mutate({ id: m.id, enabled: !m.enabled })}>{m.enabled ? 'Disable' : 'Enable'}</button>
            <button style={{ fontSize: 11 }} onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order - 1 })}>↑</button>
            <button style={{ fontSize: 11 }} onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order + 1 })}>↓</button>
          </div>
          <small>order {m.sort_order}</small>
        </div>
      ))}

      {orchestratorOn && (
        <>
          <hr />
          <div style={{ fontSize: 12, marginBottom: 6 }}><strong>Role-based Model Mapping</strong></div>
          {ORCHESTRATION_ROLES.map((role) => {
            const pref = rolePreferenceIndex[role];
            const candidates = roleCandidatesByRole[role] ?? [];
            const selected = pref?.preferred_model_names ?? [];
            return (
              <div key={role} style={{ border: '1px solid #ececec', borderRadius: 6, padding: 6, marginBottom: 6, background: '#fff' }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{role}</div>
                <div style={{ fontSize: 11, marginTop: 2 }}>default: <strong>{pref?.default_model_name ?? '-'}</strong></div>
                <div style={{ fontSize: 11 }}>fallback: {(pref?.fallback_model_names ?? []).join(', ') || '-'}</div>
                <div style={{ marginTop: 4, fontSize: 11, color: '#475467' }}>candidate models:</div>
                {candidates.length === 0 ? (
                  <div style={{ fontSize: 11, color: '#999' }}>no preferred candidates</div>
                ) : (
                  candidates.map((candidate) => (
                    <label key={`${role}-${candidate.model_name}`} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, marginTop: 2 }}>
                      <input
                        aria-label={`role-${role}-${candidate.model_name}`}
                        type="checkbox"
                        checked={selected.includes(candidate.model_name)}
                        onChange={() => updateRoleSelection(role, candidate.model_name)}
                        disabled={updateRolePreferenceMutation.isPending}
                      />
                      <span>{candidate.model_name}</span>
                      <Badge label={`priority:${candidate.priority}`} />
                      <Badge label={candidate.enabled ? 'enabled' : 'disabled'} />
                    </label>
                  ))
                )}
              </div>
            );
          })}
          {updateRolePreferenceMutation.error && (
            <div style={{ color: '#b42318', fontSize: 11 }}>
              role preference update 실패: {(updateRolePreferenceMutation.error as Error).message}
              <button style={{ marginLeft: 6, fontSize: 11 }} onClick={() => qc.invalidateQueries({ queryKey: ['role-preferences'] })}>refetch</button>
            </div>
          )}
        </>
      )}

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
