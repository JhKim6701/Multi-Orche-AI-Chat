import { useMemo } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Model, OrchestrationRole, RoleCandidate, RolePreference } from '../types/domain';
import { Alert } from './ui/alert';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Separator } from './ui/separator';

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
  const setRoleDefault = (role: OrchestrationRole, modelName: string) => {
    const current = rolePreferenceIndex[role]?.preferred_model_names ?? [];
    const next = [modelName, ...current.filter((name) => name !== modelName)];
    updateRolePreferenceMutation.mutate({ role, preferredModelNames: next });
  };
  const moveRoleOrder = (role: OrchestrationRole, modelName: string, delta: -1 | 1) => {
    const current = [...(rolePreferenceIndex[role]?.preferred_model_names ?? [])];
    const idx = current.indexOf(modelName);
    if (idx < 0) return;
    const target = idx + delta;
    if (target < 0 || target >= current.length) return;
    [current[idx], current[target]] = [current[target], current[idx]];
    updateRolePreferenceMutation.mutate({ role, preferredModelNames: current });
  };

  return (
    <aside className="h-full overflow-auto border-l border-border bg-muted/30 p-2">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Models</h3>
        <Button size="sm" variant={orchestratorOn ? 'default' : 'outline'} onClick={() => toggleOrchestrator()}>
          Orchestrator: {orchestratorOn ? 'ON' : 'OFF'}
        </Button>
      </div>

      {!orchestratorOn && (
        <Card className="mb-2">
          <CardContent className="flex items-center gap-2 p-2">
            <label className="text-xs">Manual Execution Mode</label>
            <select value={executionMode} onChange={(e) => setExecutionMode(e.target.value as any)} className="rounded border border-border bg-white px-2 py-1 text-xs">
              <option value="independent">independent</option>
              <option value="chained">chained</option>
              <option value="ordered">ordered</option>
            </select>
          </CardContent>
        </Card>
      )}

      <Card className="mb-2">
        <CardContent className="p-2">
          <label className="text-xs">Orchestrator Model</label>
          <select
            value={orchestratorModelName ?? ''}
            onChange={(e) => setOrchestratorModelName(e.target.value || undefined)}
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1 text-xs"
          >
            <option value="">(auto fallback)</option>
            {runnableModels.map((m) => (
              <option key={m.id} value={m.model_name}>{m.model_name}</option>
            ))}
          </select>
        </CardContent>
      </Card>

      <Button size="sm" variant="outline" onClick={() => syncMutation.mutate()}>
        Sync Ollama
      </Button>
      {syncMutation.error && <Alert className="mt-2 border-red-200 bg-red-50 text-red-700">Ollama model sync 실패: {(syncMutation.error as Error).message}</Alert>}

      {isLoading ? <p className="text-xs">Loading models...</p> : null}
      {error ? (
        <Alert className="mt-2 border-red-200 bg-red-50 text-red-700">
          모델 목록 로딩 실패. API 연결 상태를 확인하고 다시 시도하세요.
          <Button size="sm" variant="outline" className="ml-2" onClick={() => qc.invalidateQueries({ queryKey: ['models'] })}>Retry</Button>
        </Alert>
      ) : null}

      <div className="mt-2 space-y-2">
        {models.map((m) => (
          <Card key={m.id}>
            <CardContent className="space-y-2 p-2">
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={selectedModelNames.includes(m.model_name)} onChange={() => toggleSelectedModel(m.model_name)} />
                {m.model_name}
              </label>
              <div className="flex flex-wrap gap-1">
                <Badge>{m.downloaded ? 'downloaded' : 'not-downloaded'}</Badge>
                <Badge>{m.enabled ? 'enabled' : 'disabled'}</Badge>
                <Badge>{m.supports_vision ? 'vision' : 'no-vision'}</Badge>
                <Badge>{m.supports_reasoning ? 'reasoning' : 'no-reasoning'}</Badge>
                <Badge>{m.supports_embeddings ? 'embeddings' : 'no-embeddings'}</Badge>
                {m.preferred_roles_json?.length ? <Badge variant="info">preferred:{m.preferred_roles_json.join(',')}</Badge> : null}
              </div>
              <div className="flex gap-1">
                {!m.downloaded && <Button size="sm" variant="outline" onClick={() => pullMutation.mutate(m.model_name)}>Download</Button>}
                <Button size="sm" variant="outline" onClick={() => toggleMutation.mutate({ id: m.id, enabled: !m.enabled })}>{m.enabled ? 'Disable' : 'Enable'}</Button>
                <Button size="sm" variant="outline" onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order - 1 })}>↑</Button>
                <Button size="sm" variant="outline" onClick={() => sortMutation.mutate({ id: m.id, sortOrder: m.sort_order + 1 })}>↓</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {orchestratorOn && (
        <>
          <Separator />
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Role-based Model Mapping</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {ORCHESTRATION_ROLES.map((role) => {
                const pref = rolePreferenceIndex[role];
                const candidates = roleCandidatesByRole[role] ?? [];
                const selected = pref?.preferred_model_names ?? [];
                return (
                  <Card key={role} className="bg-white">
                    <CardContent className="space-y-1 p-2">
                      <div className="text-xs font-semibold">{role}</div>
                      <div className="text-xs">default: <strong>{pref?.default_model_name ?? '-'}</strong></div>
                      <div className="text-xs">fallback: {(pref?.fallback_model_names ?? []).join(', ') || '-'}</div>
                      <div className="text-[11px] text-slate-600">candidates</div>
                      {candidates.map((candidate) => (
                        <div
                          key={`${role}-${candidate.model_name}`}
                          className={`flex flex-wrap items-center gap-1 rounded border p-1 text-[11px] ${
                            candidate.is_default ? 'border-emerald-200 bg-emerald-50'
                              : candidate.is_fallback ? 'border-amber-200 bg-amber-50'
                                : candidate.is_preferred ? 'border-blue-200 bg-blue-50' : 'border-border'
                          }`}
                        >
                          <input
                            aria-label={`role-${role}-${candidate.model_name}`}
                            type="checkbox"
                            checked={selected.includes(candidate.model_name)}
                            onChange={() => updateRoleSelection(role, candidate.model_name)}
                            disabled={updateRolePreferenceMutation.isPending}
                          />
                          <span>{candidate.model_name}</span>
                          {candidate.is_default && <Badge variant="success">default</Badge>}
                          {candidate.is_fallback && <Badge variant="warning">fallback</Badge>}
                          {!candidate.is_preferred && <Badge>candidate</Badge>}
                          <Badge>cap:{candidate.capability_score}</Badge>
                          <Badge>priority:{candidate.priority}</Badge>
                          <Button size="sm" variant="outline" onClick={() => setRoleDefault(role, candidate.model_name)} disabled={updateRolePreferenceMutation.isPending}>set default</Button>
                          {candidate.is_preferred && (
                            <>
                              <Button size="sm" variant="outline" onClick={() => moveRoleOrder(role, candidate.model_name, -1)} disabled={updateRolePreferenceMutation.isPending}>↑pref</Button>
                              <Button size="sm" variant="outline" onClick={() => moveRoleOrder(role, candidate.model_name, 1)} disabled={updateRolePreferenceMutation.isPending}>↓pref</Button>
                            </>
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                );
              })}
              {updateRolePreferenceMutation.error && (
                <Alert className="border-red-200 bg-red-50 text-red-700">
                  role preference update 실패: {(updateRolePreferenceMutation.error as Error).message}
                  <Button size="sm" variant="outline" className="ml-2" onClick={() => qc.invalidateQueries({ queryKey: ['role-preferences'] })}>refetch</Button>
                </Alert>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Separator />
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Manual Execution Order</CardTitle>
        </CardHeader>
        <CardContent className="text-xs">
          {selectedModelsOrdered.length === 0 ? <div>none</div> : selectedModelsOrdered.map((m, idx) => <div key={m.id}>{idx + 1}. {m.model_name}</div>)}
        </CardContent>
      </Card>

      <Separator />
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Runtime Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-[11px]">
          <div>mode={runtimeInfo?.mode ?? '-'}</div>
          <div>env={runtimeInfo?.env ?? '-'}</div>
          <div>data_root={runtimeInfo?.data_root ?? '-'}</div>
          <div>upload_root={runtimeInfo?.upload_root ?? '-'}</div>
          <div>database={runtimeInfo?.database_url ?? '-'}</div>
          <div>qdrant={runtimeInfo?.qdrant_url ?? '-'}</div>
          <div>ollama={runtimeInfo?.ollama_base_url ?? '-'}</div>
          <Button size="sm" variant="outline" onClick={() => refetchRuntime()}>Refresh runtime info</Button>
        </CardContent>
      </Card>
    </aside>
  );
}
