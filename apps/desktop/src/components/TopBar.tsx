import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../lib/api';

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

export function TopBar() {
  const qc = useQueryClient();
  const { data, refetch: refetchHw } = useQuery({ queryKey: ['hardware'], queryFn: () => api.get<Hardware>('/system/hardware'), refetchInterval: 3000 });
  const { data: health, refetch: refetchHealth } = useQuery({ queryKey: ['health'], queryFn: () => api.get<Health>('/system/health'), refetchInterval: 5000 });
  const { data: runtime } = useQuery({ queryKey: ['runtime-info'], queryFn: () => api.get<RuntimeInfo>('/system/runtime-info'), refetchInterval: 15000 });

  const gpuToggle = useMutation({
    mutationFn: (enabled: boolean) => api.post<{ gpu_enabled: boolean }>('/system/gpu-state', { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hardware'] });
      qc.invalidateQueries({ queryKey: ['runtime-info'] });
    }
  });

  const degraded = health?.status === 'degraded';

  return (
    <header style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 8, borderBottom: '1px solid #ddd', fontSize: 12, background: degraded ? '#fff6f6' : '#fafafa' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong>mode={health?.mode ?? '-'}</strong>
        <span>env={health?.env ?? '-'}</span>
        <span>api={health?.status ?? 'unknown'}</span>
        <span>db={health?.checks?.database?.ok ? 'ok' : 'down'}</span>
        <span>ollama={health?.checks?.ollama?.ok ? 'ok' : 'down'}</span>
        <span>qdrant={health?.checks?.qdrant?.ok ? 'ok' : 'down'}</span>
        <span>upload={health?.checks?.upload_root?.ok ? 'ok' : 'down'}</span>
        <button style={{ fontSize: 11 }} onClick={() => { refetchHealth(); refetchHw(); }}>Retry checks</button>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <span>CPU {data?.cpu_percent?.toFixed(1) ?? '-'}%</span>
        <span>MEM {data?.memory_percent?.toFixed(1) ?? '-'}%</span>
        <span>DISK {data?.disk_percent?.toFixed(1) ?? '-'}%</span>
        <span>GPU HW {data?.gpu_available ? 'available' : 'N/A'}</span>
        <span>GPU USE {data?.gpu_usage?.toFixed(1) ?? '-'}%</span>
        <span>GPU MEM {data?.gpu_memory?.toFixed(1) ?? '-'}%</span>
        <button style={{ fontSize: 11 }} onClick={() => gpuToggle.mutate(!(data?.gpu_enabled ?? true))}>GPU ROUTING {data?.gpu_enabled ? 'ON' : 'OFF'}</button>
        <span style={{ color: '#555' }}>data_root={runtime?.data_root ?? health?.data_root ?? '-'}</span>
        <span style={{ color: '#555' }}>api={import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}</span>
        <span style={{ color: '#555' }}>ollama={runtime?.ollama_base_url ?? '-'}</span>
      </div>
      {degraded && (
        <div style={{ color: '#b42318', fontSize: 11 }}>
          의존성 준비가 완료되지 않았습니다. Ollama/Qdrant/API 경로 설정을 확인하고 Retry checks를 눌러주세요.
        </div>
      )}
    </header>
  );
}
