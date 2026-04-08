import test from 'node:test';
import assert from 'node:assert/strict';

import { runDoctor } from './doctor.mjs';

test('runDoctor prints readiness and recovery hint', async () => {
  const calls = [];
  const fetchStub = async (url) => {
    calls.push(url);
    if (url.endsWith('/system/health')) {
      return {
        ok: true,
        json: async () => ({
          mode: 'desktop',
          env: 'desktop',
          status: 'degraded',
          checks: {
            database: { ok: true },
            ollama: { ok: false },
            qdrant: { ok: true },
            upload_root: { ok: true },
          },
        }),
      };
    }
    return {
      ok: true,
      json: async () => ({
        ready: false,
        unresolved_dependencies: ['ollama'],
        doctor_hint: 'start ollama and rerun doctor',
      }),
    };
  };

  const lines = await runDoctor(fetchStub);
  assert.equal(calls.length, 2);
  assert(lines.some((line) => line.includes('readiness=not-ready')));
  assert(lines.some((line) => line.includes('blocked by unresolved dependencies (ollama)')));
  assert(lines.some((line) => line.includes('start ollama and rerun doctor')));
});
