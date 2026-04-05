import { useQuery } from '@tanstack/react-query';

import { getJson } from '../lib/api';

type Hardware = { cpu_percent: number; memory_percent: number; disk_percent: number; gpu_available: boolean };

export function TopBar() {
  const { data } = useQuery({ queryKey: ['hardware'], queryFn: () => getJson<Hardware>('/system/hardware'), refetchInterval: 3000 });

  return (
    <header style={{ display: 'flex', gap: 12, padding: 8, borderBottom: '1px solid #ddd', fontSize: 12 }}>
      <span>CPU {data?.cpu_percent?.toFixed(1) ?? '-'}%</span>
      <span>MEM {data?.memory_percent?.toFixed(1) ?? '-'}%</span>
      <span>DISK {data?.disk_percent?.toFixed(1) ?? '-'}%</span>
      <span>GPU {data?.gpu_available ? 'ON' : 'N/A'}</span>
    </header>
  );
}
