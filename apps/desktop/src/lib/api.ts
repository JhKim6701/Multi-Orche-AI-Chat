const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error('request failed');
  return res.json() as Promise<T>;
}
