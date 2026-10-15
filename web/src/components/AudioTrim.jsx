import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Download, Inbox, Loader2, Pause, Play, Send } from 'lucide-react'
import { clip } from '../audioCheck'
import { decodeAudio, encodeWav } from '../wav'
import { Button, Select } from './ui'

const MIN_SEL = 0.05 // đoạn chọn ngắn nhất (giây)
const WAVE_H = 160
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))
const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`

// Biên độ lớn nhất của mỗi "ô" thời gian, dùng để vẽ sóng âm
function computePeaks(buf, bins = 2000) {
  const n = buf.length, peaks = new Float32Array(bins)
  const chans = Array.from({ length: buf.numberOfChannels }, (_, c) => buf.getChannelData(c))
  const step = n / bins
  for (let b = 0; b < bins; b++) {
    const from = Math.floor(b * step), to = Math.max(from + 1, Math.floor((b + 1) * step))
    let m = 0
    for (const ch of chans) for (let i = from; i < to && i < n; i++) { const a = Math.abs(ch[i]); if (a > m) m = a }
    peaks[b] = m
  }
  return peaks
}

// Ghép kết quả cắt thành file WAV. keep: giữ [start,end); remove: bỏ [start,end) rồi nối hai phần còn lại.
function renderCut(buf, start, end, mode, name) {
  const sr = buf.sampleRate
  const a = Math.round(start * sr), b = Math.round(end * sr)
  const chans = Array.from({ length: buf.numberOfChannels }, (_, c) => buf.getChannelData(c))
  let out
  if (mode === 'keep') {
    out = chans.map((ch) => ch.slice(a, b))
  } else {
    out = chans.map((ch) => {
      const o = new Float32Array(a + (ch.length - b))
      o.set(ch.subarray(0, a)); o.set(ch.subarray(b), a)
      const f = a > 0 && b < ch.length ? Math.min(Math.round(0.003 * sr), a, ch.length - b) : 0 // fade 3ms tại điểm nối để không bị tiếng "tách"
      for (let i = 0; i < f; i++) { o[a - 1 - i] *= i / f; o[a + i] *= i / f }
      return o
    })
  }
  return new File([encodeWav(out, sr)], name, { type: 'audio/wav' })
}

function TimeField({ label, value, min, max, onCommit }) {
  const [text, setText] = useState(value.toFixed(2))
  const focused = useRef(false)
  useEffect(() => { if (!focused.current) setText(value.toFixed(2)) }, [value])
  const commit = () => {
    focused.current = false
    const n = parseFloat(text.replace(',', '.'))
    if (Number.isFinite(n)) onCommit(clamp(n, min, max))
    setText(value.toFixed(2))
  }
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex items-center gap-2">
        <input value={text} inputMode="decimal" onFocus={() => { focused.current = true }} onChange={(e) => setText(e.target.value)}
          onBlur={commit} onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          className="w-24 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm tabular-nums outline-none focus:border-brand-500 dark:border-slate-800 dark:bg-slate-900" />
        <span className="text-xs text-slate-400">giây · {fmt(value)}</span>
      </div>
    </label>
  )
}

function Waveform({ peaks, duration, start, end, mode, pos, onChange }) {
  const wrap = useRef(null), canvas = useRef(null), drag = useRef(null)
  const [w, setW] = useState(0)

  useEffect(() => {
    const el = wrap.current
    const ro = new ResizeObserver(() => setW(el.clientWidth))
    ro.observe(el); setW(el.clientWidth)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const c = canvas.current
    if (!c || !w) return
    const dpr = window.devicePixelRatio || 1
    c.width = w * dpr; c.height = WAVE_H * dpr
    const g = c.getContext('2d')
    g.scale(dpr, dpr)
    const dark = document.documentElement.classList.contains('dark')
    const bars = Math.floor(w / 3), n = peaks.length
    for (let i = 0; i < bars; i++) {
      const from = Math.floor((i / bars) * n), to = Math.max(from + 1, Math.floor(((i + 1) / bars) * n))
      let p = 0
      for (let k = from; k < to; k++) if (peaks[k] > p) p = peaks[k]
      const t = ((i + 0.5) / bars) * duration
      const inside = t >= start && t <= end
      g.fillStyle = (mode === 'keep' ? inside : !inside) ? '#7c5cfc' : dark ? '#334155' : '#cbd5e1'
      const h = Math.max(2, p * WAVE_H * 0.92)
      g.fillRect(i * 3, (WAVE_H - h) / 2, 2, h)
    }
  }, [peaks, w, start, end, mode, duration])

  const timeAt = (x) => {
    const r = wrap.current.getBoundingClientRect()
    return clamp((x - r.left) / r.width, 0, 1) * duration
  }
  const down = (e) => {
    e.preventDefault()
    wrap.current.setPointerCapture(e.pointerId)
    const t = timeAt(e.clientX)
    let kind = e.target.dataset.kind || 'new'
    if (kind === 'move' && end - start >= duration - 0.001) kind = 'new' // chưa chọn gì (đang chọn cả file): kéo là vẽ vùng chọn mới
    drag.current = { kind, t0: t, s0: start, e0: end }
  }
  const move = (e) => {
    const d = drag.current
    if (!d) return
    const t = timeAt(e.clientX)
    if (d.kind === 'start') onChange(clamp(t, 0, d.e0 - MIN_SEL), d.e0)
    else if (d.kind === 'end') onChange(d.s0, clamp(t, d.s0 + MIN_SEL, duration))
    else if (d.kind === 'move') {
      const len = d.e0 - d.s0, s = clamp(d.s0 + (t - d.t0), 0, duration - len)
      onChange(s, s + len)
    } else {
      const a = Math.min(d.t0, t), b = Math.max(d.t0, t)
      const s = Math.min(a, duration - MIN_SEL)
      onChange(s, Math.max(b, s + MIN_SEL))
    }
  }
  const up = () => { drag.current = null }
  const key = (kind) => (e) => {
    const step = (e.shiftKey ? 1 : 0.05) * (e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0)
    if (!step) return
    e.preventDefault()
    if (kind === 'start') onChange(clamp(start + step, 0, end - MIN_SEL), end)
    else onChange(start, clamp(end + step, start + MIN_SEL, duration))
  }

  const pct = (t) => `${(t / duration) * 100}%`
  const handle = 'absolute top-0 z-10 flex h-full w-3 -translate-x-1/2 cursor-ew-resize items-center justify-center outline-none'
  const grip = 'pointer-events-none h-10 w-1 rounded-full bg-brand-500'

  return (
    <div ref={wrap} data-testid="waveform" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
      className="relative cursor-crosshair touch-none select-none overflow-hidden rounded-xl bg-slate-50 dark:bg-slate-900" style={{ height: WAVE_H }}>
      <canvas ref={canvas} style={{ width: '100%', height: WAVE_H }} />
      <div data-kind="move" className={`absolute top-0 h-full cursor-grab border-x-2 ${mode === 'keep' ? 'border-brand-500 bg-brand-500/10' : 'border-red-400 bg-red-500/10'}`}
        style={{ left: pct(start), width: pct(end - start) }} />
      <div data-kind="start" role="slider" tabIndex={0} aria-label="Điểm bắt đầu" aria-valuemin={0} aria-valuemax={duration} aria-valuenow={start}
        onKeyDown={key('start')} className={handle} style={{ left: pct(start) }}><span className={grip} /></div>
      <div data-kind="end" role="slider" tabIndex={0} aria-label="Điểm kết thúc" aria-valuemin={0} aria-valuemax={duration} aria-valuenow={end}
        onKeyDown={key('end')} className={handle} style={{ left: pct(end) }}><span className={grip} /></div>
      {pos > 0 && <div className="pointer-events-none absolute top-0 h-full w-px bg-slate-900 dark:bg-white" style={{ left: pct(pos) }} />}
    </div>
  )
}

export default function AudioTrim({ history, limits, onUseForClone }) {
  const [file, setFile] = useState(null)
  const [audio, setAudio] = useState(null) // { buf, peaks, duration, url }
  const [decoding, setDecoding] = useState(false)
  const [error, setError] = useState(null)
  const [sel, setSel] = useState({ start: 0, end: 0 })
  const [mode, setMode] = useState('keep')
  const [playing, setPlaying] = useState(false)
  const [pos, setPos] = useState(0)
  const [drag, setDrag] = useState(false)
  const el = useRef(null), raf = useRef(0), inputRef = useRef(null)
  const live = useRef({})
  live.current = { sel, mode }

  useEffect(() => () => cancelAnimationFrame(raf.current), [])
  useEffect(() => () => audio && URL.revokeObjectURL(audio.url), [audio])

  const stop = () => { cancelAnimationFrame(raf.current); el.current?.pause(); setPlaying(false) }

  const load = async (f) => {
    if (!f) return
    stop(); setError(null); setDecoding(true)
    try {
      const buf = await decodeAudio(f)
      if (!buf.length) throw new Error('empty')
      setAudio({ buf, peaks: computePeaks(buf), duration: buf.duration, url: URL.createObjectURL(f) })
      setFile(f); setSel({ start: 0, end: buf.duration }); setMode('keep'); setPos(0)
    } catch {
      setError('Không đọc được file âm thanh này. Hãy thử WAV, MP3, M4A hoặc OGG.')
    } finally { setDecoding(false) }
  }

  const loadHistory = async (id) => {
    const it = history.find((h) => h.id === id)
    if (!it) return
    setError(null); setDecoding(true)
    try {
      const blob = await (await fetch(it.audio_url)).blob()
      await load(new File([blob], `${it.id}.wav`, { type: 'audio/wav' }))
    } catch { setError('Không tải được audio từ lịch sử.'); setDecoding(false) }
  }

  const tick = () => {
    const a = el.current
    if (!a) return
    const { sel: s, mode: m } = live.current
    let t = a.currentTime
    if (m === 'keep' && t >= s.end) { a.pause(); setPlaying(false); setPos(s.end); return }
    if (m === 'remove' && t >= s.start && t < s.end) { a.currentTime = s.end; t = s.end } // bỏ qua đoạn bị cắt
    setPos(t)
    if (a.ended || a.paused) { setPlaying(false); return }
    raf.current = requestAnimationFrame(tick)
  }
  const preview = () => {
    if (playing) return stop()
    const a = el.current
    a.currentTime = mode === 'keep' ? sel.start : 0
    a.play(); setPlaying(true)
    raf.current = requestAnimationFrame(tick)
  }

  const cutName = file ? `${file.name.replace(/\.[^.]+$/, '')}_cut.wav` : 'cut.wav'
  const download = () => {
    const out = renderCut(audio.buf, sel.start, sel.end, mode, cutName)
    const url = URL.createObjectURL(out)
    const a = document.createElement('a'); a.href = url; a.download = cutName; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const duration = audio?.duration ?? 0
  const resultLen = audio ? (mode === 'keep' ? sel.end - sel.start : duration - (sel.end - sel.start)) : 0
  // Đối chiếu với luật của Voice Clone do server công bố (cùng nguồn với trang Voice Clone)
  const cloneHint = (() => {
    if (!limits) return null
    const [lo, hi] = limits.ref_recommended_seconds
    if (resultLen < limits.ref_min_seconds) return { level: 'error', text: `Ngắn hơn mức tối thiểu ${limits.ref_min_seconds}s của Voice Clone` }
    if (resultLen > limits.ref_max_seconds) return { level: 'error', text: `Dài hơn mức tối đa ${limits.ref_max_seconds}s của Voice Clone` }
    if (resultLen < lo || resultLen > hi) return { level: 'warn', text: `Voice Clone cho kết quả tốt nhất với đoạn dài ${lo}–${hi}s` }
    return { level: 'ok', text: 'Độ dài phù hợp để làm audio mẫu cho Voice Clone' }
  })()
  const sendToClone = () => onUseForClone(renderCut(audio.buf, sel.start, sel.end, mode, cutName))

  const histOptions = history.map((h) => ({ value: h.id, label: `${h.voice_name}: ${clip(h.text || '', 60)}` }))
  const setRange = (start, end) => setSel({ start, end })

  return (
    <div className="mx-auto max-w-3xl pb-8">
      <h1 className="text-2xl font-bold tracking-tight">Cắt audio</h1>
      <p className="mb-8 mt-1 text-sm text-slate-500">Kéo trên sóng âm để chọn đoạn, giữ lại hoặc xoá đoạn đó, rồi tải về dạng WAV. Xử lý ngay trên trình duyệt, file không bị gửi đi đâu.</p>

      <div className="flex flex-wrap items-stretch gap-3">
        <button onClick={() => inputRef.current.click()} onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); load(e.dataTransfer.files[0]) }}
          className={`flex min-w-[260px] flex-1 items-center gap-3 rounded-2xl border border-dashed px-5 ${audio ? 'py-3' : 'h-36 flex-col justify-center'} transition ${drag ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-slate-200 bg-slate-50 hover:border-brand-400 dark:border-slate-800 dark:bg-slate-900'}`}>
          {decoding ? <Loader2 size={26} className="animate-spin text-brand-500" /> : <Inbox size={audio ? 22 : 30} className="text-brand-500" />}
          <span className={audio ? 'text-left' : 'text-center'}>
            <span className="block truncate text-sm font-semibold">{decoding ? 'Đang đọc file…' : audio ? `${file.name} · ${fmt(duration)}` : 'Kéo thả file hoặc bấm để chọn'}</span>
            <span className="block text-xs text-slate-400">{audio ? 'Bấm để đổi file khác' : 'WAV, MP3, M4A, OGG… (tuỳ trình duyệt hỗ trợ)'}</span>
          </span>
        </button>
        <input ref={inputRef} type="file" accept="audio/*" hidden onChange={(e) => { load(e.target.files[0]); e.target.value = '' }} />
        {history.length > 0 && (
          <div className="flex w-72 flex-col justify-center gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hoặc từ lịch sử</span>
            <Select value="" options={histOptions} onChange={loadHistory} searchable searchPlaceholder="Tìm trong lịch sử…" placeholder="Chọn bản đã tạo…" />
          </div>
        )}
      </div>
      {error && <p className="mt-3 flex items-start gap-1.5 text-sm text-red-600"><AlertTriangle size={15} className="mt-0.5 shrink-0" />{error}</p>}

      {audio && (
        <div className="mt-6 space-y-5">
          <audio ref={el} src={audio.url} onPause={() => setPlaying(false)} onEnded={() => { setPlaying(false); setPos(0) }} />
          <Waveform peaks={audio.peaks} duration={duration} start={sel.start} end={sel.end} mode={mode} pos={pos} onChange={setRange} />

          <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
            <TimeField label="Bắt đầu" value={sel.start} min={0} max={sel.end - MIN_SEL} onCommit={(v) => setRange(v, sel.end)} />
            <TimeField label="Kết thúc" value={sel.end} min={sel.start + MIN_SEL} max={duration} onCommit={(v) => setRange(sel.start, v)} />
            <div className="ml-auto inline-flex rounded-xl bg-slate-100 p-1 text-sm dark:bg-slate-800" role="radiogroup" aria-label="Kiểu cắt">
              {[['keep', 'Giữ đoạn đã chọn'], ['remove', 'Xoá đoạn đã chọn']].map(([id, l]) => (
                <button key={id} role="radio" aria-checked={mode === id} onClick={() => { stop(); setMode(id) }}
                  className={`rounded-lg px-3 py-1.5 font-medium transition ${mode === id ? 'bg-white shadow-sm dark:bg-slate-950' : 'text-slate-500 hover:text-slate-800'}`}>{l}</button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-slate-50 p-4 dark:bg-slate-900">
            <div>
              <div className="text-sm font-semibold" data-testid="result-len">Kết quả: {resultLen.toFixed(2)}s <span className="font-normal text-slate-400">({fmt(resultLen)})</span></div>
              {cloneHint && (
                <p className={`mt-1 flex items-center gap-1.5 text-xs ${cloneHint.level === 'error' ? 'text-red-600' : cloneHint.level === 'warn' ? 'text-amber-600' : 'text-emerald-600'}`}>
                  {cloneHint.level === 'ok' ? <Check size={13} /> : <AlertTriangle size={13} />}{cloneHint.text}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={preview} className="border border-slate-200 dark:border-slate-700">
                {playing ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" />} {playing ? 'Dừng' : 'Nghe thử kết quả'}
              </Button>
              <Button variant="outline" onClick={sendToClone} disabled={resultLen <= 0 || cloneHint?.level === 'error'} title={cloneHint?.level === 'error' ? cloneHint.text : ''}>
                <Send size={15} /> Dùng cho Voice Clone
              </Button>
              <Button onClick={download} disabled={resultLen <= 0}><Download size={15} /> Tải WAV</Button>
            </div>
          </div>
          <p className="text-xs text-slate-400">Mẹo: kéo vào vùng chọn để dời cả đoạn, kéo hai mép để chỉnh điểm đầu/cuối, hoặc dùng phím ← → (giữ Shift để nhảy 1 giây) khi đang chọn một mép.</p>
        </div>
      )}
    </div>
  )
}
