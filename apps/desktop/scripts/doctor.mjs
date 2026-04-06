const api = process.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function main() {
  try {
    const res = await fetch(`${api}/system/health`);
    if (!res.ok) {
      console.error(`[doctor] API health endpoint failed: ${res.status}`);
      process.exit(1);
    }
    const payload = await res.json();
    console.log(`[doctor] mode=${payload.mode} env=${payload.env} status=${payload.status}`);
    const checks = payload.checks || {};
    for (const [key, info] of Object.entries(checks)) {
      const ok = info && typeof info === 'object' && 'ok' in info ? info.ok : false;
      console.log(`[doctor] ${key}: ${ok ? 'ok' : 'degraded'}`);
    }
    if (payload.status !== 'ok') {
      console.warn('[doctor] Dependencies are degraded. You can still run UI, but execution may fail until dependencies recover.');
    }
    const readyRes = await fetch(`${api}/system/readiness`);
    if (readyRes.ok) {
      const ready = await readyRes.json();
      console.log(`[doctor] readiness=${ready.ready ? 'ready' : 'not-ready'}`);
    }
  } catch (err) {
    console.error(`[doctor] Unable to reach API at ${api}. Start backend first.`);
    process.exit(1);
  }
}

main();
