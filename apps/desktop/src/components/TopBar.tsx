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

export function TopBar() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['hardware'], queryFn: () => api.get<Hardware>('/system/hardware'), refetchInterval: 3000 });
  const gpuToggle = useMutation({
    mutationFn: (enabled: boolean) => api.post<{ gpu_enabled: boolean }>('/system/gpu-state', { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hardware'] });
    }
  });

  return (
    <header style={{ display: 'flex', gap: 12, padding: 8, borderBottom: '1px solid #ddd', fontSize: 12 }}>
      <span>CPU {data?.cpu_percent?.toFixed(1) ?? '-'}%</span>
      <span>MEM {data?.memory_percent?.toFixed(1) ?? '-'}%</span>
      <span>DISK {data?.disk_percent?.toFixed(1) ?? '-'}%</span>
      <span>GPU HW {data?.gpu_available ? 'available' : 'N/A'}</span>
      <span>GPU USE {data?.gpu_usage?.toFixed(1) ?? '-'}%</span>
      <span>GPU MEM {data?.gpu_memory?.toFixed(1) ?? '-'}%</span>
      <button
        style={{ fontSize: 11 }}
        onClick={() => gpuToggle.mutate(!(data?.gpu_enabled ?? true))}
      >
        GPU ROUTING {data?.gpu_enabled ? 'ON' : 'OFF'}
      </button>
      <span style={{ color: '#555' }}>GPU OFF 시 vision/reasoning 모델 fallback 적용</span>
    </header>
  );
}
