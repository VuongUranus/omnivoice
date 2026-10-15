async function req(url, opts) {
  const r = await fetch(url, opts)
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return r.json()
}
const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => req('/api/health'),
  meta: () => req('/api/meta'),
  voices: () => req('/api/voices'),
  createVoice: (form) => req('/api/voices', { method: 'POST', body: form }),
  deleteVoice: (key) => req(`/api/voices?key=${encodeURIComponent(key)}`, { method: 'DELETE' }),
  previewVoice: (form) => req('/api/voices/preview', { method: 'POST', body: form }),
  transcribe: (form) => req('/api/transcribe', { method: 'POST', body: form }),
  generate: (body) => req('/api/generate', json('POST', body)),
  history: () => req('/api/history'),
  deleteHistory: (id) => req(`/api/history/${id}`, { method: 'DELETE' }),
  clearHistory: () => req('/api/history', { method: 'DELETE' }),
}
