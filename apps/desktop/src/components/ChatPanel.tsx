import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useUiStore } from '../store/uiStore';
import { Asset, MessageListResponse, OrchestrationRun, OrchestrationStep, RolePreference } from '../types/domain';
import { Alert } from './ui/alert';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Separator } from './ui/separator';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

type Segment = {
  id: number;
  topic_label: string;
  topic_summary: string;
  is_active: boolean;
  parent_segment_id?: number | null;
  branch_from_message_id?: number | null;
};

type ViewMode = 'active' | 'all' | 'segment';

type DetectResponse = {
  active_segment_id: number;
  diverged: boolean;
  overlap: number;
  reason: string;
  recommended_action: 'stay' | 'new_segment';
  suggested_topic_label: string;
};

type BranchResponse = {
  created_segment_id: number;
  topic_label: string;
  parent_segment_id: number | null;
  branch_from_message_id: number;
  active_switched: boolean;
  active_segment_id: number;
};

type StreamEvent = {
  event_type: string;
  run_id: number;
  step_id: number | null;
  step_name: string | null;
  status: string;
  model_name: string | null;
  segment_id: number | null;
  timestamp: string;
  final_message_id?: number | null;
  reviewer_decision?: string | null;
  assigned_role?: string | null;
  fallback_model_name?: string | null;
  fallback_reason?: string | null;
  retry_count?: number;
  approval_status?: string | null;
};

type RetrievalHit = {
  chunk_id: number;
  asset_id: number;
  filename: string;
  chunk_index: number;
  page?: number | null;
  snippet: string;
  score: number;
  retrieval_mode: string;
  vector_score: number;
  lexical_score: number;
  ocr_fallback_used?: boolean;
};

export function ChatPanel() {
  const qc = useQueryClient();
  const selectedProjectId = useUiStore((s) => s.selectedProjectId);
  const selectedChatId = useUiStore((s) => s.selectedChatId);
  const selectedModelNames = useUiStore((s) => s.selectedModelNames);
  const orchestratorOn = useUiStore((s) => s.orchestratorOn);
  const executionMode = useUiStore((s) => s.executionMode);
  const orchestratorModelName = useUiStore((s) => s.orchestratorModelName);

  const [message, setMessage] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [streamPreview, setStreamPreview] = useState('');
  const [showRunDetail, setShowRunDetail] = useState(true);
  const [showOrchestrationDrawer, setShowOrchestrationDrawer] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('active');
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [divergence, setDivergence] = useState<DetectResponse | null>(null);
  const [liveEvents, setLiveEvents] = useState<StreamEvent[]>([]);
  const [requireApprovalBeforePublish, setRequireApprovalBeforePublish] = useState(false);
  const [showRetrievalDebug, setShowRetrievalDebug] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [showDiagnosticsVerbose, setShowDiagnosticsVerbose] = useState(false);

  const queryScope = viewMode === 'segment' ? 'segment' : viewMode;
  const scopeQuery = viewMode === 'segment' && selectedSegmentId ? `&segment_id=${selectedSegmentId}` : '';

  const { data: messageResponse, error: messageError } = useQuery({
    queryKey: ['messages', selectedChatId, queryScope, selectedSegmentId],
    queryFn: () => api.get<MessageListResponse>(`/messages?chat_thread_id=${selectedChatId}&scope=${queryScope}${scopeQuery}`),
    enabled: !!selectedChatId
  });

  const messages = messageResponse?.items ?? [];
  const scopeMeta = messageResponse?.scope_meta;

  const { data: assets = [] } = useQuery({
    queryKey: ['assets', selectedChatId],
    queryFn: () => api.get<Asset[]>(`/assets/chat/${selectedChatId}`),
    enabled: !!selectedChatId
  });
  const { data: retrievalPreview } = useQuery({
    queryKey: ['retrieval-preview', selectedChatId, selectedSegmentId, message],
    queryFn: () => api.get<{ hits: RetrievalHit[]; packed_context: string; packed_meta: { retrieval_mode: string; used_chunk_ids: number[]; ocr_used: boolean }; scope: { project_id: number; chat_thread_id: number; segment_id?: number } }>(`/assets/chat/${selectedChatId}/retrieval-preview?query=${encodeURIComponent(message)}${selectedSegmentId ? `&segment_id=${selectedSegmentId}` : ''}`),
    enabled: !!selectedChatId && showRetrievalDebug && message.trim().length > 2,
  });
  const { data: diagnostics } = useQuery({
    queryKey: ['diagnostics', selectedChatId, showDiagnosticsVerbose],
    queryFn: () => api.get<{ status: string; mode: string; unresolved_dependencies: string[]; data_root: string; upload_root: string; checks: Record<string, { ok: boolean }>; sensitive_details_included: boolean; database_url: string; ollama_base_url: string; qdrant_url: string }>(`/system/health?verbose=${showDiagnosticsVerbose}`),
    enabled: showDiagnostics,
    refetchInterval: 5000,
  });

  const { data: segments = [] } = useQuery({
    queryKey: ['segments', selectedChatId],
    queryFn: () => api.get<Segment[]>(`/segments?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId,
    refetchInterval: 3000,
  });

  const activeSegment = segments.find((s) => s.is_active);
  const selectedSegment = segments.find((s) => s.id === selectedSegmentId);

  useEffect(() => {
    if (!selectedSegmentId && activeSegment) {
      setSelectedSegmentId(activeSegment.id);
    }
  }, [activeSegment, selectedSegmentId]);

  const switchSegment = useMutation({
    mutationFn: (segmentId: number) => api.post<{ active_segment: { id: number } }>(`/segments/switch?chat_thread_id=${selectedChatId}`, { segment_id: segmentId }),
    onSuccess: ({ active_segment }) => {
      setSelectedSegmentId(active_segment.id);
      setViewMode('segment');
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });

  const branchMutation = useMutation({
    mutationFn: ({ messageId, topicLabel }: { messageId: number; topicLabel: string }) =>
      api.post<BranchResponse>(`/segments/branch?chat_thread_id=${selectedChatId}`, { from_message_id: messageId, topic_label: topicLabel }),
    onSuccess: (payload) => {
      setSelectedSegmentId(payload.created_segment_id);
      setViewMode('segment');
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
    }
  });

  const { data: runs = [] } = useQuery({
    queryKey: ['orchestration-runs', selectedChatId],
    queryFn: () => api.get<OrchestrationRun[]>(`/orchestration/runs?chat_thread_id=${selectedChatId}`),
    enabled: !!selectedChatId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });

  const { data: runDetail } = useQuery({
    queryKey: ['orchestration-run-detail', selectedRunId],
    queryFn: () => api.get<{ run: OrchestrationRun & { final_message_id?: number; segment_id?: number; generated_artifact_ids?: number[]; artifact_summary?: Array<{ id: number; filename: string; producing_model?: string; producing_role?: string }>; vision_used?: boolean; image_asset_ids?: number[]; approval_status?: string; pending_final_draft?: string; execution_graph_summary?: { parallel_groups?: Record<string, number[]>; step_count?: number }; final_publish_status?: string }; steps: OrchestrationStep[]; final_message?: { content_markdown: string; model_name?: string; model_role?: string; final_provenance_summary?: string; generated_artifact_ids?: number[] } }>(`/orchestration/runs/${selectedRunId}`),
    enabled: !!selectedRunId && orchestratorOn,
    refetchInterval: orchestratorOn ? 3000 : false,
  });
  const { data: rolePreferencesRaw = [] } = useQuery({
    queryKey: ['role-preferences'],
    queryFn: () => api.get<RolePreference[]>('/models/role-preferences'),
    enabled: orchestratorOn,
  });
  const rolePreferences = Array.isArray(rolePreferencesRaw) ? rolePreferencesRaw : [];
  const rolePreferenceByRole = useMemo(
    () => rolePreferences.reduce<Record<string, RolePreference>>((acc, item) => ({ ...acc, [item.role]: item }), {}),
    [rolePreferences]
  );

  useEffect(() => {
    if (!selectedRunId || !orchestratorOn) return;
    const source = new EventSource(`${API_BASE}/orchestration/runs/${selectedRunId}/stream`);
    const handle = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as StreamEvent;
        setLiveEvents((prev) => [...prev.slice(-9), payload]);
        qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
        if (payload.event_type === 'run_completed' || payload.event_type === 'run_failed') {
          qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
          qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
        }
      } catch {
        // noop, fallback polling still active
      }
    };

    source.addEventListener('run_started', handle);
    source.addEventListener('step_started', handle);
    source.addEventListener('step_completed', handle);
    source.addEventListener('reviewer_started', handle);
    source.addEventListener('reviewer_completed', handle);
    source.addEventListener('specialist_started', handle);
    source.addEventListener('specialist_completed', handle);
    source.addEventListener('revision_started', handle);
    source.addEventListener('revision_completed', handle);
    source.addEventListener('step_failed', handle);
    source.addEventListener('run_completed', handle);
    source.addEventListener('run_failed', handle);
    source.onerror = () => source.close();

    return () => source.close();
  }, [selectedRunId, orchestratorOn, qc, selectedChatId]);

  const uploadMutation = useMutation({
    mutationFn: (payload: { file: File; messageId?: number }) => {
      const form = new FormData();
      form.append('project_id', String(selectedProjectId));
      form.append('chat_thread_id', String(selectedChatId));
      form.append('source_type', 'user_upload');
      if (payload.messageId) form.append('message_id', String(payload.messageId));
      form.append('file', payload.file);
      return api.postForm<Asset>('/assets/upload', form);
    },
    onSuccess: () => {
      setFile(null);
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
    }
  });

  const manualRunMutation = useMutation({
    mutationFn: (assetIds: number[]) =>
      api.post<{ used_segment_id: number; user_message: { id: number } }>('/messages/execute', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        content_markdown: message,
        selected_model_names: selectedModelNames,
        execution_mode: executionMode,
        message_asset_ids: assetIds
      }),
    onSuccess: (result) => {
      setMessage('');
      setStreamPreview('');
      setSelectedSegmentId(result.used_segment_id);
      if (viewMode === 'segment' && result.used_segment_id) {
        setViewMode('segment');
      }
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
    }
  });

  const orchestrateMutation = useMutation({
    mutationFn: (assetIds: number[]) =>
      api.post<{ id: number }>('/orchestration/run', {
        project_id: selectedProjectId,
        chat_thread_id: selectedChatId,
        content_markdown: message,
        selected_model_names: selectedModelNames,
        orchestrator_model_name: orchestratorModelName,
        message_asset_ids: assetIds,
        require_approval_before_publish: requireApprovalBeforePublish,
      }),
    onSuccess: (run) => {
      setMessage('');
      setSelectedRunId(run.id);
      qc.invalidateQueries({ queryKey: ['orchestration-runs', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['segments', selectedChatId] });
    }
  });
  const approveRunMutation = useMutation({
    mutationFn: (runId: number) => api.post(`/orchestration/runs/${runId}/approve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['assets', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['orchestration-runs', selectedChatId] });
    }
  });
  const rejectRunMutation = useMutation({
    mutationFn: (runId: number) => api.post(`/orchestration/runs/${runId}/reject`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
      qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
      qc.invalidateQueries({ queryKey: ['orchestration-runs', selectedChatId] });
    }
  });

  const canSend = !!selectedChatId && !!selectedProjectId && !!message.trim() && selectedModelNames.length > 0;

  const previewStream = async () => {
    if (!selectedChatId || selectedModelNames.length === 0 || !message.trim()) return;
    const detect = await api.post<DetectResponse>(`/segments/detect?chat_thread_id=${selectedChatId}&new_text=${encodeURIComponent(message)}`);
    setDivergence(detect);

    const url = new URL(`${API_BASE}/messages/stream`);
    url.searchParams.set('chat_thread_id', String(selectedChatId));
    url.searchParams.set('model_name', selectedModelNames[0]);
    url.searchParams.set('prompt', message);
    url.searchParams.set('scope', queryScope);
    if (queryScope === 'segment' && selectedSegmentId) {
      url.searchParams.set('segment_id', String(selectedSegmentId));
    }

    const res = await fetch(url.toString());
    if (!res.ok || !res.body) {
      setStreamPreview('stream unavailable');
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let text = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      text += decoder.decode(value, { stream: true });
      setStreamPreview(text.slice(-3000));
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    try {
      let uploaded: Asset | null = null;
      if (file) uploaded = await uploadMutation.mutateAsync({ file });
      const assetIds = uploaded ? [uploaded.id] : [];

      if (orchestratorOn) await orchestrateMutation.mutateAsync(assetIds);
      else await manualRunMutation.mutateAsync(assetIds);
    } finally {
      setSending(false);
    }
  };

  const timeline = useMemo(() => messages.slice().sort((a, b) => a.sequence_no - b.sequence_no), [messages]);
  const activeStepId = runDetail?.steps?.find((step) => step.status === 'running')?.id;
  const latestAssistant = [...timeline].reverse().find((m) => m.role === 'assistant');
  const usedAssetsLine = latestAssistant?.content_markdown?.split('\n').find((line) => line.includes('[Used assets]'));
  const provenanceLine = latestAssistant?.content_markdown?.split('\n').find((line) => line.includes('[Orchestration Provenance]'));
  const generatedByMessage = useMemo(() => {
    const map = new Map<number, Asset[]>();
    assets.filter((a) => a.source_type === 'ai_generated' && a.message_id).forEach((a) => {
      const key = a.message_id as number;
      const prev = map.get(key) ?? [];
      prev.push(a);
      map.set(key, prev);
    });
    return map;
  }, [assets]);
  const visionPending = file?.type?.startsWith('image/') ?? false;
  const surfaceError = (manualRunMutation.error || orchestrateMutation.error || branchMutation.error || switchSegment.error) as Error | null;
  const errorText = (surfaceError?.message ?? '').toLowerCase();
  const errorCode = (surfaceError?.message.match(/\[([^\]]+)\]/)?.[1] ?? '').toLowerCase();
  const recoveryHintByCode: Record<string, string> = {
    ollama_unavailable: 'Ollama 서버가 내려가 있거나 base URL이 잘못됐습니다. 서비스 상태를 확인하세요.',
    qdrant_unavailable: 'Qdrant 연결 문제입니다. Docker/endpoint 및 인덱스 상태를 점검하세요.',
    approval_state_inconsistent: '승인 상태 불일치입니다. Run detail 새로고침 후 approve/reject를 다시 시도하세요.',
    desktop_runtime_misconfigured: 'Desktop 모드 설정이 어긋났습니다. doctor 실행 후 runtime-info를 재확인하세요.',
    routing_fallback: '모델 capabilities와 enabled/downloaded 상태를 점검하세요.',
  };
  const recoveryHint = recoveryHintByCode[errorCode]
    ?? (errorText.includes('upload') || errorText.includes('write')
      ? '업로드/데이터 경로 권한을 확인하세요.'
      : '시스템 상태 배너를 확인하고 다시 시도하세요.');

  const divergenceLabel = useMemo(() => {
    if (!divergence) return '';
    if (divergence.reason.includes('shift_expression')) return '전환 표현 감지: 새 segment 권장';
    if (divergence.recommended_action === 'new_segment') return '새 segment 추천';
    return '현재 주제 유지';
  }, [divergence]);

  const statusBadgeVariant = (status?: string) => {
    if (!status) return 'default' as const;
    if (status.includes('fail') || status.includes('reject')) return 'danger' as const;
    if (status.includes('pending') || status.includes('running')) return 'warning' as const;
    if (status.includes('complete') || status.includes('approved') || status.includes('published')) return 'success' as const;
    return 'info' as const;
  };

  const eventBadgeVariant = (eventType: string) => {
    if (eventType.includes('failed')) return 'danger' as const;
    if (eventType.includes('approval')) return 'warning' as const;
    if (eventType.includes('specialist')) return 'info' as const;
    return 'default' as const;
  };

  return (
    <main className="flex h-full flex-col gap-3 p-3">
      <div className="flex items-center justify-between">
        <h3 className="m-0 text-sm font-semibold">Chat {orchestratorOn ? '(Orchestrator ON)' : '(Manual Mode)'}</h3>
        <Badge variant={orchestratorOn ? 'info' : 'default'}>{orchestratorOn ? 'orchestrated' : 'manual'}</Badge>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Segment Scope</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant={viewMode === 'active' ? 'default' : 'outline'} onClick={() => setViewMode('active')}>Active Segment View</Button>
            <Button size="sm" variant={viewMode === 'all' ? 'default' : 'outline'} onClick={() => setViewMode('all')}>Full Timeline View</Button>
            <Button size="sm" variant={viewMode === 'segment' ? 'default' : 'outline'} onClick={() => setViewMode('segment')} disabled={!selectedSegmentId}>Selected Segment View</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <Badge variant="info">active #{scopeMeta?.active_segment_id ?? '-'}</Badge>
            <span>{activeSegment?.topic_label ?? 'N/A'}</span>
            {activeSegment?.parent_segment_id ? <span>parent #{activeSegment.parent_segment_id}</span> : null}
            {activeSegment?.branch_from_message_id ? <span>origin msg#{activeSegment.branch_from_message_id}</span> : null}
            {viewMode === 'segment' && selectedSegment ? <Badge>viewing seg#{selectedSegment.id}:{selectedSegment.topic_label}</Badge> : null}
          </div>
          {!!segments.length && (
            <div className="flex flex-wrap gap-2">
              {segments.map((s) => (
                <Button key={s.id} size="sm" variant={s.is_active ? 'default' : 'outline'} onClick={() => { setSelectedSegmentId(s.id); setViewMode('segment'); }}>
                  seg#{s.id} {s.topic_label}
                </Button>
              ))}
              {viewMode === 'segment' && selectedSegmentId && (
                <Button size="sm" variant="ghost" onClick={() => switchSegment.mutate(selectedSegmentId)}>Switch active to seg#{selectedSegmentId}</Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {!selectedChatId && <Alert className="text-xs">Select chat to start.</Alert>}
      {messageError && <Alert className="border-red-200 bg-red-50 text-red-700">Failed to load messages</Alert>}

      <Card className="min-h-[260px] flex-1 overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Timeline</CardTitle>
        </CardHeader>
        <CardContent className="max-h-[52vh] space-y-2 overflow-auto">
        {timeline.length === 0 ? <p className="text-xs text-slate-500">No messages yet</p> : null}
        {timeline.map((m, idx) => (
          <div key={m.id} className={`rounded-md border p-3 ${m.role === 'user' ? 'border-blue-100 bg-blue-50/40' : 'border-slate-200 bg-slate-50/50'}`}>
            {scopeMeta?.scope === 'all' && scopeMeta.segment_boundaries.includes(m.sequence_no) && (
              <Badge variant="warning" className="mb-1">Segment boundary · segment #{m.segment_id}</Badge>
            )}
            {idx > 0 && timeline[idx - 1].segment_id !== m.segment_id && scopeMeta?.scope !== 'all' && (
              <Badge variant="warning" className="mb-1">새 주제 시작 (segment #{m.segment_id})</Badge>
            )}
            <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
              <Badge>{m.role}</Badge>
              <span>seg#{m.segment_id ?? '-'}</span>
              {m.model_name ? <Badge variant="info">{m.model_name}</Badge> : null}
            </div>
            <div className="whitespace-pre-wrap text-sm">{m.content_markdown}</div>
            {m.role === 'assistant' && (
              <div className="mt-2 border-t border-dashed pt-2 text-[11px] text-slate-600">
                {m.content_markdown.split('\n').filter((line) => line.startsWith('[Used ') || line.startsWith('[RAG Provenance]')).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            )}
            {m.role === 'assistant' && (generatedByMessage.get(m.id)?.length ?? 0) > 0 && (
              <div className="mt-2 space-y-1 border-t border-dashed pt-2 text-[11px]">
                <div className="font-medium">Generated Artifacts</div>
                {(generatedByMessage.get(m.id) ?? []).map((asset) => (
                  <div key={asset.id} className="flex flex-wrap items-center gap-2">
                    <a href={`${API_BASE}/assets/${asset.id}/download`} target="_blank">{asset.original_filename}</a>
                    <Badge>model={asset.producing_model ?? '-'}</Badge>
                    <Badge>role={asset.producing_role ?? '-'}</Badge>
                    <span>kind={asset.derived_metadata_json?.kind ?? 'unknown'}</span>
                  </div>
                ))}
              </div>
            )}
            {m.role === 'user' && (
              <div className="mt-2">
                <Button type="button" size="sm" variant="outline" onClick={() => branchMutation.mutate({ messageId: m.id, topicLabel: `${m.content_markdown.split(' ').slice(0, 4).join(' ') || 'branch'}-branch` })}>
                  여기서 분기 만들기
                </Button>
              </div>
            )}
          </div>
        ))}
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2">
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Assets</CardTitle></CardHeader>
        <CardContent className="space-y-2">
        {assets.length === 0 ? <small className="text-xs text-slate-500">No uploads</small> : assets.map((a) => (
          <div key={a.id} className="rounded border p-2 text-xs">
            <a href={`${API_BASE}/assets/${a.id}/download`} target="_blank">{a.original_filename}</a>
            <Badge className="ml-2">chunks:{a.derived_metadata_json?.chunk_count ?? 0}</Badge>
            <div className="mt-1 text-[11px] text-slate-600">
              ingest={a.derived_metadata_json?.ingest_status ?? 'uploaded'} · ocr={String(a.derived_metadata_json?.ocr_fallback_used ?? false)} · failed={String(a.derived_metadata_json?.ingest_pipeline?.failed ?? false)}
            </div>
          </div>
        ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Diagnostics & Retrieval</CardTitle></CardHeader>
        <CardContent className="space-y-2">
        <Button type="button" size="sm" variant="outline" onClick={() => setShowDiagnostics((v) => !v)}>
          {showDiagnostics ? 'Hide' : 'Show'} Diagnostics
        </Button>
        {showDiagnostics && (
          <div className="rounded border p-2 text-[11px]">
            <label className="mb-1 flex items-center gap-2">
              <input type="checkbox" checked={showDiagnosticsVerbose} onChange={(e) => setShowDiagnosticsVerbose(e.target.checked)} />
              dev verbose diagnostics
            </label>
            <div>status={diagnostics?.status ?? '-'} · mode={diagnostics?.mode ?? '-'}</div>
            <div>unresolved={(diagnostics?.unresolved_dependencies ?? []).join(', ') || 'none'}</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {Object.entries(diagnostics?.checks ?? {}).map(([k, v]) => (
                <Badge key={k} variant={v.ok ? 'success' : 'danger'}>{k}:{v.ok ? 'ok' : 'down'}</Badge>
              ))}
            </div>
          </div>
        )}
        <Button type="button" size="sm" variant="outline" onClick={() => setShowRetrievalDebug((v) => !v)}>
          {showRetrievalDebug ? 'Hide' : 'Show'} Retrieval Preview
        </Button>
        {showRetrievalDebug && (
          <div className="space-y-1 rounded border p-2 text-[11px]">
            {(retrievalPreview?.hits ?? []).map((hit) => (
              <div key={hit.chunk_id} className="border-b border-dashed pb-1">
                asset#{hit.asset_id} {hit.filename} · chunk#{hit.chunk_id} idx={hit.chunk_index} page={hit.page ?? '-'} · score={hit.score}
                <div>vector={hit.vector_score} · lexical={hit.lexical_score} · mode={hit.retrieval_mode} · ocr={String(hit.ocr_fallback_used ?? false)}</div>
                <div>{hit.snippet}</div>
              </div>
            ))}
            {!!retrievalPreview?.packed_context && (
              <details>
                <summary>packed context preview</summary>
                <pre className="whitespace-pre-wrap">{retrievalPreview.packed_context}</pre>
              </details>
            )}
            {(retrievalPreview?.hits ?? []).length === 0 && <small>No retrieval hits for current query.</small>}
          </div>
        )}
        </CardContent>
      </Card>
      </div>

      {usedAssetsLine && <Alert className="text-xs">Used assets: {usedAssetsLine}</Alert>}
      {!!divergence && (
        <Alert className="text-xs text-slate-700">
          {divergenceLabel} · overlap={divergence.overlap.toFixed(2)} · suggested label: {divergence.suggested_topic_label}
          {divergence.recommended_action === 'new_segment' && (
            <Button size="sm" variant="outline" className="ml-2" onClick={() => {
                if (!selectedChatId || !timeline.length) return;
                const lastUser = [...timeline].reverse().find((item) => item.role === 'user');
                if (!lastUser) return;
                branchMutation.mutate({ messageId: lastUser.id, topicLabel: divergence.suggested_topic_label });
              }}>
              새 segment로 분기
            </Button>
          )}
        </Alert>
      )}

      {orchestratorOn && (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Orchestration Detail</CardTitle>
            <Button size="sm" variant="outline" onClick={() => setShowRunDetail((v) => !v)}>{showRunDetail ? 'Hide' : 'Show'}</Button>
          </CardHeader>
          <CardContent>
          {showRunDetail && (
            <>
              <div className="mb-2 flex flex-wrap gap-2 text-xs">
                <Badge variant={runDetail?.run?.status === 'failed' ? 'danger' : runDetail?.run?.status === 'approval_pending' ? 'warning' : 'success'}>status={runDetail?.run?.status ?? '-'}</Badge>
                <Badge>approval={runDetail?.run?.approval_status ?? '-'}</Badge>
                <Badge>publish={runDetail?.run?.final_publish_status ?? '-'}</Badge>
                <Badge>active={runDetail?.run?.current_active_step ?? '-'}</Badge>
              </div>
              <div className="text-xs">Run Segment: {runDetail?.run?.segment_id ?? '-'} · topic: {runDetail?.run?.topic_label ?? '-'} · parent: {runDetail?.run?.parent_segment_id ?? '-'}</div>
              <div className="text-xs">Divergence reason: {runDetail?.run?.divergence_reason ?? '-'} · current step: {runDetail?.run?.current_active_step ?? '-'}</div>
              <div className="text-xs">
                Routing reason: {runDetail?.run?.routing_reason ?? '-'} · reviewer: {runDetail?.run?.reviewer_decision ?? '-'} · parent summary used: {String(runDetail?.run?.parent_segment_summary_used ?? false)}
              </div>
              <div className="text-xs">Used assets: {(runDetail?.run?.used_asset_ids ?? []).join(', ') || '-'} · used chunks: {(runDetail?.run?.used_chunk_ids ?? []).join(', ') || '-'} · image assets: {(runDetail?.run?.image_asset_ids ?? []).join(', ') || '-'}</div>
              <div className="text-xs">retrieval mode: {runDetail?.run?.retrieval_mode ?? '-'} · ocr used: {String(runDetail?.run?.ocr_used ?? false)}</div>
              <div className="text-xs">Critic model: {runDetail?.run?.critic_model ?? '-'} · critic summary: {runDetail?.run?.critic_summary ?? '-'}</div>
              <div className="text-xs">Specialist model: {runDetail?.run?.specialist_model ?? '-'} · specialist summary: {runDetail?.run?.specialist_summary ?? '-'}</div>
              <div className="text-xs">
                Role mapping check · reviewer(default={rolePreferenceByRole.reviewer?.default_model_name ?? '-'}) / critic(default={rolePreferenceByRole.critic?.default_model_name ?? '-'}) / specialist(default={rolePreferenceByRole.specialist?.default_model_name ?? '-'}) / orchestrator(default={rolePreferenceByRole.orchestrator?.default_model_name ?? '-'})
              </div>
              <div className="text-xs">
                Actual run · routing={runDetail?.run?.routing_reason ?? '-'} · reviewer_decision={runDetail?.run?.reviewer_decision ?? '-'} · critic_model={runDetail?.run?.critic_model ?? '-'} · specialist_model={runDetail?.run?.specialist_model ?? '-'}
              </div>
              <div className="text-xs">
                Final responder model={runDetail?.final_message?.model_name ?? '-'} (default={rolePreferenceByRole.final_responder?.default_model_name ?? '-'})
              </div>
              <div className="text-xs">Approval: {runDetail?.run?.approval_status ?? '-'} · publish: {runDetail?.run?.final_publish_status ?? '-'}</div>
              {runDetail?.run?.pending_final_draft && (
                <div className="mt-1 rounded border border-dashed p-2 text-xs">
                  Pending draft: {runDetail.run.pending_final_draft.slice(0, 300)}
                </div>
              )}
              {runDetail?.run?.approval_status === 'pending' && selectedRunId && (
                <div className="mt-1 flex gap-2">
                  <Button size="sm" onClick={() => approveRunMutation.mutate(selectedRunId)}>Approve publish</Button>
                  <Button size="sm" variant="destructive" onClick={() => rejectRunMutation.mutate(selectedRunId)}>Reject run</Button>
                </div>
              )}
              {runDetail?.run?.approval_status === 'pending' && (
                <Alert className="mt-1 border-amber-200 bg-amber-50 text-amber-700">
                  승인 전 draft이며 publish 후 메시지/아티팩트/provenance가 즉시 timeline에 반영됩니다.
                </Alert>
              )}
              {runDetail?.run?.approval_status === 'approved' && runDetail?.final_message && (
                <Alert className="mt-1 border-emerald-200 bg-emerald-50 text-emerald-700">
                  Published result: {runDetail.final_message.content_markdown.slice(0, 220)}
                </Alert>
              )}
              {runs.map((r) => <Button key={r.id} size="sm" variant="outline" onClick={() => { setSelectedRunId(r.id); setShowOrchestrationDrawer(true); }} className="mr-1">#{r.id} {r.status}</Button>)}
              <Button type="button" size="sm" variant="outline" onClick={() => setShowOrchestrationDrawer(true)}>Open Visual Panel</Button>
              {runDetail?.steps?.length ? (
                <ol className="mt-2 list-decimal space-y-2 pl-4">
                  {runDetail.steps.map((step) => (
                    <li key={step.id} className={`rounded border p-2 text-xs ${activeStepId === step.id ? 'border-amber-200 bg-amber-50' : 'bg-slate-50/70'}`}>
                      <div><strong>{step.step_name}</strong> role={step.assigned_role} model={step.model_name ?? '-'}</div>
                      <div>input: {step.input_summary ?? '-'}</div>
                      <div>output: {step.output_summary ?? '-'}</div>
                      <div>routing_reason: {step.routing_reason ?? '-'} · reviewer_decision: {step.reviewer_decision ?? '-'} · execution_mode: {step.execution_mode ?? '-'} · duration={step.duration_ms ?? '-'}ms</div>
                      <div>used_asset_ids: {(step.used_asset_ids ?? []).join(', ') || '-'} · used_chunk_ids: {(step.used_chunk_ids ?? []).join(', ') || '-'} · image_asset_ids: {(step.image_asset_ids ?? []).join(', ') || '-'} · vision_used: {String(step.vision_used ?? false)}</div>
                      <div>used_segment: {step.used_segment_id ?? '-'} · parent_summary_used: {String(step.parent_segment_summary_used ?? false)} · retry={step.retry_count ?? 0} · fallback={step.fallback_model_name ?? '-'} ({step.fallback_reason ?? 'n/a'})</div>
                      <div>group={step.step_group ?? '-'} · depends_on={(step.depends_on_step_ids ?? []).join(', ') || '-'} · retrieval={step.retrieval_mode ?? '-'} · ocr={String(step.ocr_used ?? false)} · approval={step.approval_status ?? '-'}</div>
                    </li>
                  ))}
                </ol>
              ) : null}
              {!!liveEvents.length && (
                <div className="mt-2 space-y-1 border-t border-dashed pt-2 text-[11px]">
                  {liveEvents.map((evt, idx) => {
                    return (
                      <div key={`${evt.timestamp}-${idx}`} className="rounded border bg-slate-50 p-1">
                        <Badge variant={eventBadgeVariant(evt.event_type)}>{evt.event_type}</Badge>
                        <strong>{evt.event_type}</strong> · step={evt.step_name ?? '-'} · role={evt.assigned_role ?? '-'} · status={evt.status} · model={evt.model_name ?? '-'}
                        <div>retry={evt.retry_count ?? 0} · fallback={evt.fallback_model_name ?? '-'} ({evt.fallback_reason ?? 'n/a'}) · approval={evt.approval_status ?? '-'}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
          </CardContent>
        </Card>
      )}

      <Card>
      <CardContent className="pt-4">
      <form onSubmit={submit} className="flex flex-col gap-2">
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} placeholder="Type message..." className="min-h-24 rounded-md border p-2 text-sm" />
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {visionPending && <Badge variant="info">Vision badge: 이미지 업로드 감지됨</Badge>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          {orchestratorOn && (
            <label className="text-[11px]">
              <input type="checkbox" checked={requireApprovalBeforePublish} onChange={(e) => setRequireApprovalBeforePublish(e.target.checked)} />
              require approval before publish
            </label>
          )}
          <small className="text-xs text-slate-600">{sending ? 'Processing request...' : `Ready · scope=${queryScope}${queryScope === 'segment' ? `#${selectedSegmentId}` : ''}`}</small>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={previewStream}>Stream Preview</Button>
            <Button type="submit" size="sm" disabled={!canSend || sending}>Send</Button>
          </div>
        </div>
      </form>
      </CardContent>
      </Card>
      {streamPreview && <pre className="m-0 max-h-32 overflow-auto rounded-md border bg-slate-50 p-2 text-[11px]">{streamPreview}</pre>}
      {orchestratorOn && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Provenance card</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-[11px]">
          <div>run: {selectedRunId ?? '-'} · segment: {runDetail?.run?.used_segment_id ?? runDetail?.run?.segment_id ?? '-'}</div>
          <div>assets: {(runDetail?.run?.used_asset_ids ?? []).join(', ') || '-'}</div>
          <div>parent summary used: {String(runDetail?.run?.parent_segment_summary_used ?? false)}</div>
          <div>review outcome: {runDetail?.run?.reviewer_decision ?? '-'}</div>
          <div>revised final: {latestAssistant?.model_role === 'final_responder_revised' ? 'yes' : 'no'}</div>
          {provenanceLine && <div>{provenanceLine}</div>}
          {runDetail?.final_message?.final_provenance_summary && <div>{runDetail.final_message.final_provenance_summary}</div>}
          </CardContent>
        </Card>
      )}
      {surfaceError && (
        <Alert className="border-red-200 bg-red-50 text-red-700">
          <div><strong>요청 처리 실패</strong></div>
          <div>{surfaceError.message}</div>
          <div className="mt-1">복구 안내: {recoveryHint}</div>
          <Button size="sm" variant="outline" className="mt-2" onClick={() => {
            qc.invalidateQueries({ queryKey: ['messages', selectedChatId] });
            qc.invalidateQueries({ queryKey: ['orchestration-run-detail', selectedRunId] });
          }}>Retry load</Button>
        </Alert>
      )}
      {showOrchestrationDrawer && (
        <aside className="fixed right-0 top-0 z-50 h-full w-[430px] overflow-auto border-l bg-white p-3 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <strong className="text-sm">Orchestration Visual Panel</strong>
            <Button size="sm" variant="outline" onClick={() => setShowOrchestrationDrawer(false)}>Close</Button>
          </div>
          <div className="mb-2 flex flex-wrap gap-1 text-xs">
            <Badge>run #{selectedRunId ?? '-'}</Badge>
            <Badge variant={statusBadgeVariant(runDetail?.run?.status)}>{runDetail?.run?.status ?? '-'}</Badge>
            <Badge variant={statusBadgeVariant(runDetail?.run?.approval_status)}>{runDetail?.run?.approval_status ?? '-'}</Badge>
            <Badge>routing={runDetail?.run?.routing_reason ?? '-'}</Badge>
          </div>
          <p className="text-xs text-slate-600">graph steps={runDetail?.run?.execution_graph_summary?.step_count ?? 0} · artifacts={(runDetail?.run?.generated_artifact_ids ?? []).join(', ') || '-'}</p>
          <Separator className="my-2" />
          <ol className="space-y-2 pl-0">
            {(runDetail?.steps ?? []).map((step, index) => (
              <li key={step.id} className={`rounded border p-2 text-xs ${activeStepId === step.id ? 'border-amber-200 bg-amber-50' : 'bg-slate-50/70'}`}>
                <div className="mb-1 flex items-center gap-1">
                  <Badge>#{index + 1}</Badge>
                  <span className="font-medium">{step.step_name}</span>
                  <Badge variant={statusBadgeVariant(step.status)}>{step.status}</Badge>
                </div>
                <div>role={step.assigned_role} · model={step.model_name ?? '-'}</div>
                <div>routing={step.routing_reason ?? '-'} · reviewer={step.reviewer_decision ?? '-'}</div>
                <div>retry={step.retry_count ?? 0} · fallback={step.fallback_model_name ?? '-'} ({step.fallback_reason ?? 'n/a'})</div>
                <div>used assets={(step.used_asset_ids ?? []).join(', ') || '-'} · used chunks={(step.used_chunk_ids ?? []).join(', ') || '-'}</div>
                <div>approval={step.approval_status ?? '-'} · metadata keys={Object.keys(step.step_metadata ?? {}).join(', ') || '-'}</div>
              </li>
            ))}
          </ol>
          <Separator className="my-2" />
          {(runDetail?.run?.artifact_summary ?? []).map((a) => (
            <div key={a.id} className="text-xs">
              artifact#{a.id} {a.filename} ({a.producing_model ?? '-'}/{a.producing_role ?? '-'})
            </div>
          ))}
        </aside>
      )}
    </main>
  );
}
