const api = process.env.VITE_API_BASE_URL || 'http://localhost:8000';

function status(ok) {
  return ok ? 'ok' : 'degraded';
}

function normalizeChecks(payload) {
  const checks = payload?.checks || {};
  return {
    backend: Boolean(checks.database?.ok),
    database: Boolean(checks.database?.ok),
    ollama: Boolean(checks.ollama?.ok),
    qdrant: Boolean(checks.qdrant?.ok),
    upload_root: Boolean(checks.upload_root?.ok),
    migration: Boolean(checks.migration?.ok),
  };
}

function renderChecklist(checks) {
  const labels = [
    ['backend', checks.backend],
    ['database', checks.database],
    ['ollama', checks.ollama],
    ['qdrant', checks.qdrant],
    ['upload_root', checks.upload_root],
    ['migration', checks.migration],
  ];
  return labels.map(([name, ok]) => `[doctor] ${name}: ${status(ok)}`);
}

export async function runDoctor(fetchImpl = fetch) {
  const healthRes = await fetchImpl(`${api}/system/health`);
  if (!healthRes.ok) {
    throw new Error(`[doctor] API health endpoint failed: ${healthRes.status}`);
  }
  const health = await healthRes.json();
  const checks = normalizeChecks(health);
  const healthLines = [
    `[doctor] mode=${health.mode} env=${health.env} status=${health.status}`,
    ...renderChecklist(checks),
  ];

  const readyRes = await fetchImpl(`${api}/system/readiness`);
  if (!readyRes.ok) {
    throw new Error(`[doctor] readiness endpoint failed: ${readyRes.status}`);
  }
  const readiness = await readyRes.json();
  const readinessState = readiness.ready ? 'ready' : 'not-ready';
  const unresolved = (readiness.unresolved_dependencies || []).join(', ') || 'none';

  const advice = readiness.ready
    ? '[doctor] preflight: all dependencies ready. You can run desktop orchestration flows.'
    : `[doctor] preflight: blocked by unresolved dependencies (${unresolved}).`;
  const hint = `[doctor] recovery: ${readiness.doctor_hint || 'Check backend/Ollama/Qdrant/database and rerun doctor.'}`;

  return [...healthLines, `[doctor] readiness=${readinessState}`, advice, hint];
}

async function main() {
  try {
    const lines = await runDoctor();
    lines.forEach((line) => console.log(line));
  } catch (err) {
    console.error((err && err.message) || `[doctor] Unable to reach API at ${api}. Start backend first.`);
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
