import { useRef, useState } from 'react'
import { Loader2, Mic, Square, Upload, Wand2, Trash2, Save } from 'lucide-react'
import { api } from '../api'
import { Button, Card, Field, PageHeader, VoiceAvatar, inputCls } from './ui'

export default function VoiceCreator({ voices, onChanged, onUse }) {
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [avatar, setAvatar] = useState('🎙️')
  const [tag, setTag] = useState('Custom Voice')
  const [refText, setRefText] = useState('')
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState(null)
  const [recording, setRecording] = useState(false)
  const recRef = useRef(null)

  const toggleRecord = async () => {
    if (recording) { recRef.current.stop(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream), chunks = []
      rec.ondataavailable = (e) => chunks.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        setFile(new File(chunks, 'recording.webm', { type: rec.mimeType }))
        setRecording(false)
      }
      rec.start(); recRef.current = rec; setRecording(true)
    } catch { setMsg({ ok: false, msg: 'Không truy cập được micro.' }) }
  }

  const form = () => { const f = new FormData(); f.append('audio', file); return f }

  const transcribe = async () => {
    setBusy('asr'); setMsg(null)
    try { setRefText((await api.transcribe(form())).text) }
    catch (e) { setMsg({ ok: false, msg: e.message }) }
    finally { setBusy('') }
  }

  const save = async () => {
    setBusy('save'); setMsg(null)
    try {
      const f = form()
      f.append('name', name); f.append('avatar', avatar); f.append('style_tag', tag); f.append('ref_text', refText)
      await api.createVoice(f)
      setMsg({ ok: true, msg: `Đã lưu giọng "${name}" vào thư viện.` })
      setFile(null); setName(''); setRefText(''); onChanged()
    } catch (e) { setMsg({ ok: false, msg: e.message }) }
    finally { setBusy('') }
  }

  const custom = voices.filter((v) => v.custom)

  return (
    <>
      <PageHeader title="Voice Creator" subtitle="Nhân bản giọng nói từ một đoạn audio mẫu 5–15 giây." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="space-y-4">
          <Field label="Audio mẫu">
            <div className="flex gap-2">
              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-3 text-sm text-slate-500 hover:border-brand-500 dark:border-slate-700">
                <Upload size={16} /><span className="truncate">{file ? file.name : 'Tải file âm thanh…'}</span>
                <input type="file" accept="audio/*" hidden onChange={(e) => setFile(e.target.files[0] || null)} />
              </label>
              <Button variant="ghost" onClick={toggleRecord} className={recording ? '!text-red-600' : ''}>
                {recording ? <><Square size={16} /> Dừng</> : <><Mic size={16} /> Thu âm</>}
              </Button>
            </div>
          </Field>
          <Field label="Lời thoại trong audio">
            <textarea value={refText} onChange={(e) => setRefText(e.target.value)} rows={4} className={inputCls}
              placeholder="Để trống để tự nhận diện bằng Whisper khi lưu" />
          </Field>
          <Button variant="ghost" onClick={transcribe} disabled={!file || !!busy} className="w-full border border-slate-200 dark:border-slate-700">
            {busy === 'asr' ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />} Tự động nhận diện chữ
          </Button>
          <div className="grid grid-cols-[72px_1fr] gap-3">
            <Field label="Icon"><input value={avatar} onChange={(e) => setAvatar(e.target.value)} className={`${inputCls} text-center`} maxLength={2} /></Field>
            <Field label="Tên giọng"><input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="VD: Giọng của tôi" /></Field>
          </div>
          <Field label="Phong cách"><input value={tag} onChange={(e) => setTag(e.target.value)} className={inputCls} /></Field>
          <Button onClick={save} disabled={!file || !name.trim() || !!busy} className="w-full">
            {busy === 'save' ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Lưu giọng vào thư viện
          </Button>
          {msg && <p className={`text-sm ${msg.ok ? 'text-emerald-600' : 'text-red-600'}`}>{msg.msg}</p>}
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold">Thư viện giọng của bạn ({custom.length})</h2>
          {custom.length === 0 && <p className="py-10 text-center text-sm text-slate-500">Chưa có giọng tuỳ chỉnh nào.</p>}
          <div className="space-y-2">
            {custom.map((v) => (
              <div key={v.key} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
                <VoiceAvatar voice={v} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{v.name}</div>
                  <div className="truncate text-xs text-slate-500">{v.style_tag}</div>
                </div>
                <Button variant="ghost" onClick={() => onUse(v.key)} className="!px-3 !py-1.5">Dùng</Button>
                <button onClick={async () => { if (confirm(`Xoá giọng "${v.name}"?`)) { await api.deleteVoice(v.key); onChanged() } }}
                  className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 size={16} /></button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}
