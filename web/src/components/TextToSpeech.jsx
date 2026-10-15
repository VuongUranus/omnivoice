import { useState } from 'react'
import { Loader2, Sparkles, SlidersHorizontal } from 'lucide-react'
import { api } from '../api'
import { Button, Card, Field, PageHeader, VoiceAvatar, inputCls } from './ui'

const MAX = 5000

export default function TextToSpeech({ voices, languages, selected, onSelect, ready, onGenerated }) {
  const [text, setText] = useState('')
  const [instruct, setInstruct] = useState('')
  const [language, setLanguage] = useState('Auto')
  const [speed, setSpeed] = useState(1)
  const [cfg, setCfg] = useState(2)
  const [steps, setSteps] = useState(32)
  const [denoise, setDenoise] = useState(true)
  const [pre, setPre] = useState(true)
  const [post, setPost] = useState(true)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)

  const generate = async () => {
    setBusy(true); setStatus(null)
    try {
      const item = await api.generate({
        text, voice: selected, instruct, language, speed, guidance_scale: cfg, num_step: steps,
        denoise, preprocess_prompt: pre, postprocess_output: post,
      })
      onGenerated(item)
      setStatus({ ok: true, msg: `Hoàn thành · ${item.duration}s âm thanh · ${item.elapsed}s xử lý` })
    } catch (e) {
      setStatus({ ok: false, msg: e.message })
    } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Text to Speech" subtitle="Chuyển văn bản thành giọng nói tự nhiên với giọng bạn chọn." />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card>
            <textarea
              value={text} maxLength={MAX} onChange={(e) => setText(e.target.value)} rows={11}
              placeholder="Nhập hoặc dán văn bản cần đọc tại đây…"
              className="w-full resize-none bg-transparent text-base leading-relaxed outline-none placeholder:text-slate-400"
            />
            <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 dark:border-slate-800">
              <span className="text-xs text-slate-500">{text.length.toLocaleString()} / {MAX.toLocaleString()} ký tự</span>
              <Button onClick={generate} disabled={busy || !ready || !text.trim() || !selected}>
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {busy ? 'Đang tạo…' : 'Tạo giọng nói'}
              </Button>
            </div>
          </Card>
          {status && (
            <div className={`rounded-xl px-4 py-3 text-sm ${status.ok ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'}`}>
              {status.msg}
            </div>
          )}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Chọn giọng</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {voices.map((v) => (
                <button key={v.key} onClick={() => onSelect(v.key)}
                  className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                    selected === v.key ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20 dark:bg-brand-500/10'
                      : 'border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700'}`}>
                  <VoiceAvatar voice={v} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{v.name}</div>
                    <div className="truncate text-xs text-slate-500">{v.style_tag}</div>
                    <div className="mt-1 line-clamp-2 text-xs text-slate-400">{v.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <Card className="h-fit space-y-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><SlidersHorizontal size={16} /> Cài đặt</h2>
          <Field label="Ngôn ngữ">
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className={inputCls}>
              {languages.map((l) => <option key={l}>{l}</option>)}
            </select>
          </Field>
          <Field label="Chỉ dẫn giọng (tuỳ chọn)">
            <input value={instruct} onChange={(e) => setInstruct(e.target.value)} placeholder="male, low pitch, calm" className={inputCls} />
          </Field>
          <Field label="Tốc độ" hint={`${speed.toFixed(2)}x`}>
            <input type="range" min="0.5" max="2" step="0.05" value={speed} onChange={(e) => setSpeed(+e.target.value)} className="w-full" />
          </Field>
          <Field label="Guidance scale" hint={cfg.toFixed(1)}>
            <input type="range" min="0.5" max="6" step="0.1" value={cfg} onChange={(e) => setCfg(+e.target.value)} className="w-full" />
          </Field>
          <Field label="Số bước" hint={steps}>
            <input type="range" min="8" max="64" step="1" value={steps} onChange={(e) => setSteps(+e.target.value)} className="w-full" />
          </Field>
          <div className="space-y-2 border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
            {[['Khử nhiễu', denoise, setDenoise], ['Tiền xử lý audio mẫu', pre, setPre], ['Hậu xử lý đầu ra', post, setPost]].map(([l, v, s]) => (
              <label key={l} className="flex cursor-pointer items-center justify-between">
                {l}<input type="checkbox" checked={v} onChange={(e) => s(e.target.checked)} className="h-4 w-4 accent-brand-500" />
              </label>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}
