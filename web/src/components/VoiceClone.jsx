import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Info, Inbox, Loader2, Mic, Save, Sparkles, Square, Trash2, Wand2 } from 'lucide-react'
import { api } from '../api'
import { blobToWavFile } from '../wav'
import { usePersisted } from '../usePersisted'
import { Button, Select, Toggle, inputCls, langOptions } from './ui'

const SAMPLE = 'Xin chào, rất vui được hỗ trợ bạn. Hãy chọn một giọng nói phù hợp và cùng bắt đầu hành trình sáng tạo âm thanh nhé.'
const IDLE = { status: 'idle', duration: null, errors: [], warnings: [] }

const clip = (s, n) => Array.from(s).slice(0, n).join('')
const mb = (bytes) => (bytes / 1024 / 1024).toFixed(1)
const extLabel = (exts) => exts.map((e) => e.replace('.', '').toUpperCase()).join(', ')
const extOf = (name) => (name.match(/\.[^.]+$/)?.[0] || '').toLowerCase()

// Mọi giới hạn (dung lượng, độ dài, số ký tự, định dạng) lấy từ `limits` do server trả về
// qua /api/meta, nên giao diện luôn trùng với những gì server thực sự kiểm tra.
export default function VoiceClone({ languages, limits, onSaved, ready }) {
  if (!limits) return <p className="py-24 text-center text-sm text-slate-400">Đang tải cấu hình từ server…</p>
  return <CloneForm languages={languages} limits={limits} onSaved={onSaved} ready={ready} />
}

function CloneForm({ languages, limits, onSaved, ready }) {
  const [lo, hi] = limits.ref_recommended_seconds
  const [file, setFile] = useState(null)
  const [fileUrl, setFileUrl] = useState('')
  const [info, setInfo] = useState(IDLE)
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

  const lang = languages.includes(language) ? language : 'Auto'
  const previewText = clip(text, limits.preview_max_chars)

  useEffect(() => {
    if (!file) { setFileUrl(''); return }
    const u = URL.createObjectURL(file); setFileUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [file])

  // Hỏi server kiểm tra audio mẫu ngay khi chọn file (độ dài, định dạng, dung lượng)
  useEffect(() => {
    if (!file) { setInfo(IDLE); return }
    let stale = false
    setInfo({ ...IDLE, status: 'checking' })
    const f = new FormData(); f.append('audio', file)
    api.inspectAudio(f)
      .then((r) => !stale && setInfo({ status: 'done', ...r }))
      .catch((e) => !stale && setInfo({ ...IDLE, status: 'done', errors: [e.message] }))
    return () => { stale = true }
  }, [file])

  useEffect(() => {
    if (!recording) return
    setSecs(0)
    const t = setInterval(() => setSecs((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [recording])

  // Server từ chối audio dài hơn mức tối đa nên tự dừng thu khi chạm mốc đó
  useEffect(() => {
    if (recording && secs >= limits.ref_max_seconds) recRef.current?.stop()
  }, [recording, secs, limits.ref_max_seconds])

  const pick = (f) => {
    if (!f) return
    const ext = extOf(f.name)
    if (!limits.extensions.includes(ext)) {
      return setMsg({ ok: false, text: `Định dạng '${ext || 'không rõ'}' không được hỗ trợ. Chỉ nhận: ${extLabel(limits.extensions)}.` })
    }
    if (f.size > limits.max_upload_mb * 1024 * 1024) {
      return setMsg({ ok: false, text: `File ${mb(f.size)}MB vượt quá giới hạn ${limits.max_upload_mb}MB.` })
    }
    setMsg(null); setResult(null); setFile(f)
  }

  const toggleRecord = async () => {
    if (recording) { recRef.current.stop(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream), chunks = []
      rec.ondataavailable = (e) => chunks.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        try { pick(await blobToWavFile(new Blob(chunks, { type: rec.mimeType }))) }
        catch { setMsg({ ok: false, text: 'Không xử lý được bản thu âm của trình duyệt. Hãy tải file âm thanh lên thay thế.' }) }
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
    f.append('text', previewText); f.append('language', lang); f.append('ref_text', refText)
    f.append('denoise', denoise); f.append('preprocess_prompt', pre)
    const r = await api.previewVoice(f)
    setResult(r); if (!refText && r.ref_text) setRefText(r.ref_text)
  })

  const save = () => run('save', async () => {
    const f = base()
    f.append('name', name.trim()); f.append('avatar', avatar); f.append('style_tag', tag); f.append('ref_text', refText)
    await api.createVoice(f)
    setMsg({ ok: true, text: `Đã lưu giọng "${name.trim()}" vào My Voices.` })
    setFile(null); setName(''); setRefText(''); setResult(null); setAgree(false); onSaved()
  })

  // Điều kiện còn thiếu — cùng bộ luật mà server áp dụng
  const audioBlock = !file ? 'tải hoặc thu âm audio mẫu'
    : info.status === 'checking' ? 'đợi kiểm tra audio'
    : info.errors.length ? 'sửa lỗi audio mẫu' : null
  const missingPreview = [audioBlock, !previewText.trim() && 'nhập văn bản nghe thử', !agree && 'xác nhận quyền sử dụng', !ready && 'đợi engine sẵn sàng'].filter(Boolean)
  const missingSave = [audioBlock, !name.trim() && 'nhập tên giọng', !agree && 'xác nhận quyền sử dụng'].filter(Boolean)

  const drop = (e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }
  const h = 'mb-3 text-sm font-semibold'

  return (
    <div className="mx-auto max-w-3xl pb-8">
      <h1 className="text-2xl font-bold tracking-tight">Voice Cloning</h1>
      <p className="mb-8 mt-1 text-sm text-slate-500">
        Clone giọng từ đoạn audio sạch dài {lo}–{hi} giây (tối thiểu {limits.ref_min_seconds}s, tối đa {limits.ref_max_seconds}s).
      </p>

      <h2 className={h}>Import your Voice</h2>
      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-4">
        <button onClick={() => inputRef.current.click()} onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={drop}
          className={`flex h-44 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed transition ${drag ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-slate-200 bg-slate-50 hover:border-brand-400 dark:border-slate-800 dark:bg-slate-900'}`}>
          <Inbox size={30} className="text-brand-500" />
          <span className="text-sm font-semibold">Add or drop a file</span>
          <span className="px-4 text-center text-xs text-slate-400">Tối đa {limits.max_upload_mb}MB · {extLabel(limits.extensions)}</span>
        </button>
        <input ref={inputRef} type="file" accept={limits.extensions.join(',')} hidden onChange={(e) => { pick(e.target.files[0]); e.target.value = '' }} />
        <div className="flex items-center text-xs text-slate-400">or</div>
        <button onClick={toggleRecord}
          className="flex h-44 flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 hover:border-brand-400 dark:border-slate-800 dark:bg-slate-900">
          {recording ? <Square size={28} className="text-red-500" fill="currentColor" /> : <Mic size={30} className="text-brand-500" />}
          <span className="text-sm font-semibold">{recording ? `Đang thu… ${secs}/${limits.ref_max_seconds}s (bấm để dừng)` : 'Record audio'}</span>
          <span className="text-xs text-slate-400">Tối đa {limits.ref_max_seconds}s · tốt nhất {lo}–{hi}s</span>
        </button>
      </div>

      <h2 className={`${h} mt-6`}>Uploaded Sample <span className="font-normal text-slate-400">{file ? '1/1' : '0/1'}</span></h2>
      <div className="rounded-2xl bg-slate-50 p-4 text-xs leading-relaxed text-slate-400 dark:bg-slate-900">
        {file ? (
          <>
            <div className="flex items-center gap-3">
              <span className="max-w-[200px] truncate text-sm font-medium text-slate-700 dark:text-slate-200">{file.name}</span>
              <span className="flex shrink-0 items-center gap-1.5 text-slate-500">
                {info.status === 'checking' ? <><Loader2 size={13} className="animate-spin" /> Đang kiểm tra…</>
                  : `${info.duration != null ? `${info.duration.toFixed(1)}s · ` : ''}${mb(file.size)}MB`}
              </span>
              <audio src={fileUrl} controls className="h-8 min-w-0 flex-1" />
              <button onClick={() => { setFile(null); setResult(null) }} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={16} /></button>
            </div>
            {info.errors.map((e) => (
              <p key={e} className="mt-2 flex items-start gap-1.5 text-red-600"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{e}</p>
            ))}
            {info.warnings.map((w) => (
              <p key={w} className="mt-2 flex items-start gap-1.5 text-amber-600"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{w}</p>
            ))}
          </>
        ) : (
          <div className="flex gap-2"><Info size={13} className="mt-0.5 shrink-0" />
            <div>
              Dùng bản ghi sạch, chỉ một người nói, ít tạp âm và vang. Độ dài tốt nhất {lo}–{hi}s (tối thiểu {limits.ref_min_seconds}s, tối đa {limits.ref_max_seconds}s).
              <p className="mt-2">Định dạng {extLabel(limits.extensions)}, tối đa {limits.max_upload_mb}MB.</p>
            </div>
          </div>
        )}
      </div>

      {file && (
        <div className="mt-5 grid gap-3 sm:grid-cols-[72px_1fr_1fr]">
          <input value={avatar} onChange={(e) => setAvatar(clip(e.target.value, limits.avatar_max_chars))} className={`${inputCls} text-center`} title="Icon" />
          <input value={name} onChange={(e) => setName(clip(e.target.value, limits.name_max_chars))} placeholder="Tên giọng (bắt buộc)" className={inputCls} />
          <input value={tag} onChange={(e) => setTag(clip(e.target.value, limits.style_max_chars))} placeholder="Phong cách" className={inputCls} />
          <div className="sm:col-span-3">
            <textarea value={refText} onChange={(e) => setRefText(e.target.value)} rows={3} className={inputCls}
              placeholder="Lời thoại trong audio (để trống sẽ tự nhận diện bằng Whisper)" />
            <button onClick={transcribe} disabled={!!busy || !!audioBlock} className="mt-2 flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:underline disabled:opacity-50 disabled:no-underline">
              {busy === 'asr' ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />} Tự động nhận diện chữ
            </button>
          </div>
        </div>
      )}

      <h2 className={`${h} mt-6`}>Advanced Settings <span className="font-normal text-slate-400">(Optional)</span></h2>
      <Toggle checked={denoise} onChange={setDenoise} label="Khử nhiễu (denoise)" hint="Giọng tạo ra sạch hơn khi audio mẫu có tạp âm" />
      <Toggle checked={pre} onChange={setPre} label="Tiền xử lý audio mẫu" hint="Cắt khoảng lặng đầu, cuối và giữa câu" />

      <h2 className={`${h} mt-6`}>Text to Preview</h2>
      <div className="rounded-xl border border-slate-200 dark:border-slate-800">
        <Select value={lang} onChange={setLanguage} options={langOptions(languages)} searchable searchPlaceholder="Tìm ngôn ngữ…"
          triggerClass="rounded-b-none rounded-t-xl bg-transparent px-3 py-2.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-900" />
        <textarea value={previewText} maxLength={limits.preview_max_chars} onChange={(e) => setText(e.target.value)} rows={4}
          className="w-full resize-none rounded-b-xl bg-transparent p-3 text-sm outline-none" />
        <div className="px-3 pb-2 text-xs text-slate-400">{Array.from(previewText).length} / {limits.preview_max_chars} characters</div>
      </div>

      <label className="mt-4 flex cursor-pointer items-start gap-2 text-xs text-slate-500">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 h-3.5 w-3.5 accent-brand-500" />
        Tôi xác nhận có đầy đủ quyền và sự cho phép để dùng các mẫu giọng này tạo nội dung AI, và cam kết không dùng cho mục đích bất hợp pháp hoặc gây hại.
      </label>

      <div className="mt-5 flex items-center justify-end gap-3">
        {msg && <span className={`mr-auto text-sm ${msg.ok ? 'text-emerald-600' : 'text-red-600'}`}>{msg.text}</span>}
        <Button variant="outline" onClick={save} disabled={missingSave.length > 0 || !!busy} title={missingSave.join(', ')}>
          {busy === 'save' ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Lưu vào thư viện
        </Button>
        <Button onClick={preview} disabled={missingPreview.length > 0 || !!busy} title={missingPreview.join(', ')} className="px-6">
          {busy === 'preview' ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Generate
        </Button>
      </div>
      <div className="mt-2 space-y-0.5 text-right text-xs text-slate-400">
        {missingPreview.length > 0 && <p>Generate cần: {missingPreview.join(', ')}</p>}
        {missingSave.length > 0 && <p>Lưu cần: {missingSave.join(', ')}</p>}
      </div>

      <div className="mt-8">
        {result ? <audio src={result.audio_url} controls autoPlay className="w-full" />
          : <p className="text-sm font-semibold text-slate-400">Kết quả nghe thử sẽ hiện ở đây</p>}
      </div>
    </div>
  )
}
