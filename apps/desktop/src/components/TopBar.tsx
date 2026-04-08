import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../lib/api';
import { Alert } from './ui/alert';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';

type Hardware = {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  gpu_available: boolean;
  gpu_usage: number | null;
  gpu_memory: number | null;
  gpu_enabled: boolean;
};

type Health = {
  status: 'ok' | 'degraded';
  mode: 'web' | 'desktop';
  env: string;
  data_root: string;
  ollama_base_url: string;
  qdrant_url: string;
  checks: {
    database: { ok: boolean };
    ollama: { ok: boolean };
    qdrant: { ok: boolean };
    upload_root: { ok: boolean; path: string };
  };
  unresolved_dependencies?: string[];
  doctor_hint?: string;
};

type RuntimeInfo = {
  env: string;
  mode: string;
  data_root: string;
  upload_root: string;
  database_url: string;
  qdrant_url: string;
  ollama_base_url: string;
  gpu_enabled: boolean;
};

type Readiness = {
  ready: boolean;
  env: string;
  unresolved_dependencies: string[];
  doctor_hint?: string;
};

export function TopBar() {
  const qc = useQueryClient();
  const { data, refetch: refetchHw } = useQuery({ queryKey: ['hardware'], queryFn: () => api.get<Hardware>('/system/hardware'), refetchInterval: 3000 });
  const { data: health, refetch: refetchHealth } = useQuery({ queryKey: ['health'], queryFn: () => api.get<Health>('/system/health'), refetchInterval: 5000 });
  const { data: runtime } = useQuery({ queryKey: ['runtime-info'], queryFn: () => api.get<RuntimeInfo>('/system/runtime-info'), refetchInterval: 15000 });
  const { data: readiness, refetch: refetchReadiness } = useQuery({ queryKey: ['readiness'], queryFn: () => api.get<Readiness>('/system/readiness'), refetchInterval: 5000 });

  const gpuToggle = useMutation({
    mutationFn: (enabled: boolean) => api.post<{ gpu_enabled: boolean }>('/system/gpu-state', { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hardware'] });
      qc.invalidateQueries({ queryKey: ['runtime-info'] });
    }
  });

  const degraded = health?.status === 'degraded';
  const uiMode = (globalThis as any).__TAURI_INTERNALS__ ? 'desktop-ui' : 'web-ui';
  const startupReady = readiness?.ready ?? false;
  const unresolved = readiness?.unresolved_dependencies ?? health?.unresolved_dependencies ?? [];

  return (
    <header className="border-b border-border bg-muted p-2">
      <Card className={degraded ? 'border-red-200' : ''}>
        <CardContent className="space-y-2 p-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={startupReady ? 'success' : 'warning'}>startup={startupReady ? 'ready' : 'blocked'}</Badge>
            <Badge variant={health?.status === 'ok' ? 'success' : 'warning'}>runtime={health?.status ?? 'unknown'}</Badge>
            <Badge variant="info">mode={health?.mode ?? '-'}</Badge>
            <Badge>ui={uiMode}</Badge>
            <Badge>env={health?.env ?? '-'}</Badge>
            <Badge variant={health?.status === 'ok' ? 'success' : 'danger'}>api={health?.status ?? 'unknown'}</Badge>
            <Badge variant={health?.checks?.database?.ok ? 'success' : 'danger'}>db={health?.checks?.database?.ok ? 'ok' : 'down'}</Badge>
            <Badge variant={health?.checks?.ollama?.ok ? 'success' : 'danger'}>ollama={health?.checks?.ollama?.ok ? 'ok' : 'down'}</Badge>
            <Badge variant={health?.checks?.qdrant?.ok ? 'success' : 'danger'}>qdrant={health?.checks?.qdrant?.ok ? 'ok' : 'down'}</Badge>
            <Button size="sm" variant="outline" onClick={() => { refetchHealth(); refetchHw(); refetchReadiness(); }}>Retry checks</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>CPU {data?.cpu_percent?.toFixed(1) ?? '-'}%</Badge>
            <Badge>MEM {data?.memory_percent?.toFixed(1) ?? '-'}%</Badge>
            <Badge>DISK {data?.disk_percent?.toFixed(1) ?? '-'}%</Badge>
            <Badge>GPU HW {data?.gpu_available ? 'available' : 'N/A'}</Badge>
            <Badge>GPU USE {data?.gpu_usage?.toFixed(1) ?? '-'}%</Badge>
            <Badge>GPU MEM {data?.gpu_memory?.toFixed(1) ?? '-'}%</Badge>
            <Button size="sm" variant="outline" onClick={() => gpuToggle.mutate(!(data?.gpu_enabled ?? true))}>GPU ROUTING {data?.gpu_enabled ? 'ON' : 'OFF'}</Button>
            <span className="text-[11px] text-slate-600">data_root={runtime?.data_root ?? health?.data_root ?? '-'}</span>
          </div>
          <div className="rounded border border-dashed bg-white/70 p-2 text-[11px] text-slate-700">
            <div className="font-medium">Desktop preflight (before run)</div>
            <div>Backend={health?.checks?.database?.ok ? 'ready' : 'check'} · Ollama={health?.checks?.ollama?.ok ? 'ready' : 'check'} · Qdrant={health?.checks?.qdrant?.ok ? 'ready' : 'check'} · DB={health?.checks?.database?.ok ? 'ready' : 'check'}</div>
            <div>upload_root={health?.checks?.upload_root?.ok ? 'writable' : 'not-writable'} · runtime_gpu={runtime?.gpu_enabled ? 'on' : 'off'}</div>
          </div>
          {degraded && (
            <Alert className="border-red-200 bg-red-50 text-red-700">
              의존성 준비가 완료되지 않았습니다. unresolved={unresolved.join(', ') || 'none'} · {readiness?.doctor_hint ?? health?.doctor_hint ?? 'npm run doctor로 점검하세요.'}
            </Alert>
          )}
        </CardContent>
      </Card>
    </header>
  );
}
