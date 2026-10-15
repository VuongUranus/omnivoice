import { usePersisted } from '../usePersisted'
import { useEffect, useRef, useState } from 'react'
import { Info, Inbox, Loader2, Mic, Save, Sparkles, Square, Trash2, Wand2 } from 'lucide-react'
import { api } from '../api'
import { Button, Select, Toggle, inputCls, langOptions } from './ui'

const SAMPLE = 'Xin chào, rất vui được hỗ trợ bạn. Hãy chọn một giọng nói phù hợp và cùng bắt đầu hành trình sáng tạo âm thanh nhé.'
const MAX_PREVIEW = 300
const MAX_MB = 20
export default function VoiceClone({ languages, onSaved, ready }) {
  const [file, setFile] = useState(null)
  const [fileUrl, setFileUrl] = useState('')
  const [drag, setDrag] = useState(false)
  const [recording, setRecording] = useState(false)
  const [secs, setSecs] = useState(0)
  const [denoise, setDenoise] = usePersisted('ov.clone.denoise', false)
  const [pre, setPre] = usePersisted('ov.clone.pre', true)
  const [language, setLanguage] = usePersisted('ov.clone.language', 'Auto')
  const [text, setText] = usePersisted('ov.clone.text', SAMPLE)
  const [refText, setRefText] = useState('')
  const [name, setName] = useState('')
  const [avatar, setAvatar] = useState('🎙️')
  const [tag, setTag] = useState('Custom Voice')
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState(null)
  const [result, setResult] = useState(null)
  const recRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!file) { setFileUrl(''); return }
    const u = URL.createObjectURL(file); setFileUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [file])

  useEffect(() => {
    if (!recording) return
    setSecs(0)
    const t = setInterval(() => setSecs((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [recording])

  const pick = (f) => {
    if (!f) return
    if (f.size > MAX_MB * 1024 * 1024) return setMsg({ ok: false, text: `File vượt quá ${MAX_MB}MB.` })
    setMsg(null); setResult(null); setFile(f)
  }

  const toggleRecord = async () => {
    if (recording) { recRef.current.stop(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream), chunks = []
      rec.ondataavailable = (e) => chunks.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        pick(new File(chunks, 'recording.webm', { type: rec.mimeType }))
        setRecording(false)
      }
      rec.start(); recRef.current = rec; setRecording(true)
    } catch { setMsg({ ok: false, text: 'Không truy cập được micro.' }) }
  }

  const base = () => { const f = new FormData(); f.append('audio', file); return f }

  const run = async (kind, fn) => {
    setBusy(kind); setMsg(null)
    try { await fn() } catch (e) { setMsg({ ok: false, text: e.message }) } finally { setBusy('') }
  }

  const transcribe = () => run('asr', async () => setRefText((await api.transcribe(base())).text))

  const preview = () => run('preview', async () => {
    const f = base()
    f.append('text', text); f.append('language', language); f.append('ref_text', refText)
    f.append('denoise', denoise); f.append('preprocess_prompt', pre)
    const r = await api.previewVoice(f)
    setResult(r); if (!refText && r.ref_text) setRefText(r.ref_text)
  })

  const save = () => run('save', async () => {
    const f = base()
    f.append('name', name); f.append('avatar', avatar); f.append('style_tag', tag); f.append('ref_text', refText)
    await api.createVoice(f)
    setMsg({ ok: true, text: `Đã lưu giọng "${name}" vào My Voices.` })
    setFile(null); setName(''); setRefText(''); setResult(null); setAgree(false); onSaved()
  })

  const drop = (e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }
  const h = 'mb-3 text-sm font-semibold'

  return (
    <div className="mx-auto max-w-3xl pb-8">
      <h1 className="text-2xl font-bold tracking-tight">Voice Cloning</h1>
      <p className="mb-8 mt-1 text-sm text-slate-500">Clone giọng chỉ với đoạn audio sạch dài 5–15 giây.</p>

      <h2 className={h}>Import your Voice</h2>
      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-4">
        <button onClick={() => inputRef.current.click()} onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={drop}
          className={`flex h-44 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed transition ${drag ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-slate-200 bg-slate-50 hover:border-brand-400 dark:border-slate-800 dark:bg-slate-900'}`}>
          <Inbox size={30} className="text-brand-500" />
          <span className="text-sm font-semibold">Add or drop a file</span>
          <span className="text-xs text-slate-400">Up to {MAX_MB}MB each</span>
        </button>
        <input ref={inputRef} type="file" accept="audio/*" hidden onChange={(e) => { pick(e.target.files[0]); e.target.value = '' }} />
        <div className="flex items-center text-xs text-slate-400">or</div>
        <button onClick={toggleRecord}
          className="flex h-44 flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 hover:border-brand-400 dark:border-slate-800 dark:bg-slate-900">
          {recording ? <Square size={28} className="text-red-500" fill="currentColor" /> : <Mic size={30} className="text-brand-500" />}
          <span className="text-sm font-semibold">{recording ? `Đang thu… ${secs}s (bấm để dừng)` : 'Record audio'}</span>
          <span className="text-xs text-slate-400">10-60 seconds long</span>
        </button>
      </div>

      <h2 className={`${h} mt-6`}>Uploaded Sample <span className="font-normal text-slate-400">{file ? '1/1' : '0/1'}</span></h2>
      <div className="rounded-2xl bg-slate-50 p-4 text-xs leading-relaxed text-slate-400 dark:bg-slate-900">
        {file ? (
          <div className="flex items-center gap-3">
            <span className="max-w-[200px] truncate text-sm font-medium text-slate-700 dark:text-slate-200">{file.name}</span>
            <audio src={fileUrl} controls className="h-8 flex-1" />
            <button onClick={() => { setFile(null); setResult(null) }} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={16} /></button>
          </div>
        ) : (
          <div className="flex gap-2"><Info size={13} className="mt-0.5 shrink-0" />
            <div>Hãy tải lên bản ghi sạch, ít tạp âm. Vang vọng, nhiều người nói cùng lúc hay tiếng ồn nền đều làm giảm chất lượng clone.
              <p className="mt-2">Nên chọn đoạn tốt nhất, chỉ có một người nói.</p></div>
          </div>
        )}
      </div>

      {file && (
        <div className="mt-5 grid gap-3 sm:grid-cols-[72px_1fr_1fr]">
          <input value={avatar} onChange={(e) => setAvatar(e.target.value)} maxLength={2} className={`${inputCls} text-center`} title="Icon" />
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên giọng" className={inputCls} />
          <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="Phong cách" className={inputCls} />
          <div className="sm:col-span-3">
            <textarea value={refText} onChange={(e) => setRefText(e.target.value)} rows={3} className={inputCls}
              placeholder="Lời thoại trong audio (để trống sẽ tự nhận diện bằng Whisper)" />
            <button onClick={transcribe} disabled={!!busy} className="mt-2 flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:underline disabled:opacity-50">
              {busy === 'asr' ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />} Tự động nhận diện chữ
            </button>
          </div>
        </div>
      )}

      <h2 className={`${h} mt-6`}>Advanced Settings <span className="font-normal text-slate-400">(Optional)</span></h2>
      <Toggle checked={denoise} onChange={setDenoise} label="Remove Background Noise" />
      <Toggle checked={pre} onChange={setPre} label="Tiền xử lý audio mẫu" />

      <h2 className={`${h} mt-6`}>Text to Preview</h2>
      <div className="rounded-xl border border-slate-200 dark:border-slate-800">
        <Select value={language} onChange={setLanguage} options={langOptions(languages)} searchable searchPlaceholder="Tìm ngôn ngữ…" triggerClass="rounded-b-none rounded-t-xl bg-transparent px-3 py-2.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-900" />
        <textarea value={text} maxLength={MAX_PREVIEW} onChange={(e) => setText(e.target.value)} rows={4}
          className="w-full resize-none rounded-b-xl bg-transparent p-3 text-sm outline-none" />
        <div className="px-3 pb-2 text-xs text-slate-400">{text.length} / {MAX_PREVIEW} characters</div>
      </div>

      <label className="mt-4 flex cursor-pointer items-start gap-2 text-xs text-slate-500">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 h-3.5 w-3.5 accent-brand-500" />
        Tôi xác nhận có đầy đủ quyền và sự cho phép để dùng các mẫu giọng này tạo nội dung AI, và cam kết không dùng cho mục đích bất hợp pháp hoặc gây hại.
      </label>

      <div className="mt-5 flex items-center justify-end gap-3">
        {msg && <span className={`mr-auto text-sm ${msg.ok ? 'text-emerald-600' : 'text-red-600'}`}>{msg.text}</span>}
        <Button variant="outline" onClick={save} disabled={!file || !name.trim() || !agree || !!busy}>
          {busy === 'save' ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Lưu vào thư viện
        </Button>
        <Button onClick={preview} disabled={!file || !text.trim() || !agree || !ready || !!busy} className="px-6">
          {busy === 'preview' ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Generate
        </Button>
      </div>

      <div className="mt-8">
        {result ? <audio src={result.audio_url} controls autoPlay className="w-full" />
          : <p className="text-sm font-semibold text-slate-400">Kết quả nghe thử sẽ hiện ở đây</p>}
      </div>
    </div>
  )
}
