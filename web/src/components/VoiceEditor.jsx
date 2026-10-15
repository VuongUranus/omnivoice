import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Info, Loader2, RotateCcw, Upload, X } from 'lucide-react'
import { api } from '../api'
import { useConfirm } from '../confirm'
import { clip, extLabel, mb, precheckFile, useAudioInspect } from '../audioCheck'
import { Button, VoiceAvatar, inputCls } from './ui'

// Thêm giọng mới (voice = null) hoặc sửa giọng có sẵn / giọng tùy chỉnh.
// Mọi giới hạn lấy từ `limits` do server công bố, server kiểm tra lại khi lưu.
export default function VoiceEditor({ voice, limits, onClose, onSaved }) {
  const confirm = useConfirm()
  const creating = !voice
  const [name, setName] = useState(voice?.name ?? '')
  const [avatar, setAvatar] = useState(voice?.avatar ?? '🎙️')
  const [style, setStyle] = useState(voice?.style_tag ?? 'Custom Voice')
  const [desc, setDesc] = useState(voice?.desc ?? '')
  const [tags, setTags] = useState(voice?.tags ?? [])
  const [tagInput, setTagInput] = useState('')
  const [grad, setGrad] = useState(voice?.grad || limits.gradients[3])
  const [instruct, setInstruct] = useState(voice?.instruct ?? '')
  const [refText, setRefText] = useState(voice?.ref_text ?? '')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)
  const info = useAudioInspect(file)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  const pick = (f) => {
    if (!f) return
    const problem = precheckFile(f, limits)
    if (problem) return setError(problem)
    setError(null); setFile(f); setRefText('') // audio mới thì lời thoại cũ không còn đúng
  }

  const addTag = (raw) => {
    const t = clip(raw.trim().replace(/,$/, '').trim(), limits.tag_max_chars)
    if (t && !tags.includes(t) && tags.length < limits.tags_max_count) setTags([...tags, t])
    setTagInput('')
  }

  const missing = [
    !name.trim() && 'nhập tên giọng',
    creating && !file && 'chọn audio mẫu',
    file && info.status === 'checking' && 'đợi kiểm tra audio',
    file && info.errors.length > 0 && 'sửa lỗi audio mẫu',
  ].filter(Boolean)

  const save = async () => {
    setBusy(true); setError(null)
    try {
      const f = new FormData()
      f.append('name', name.trim()); f.append('avatar', avatar); f.append('style_tag', style); f.append('desc', desc)
      f.append('tags', JSON.stringify(tags)); f.append('grad', grad); f.append('instruct', instruct); f.append('ref_text', refText)
      if (file) f.append('audio', file)
      await (creating ? api.createVoice(f) : api.updateVoice(voice.key, f))
      onSaved()
    } catch (e) { setError(e.message); setBusy(false) }
  }

  const reset = async () => {
    const ok = await confirm({ title: 'Khôi phục mặc định?', message: `Mọi chỉnh sửa của giọng "${voice.name}" sẽ bị bỏ, quay về thông tin gốc.`, confirmText: 'Khôi phục', danger: false })
    if (!ok) return
    setBusy(true); setError(null)
    try { await api.resetVoice(voice.key); onSaved() } catch (e) { setError(e.message); setBusy(false) }
  }

  const label = 'mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500'

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-[1px]">
      <div role="dialog" aria-modal="true" className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-3xl bg-white shadow-2xl dark:bg-slate-950">
        <div className="flex items-center justify-between px-7 pb-3 pt-6">
          <div className="flex items-center gap-3">
            <VoiceAvatar voice={{ avatar, grad }} size="h-11 w-11" text="text-lg" />
            <div>
              <h2 className="text-lg font-bold">{creating ? 'Thêm giọng mới' : 'Sửa giọng'}</h2>
              {voice?.preset && <p className="text-xs text-slate-500">Giọng có sẵn · file audio gốc không bị thay đổi</p>}
            </div>
          </div>
          <button onClick={onClose} disabled={busy} className="rounded-full p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"><X size={20} /></button>
        </div>

        <div className="space-y-4 overflow-y-auto px-7 pb-2">
          {voice?.instruct_error && (
            <div className="flex gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>Instruct hiện tại không hợp lệ nên Generate với giọng này sẽ báo lỗi. Hãy sửa lại bên dưới hoặc để trống.</span>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-[72px_1fr_1fr]">
            <div><span className={label}>Icon</span>
              <input value={avatar} onChange={(e) => setAvatar(clip(e.target.value, limits.avatar_max_chars))} className={`${inputCls} text-center`} /></div>
            <div><span className={label}>Tên giọng</span>
              <input value={name} onChange={(e) => setName(clip(e.target.value, limits.name_max_chars))} placeholder="Bắt buộc" className={inputCls} /></div>
            <div><span className={label}>Phong cách</span>
              <input value={style} onChange={(e) => setStyle(clip(e.target.value, limits.style_max_chars))} className={inputCls} /></div>
          </div>

          <div>
            <span className={label}>Mô tả <span className="font-normal normal-case text-slate-400">{Array.from(desc).length}/{limits.desc_max_chars}</span></span>
            <textarea value={desc} rows={2} onChange={(e) => setDesc(clip(e.target.value, limits.desc_max_chars))} className={inputCls} />
          </div>

          <div>
            <span className={label}>Tags <span className="font-normal normal-case text-slate-400">{tags.length}/{limits.tags_max_count}</span></span>
            <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 p-2 dark:border-slate-800">
              {tags.map((t) => (
                <span key={t} className="flex items-center gap-1 rounded-md bg-slate-100 py-1 pl-2 pr-1 text-xs dark:bg-slate-800">
                  {t}<button type="button" onClick={() => setTags(tags.filter((x) => x !== t))} className="rounded p-0.5 text-slate-400 hover:text-red-600" title="Bỏ tag"><X size={12} /></button>
                </span>
              ))}
              {tags.length < limits.tags_max_count && (
                <input value={tagInput} onChange={(e) => (e.target.value.endsWith(',') ? addTag(e.target.value) : setTagInput(e.target.value))}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(tagInput) } else if (e.key === 'Backspace' && !tagInput && tags.length) setTags(tags.slice(0, -1)) }}
                  onBlur={() => tagInput && addTag(tagInput)} placeholder="Gõ tag rồi Enter…" className="min-w-[120px] flex-1 bg-transparent px-1 py-1 text-sm outline-none" />
              )}
            </div>
          </div>

          <div>
            <span className={label}>Màu nền</span>
            <div className="flex flex-wrap gap-2">
              {limits.gradients.map((g) => (
                <button key={g} type="button" onClick={() => setGrad(g)} aria-label="Chọn màu" aria-pressed={g === grad} style={{ background: g }}
                  className={`h-8 w-8 rounded-lg ring-offset-2 transition dark:ring-offset-slate-950 ${g === grad ? 'ring-2 ring-slate-900 dark:ring-slate-100' : 'hover:scale-110'}`} />
              ))}
            </div>
          </div>

          <div>
            <span className={label}>Instruct <span className="font-normal normal-case text-slate-400">(tuỳ chọn)</span></span>
            <input value={instruct} onChange={(e) => setInstruct(e.target.value)} placeholder="male, low pitch, young adult" className={inputCls} />
            <p className="mt-1.5 flex gap-1.5 text-xs text-slate-400"><Info size={12} className="mt-0.5 shrink-0" />
              {limits.instruct_validation
                ? 'Chỉ nhận các mục model hỗ trợ (giới tính, độ tuổi, cao độ, giọng vùng…), cách nhau bằng dấu phẩy. Server sẽ kiểm tra khi lưu.'
                : 'Chỉ dẫn phong cách cho model, cách nhau bằng dấu phẩy.'}
            </p>
          </div>

          <div>
            <span className={label}>Audio mẫu {creating ? '' : <span className="font-normal normal-case text-slate-400">(để trống nếu giữ nguyên)</span>}</span>
            {!creating && !file && voice.audio_url && <audio src={voice.audio_url} controls className="mb-2 h-9 w-full" />}
            <input ref={fileRef} type="file" accept={limits.extensions.join(',')} hidden onChange={(e) => { pick(e.target.files[0]); e.target.value = '' }} />
            <button type="button" onClick={() => fileRef.current.click()}
              className="flex w-full items-center gap-2 rounded-xl border border-dashed border-slate-300 px-3 py-3 text-sm text-slate-500 hover:border-brand-500 dark:border-slate-700">
              <Upload size={16} /><span className="truncate">{file ? file.name : creating ? 'Chọn file audio mẫu…' : 'Thay audio mẫu…'}</span>
              {file && <span className="ml-auto shrink-0 text-xs">{info.status === 'checking' ? <Loader2 size={13} className="animate-spin" /> : `${info.duration != null ? `${info.duration.toFixed(1)}s · ` : ''}${mb(file.size)}MB`}</span>}
            </button>
            <p className="mt-1.5 text-xs text-slate-400">
              {extLabel(limits.extensions)}, tối đa {limits.max_upload_mb}MB, dài {limits.ref_min_seconds}–{limits.ref_max_seconds}s (tốt nhất {limits.ref_recommended_seconds.join('–')}s).
            </p>
            {info.errors.map((e) => <p key={e} className="mt-1.5 flex gap-1.5 text-xs text-red-600"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{e}</p>)}
            {info.warnings.map((w) => <p key={w} className="mt-1.5 flex gap-1.5 text-xs text-amber-600"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{w}</p>)}
          </div>

          {(file || !creating) && (
            <div>
              <span className={label}>Lời thoại trong audio</span>
              <textarea value={refText} rows={3} onChange={(e) => setRefText(e.target.value)} className={inputCls}
                placeholder={file ? 'Để trống sẽ tự nhận diện bằng Whisper' : ''} />
            </div>
          )}
        </div>

        {error && <p className="mx-7 mt-3 whitespace-pre-line break-words rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-500/10 dark:text-red-300">{error}</p>}
        <div className="flex items-center gap-3 px-7 pb-6 pt-4">
          {voice?.modified && (
            <button type="button" onClick={reset} disabled={busy} className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-brand-600"><RotateCcw size={13} /> Khôi phục mặc định</button>
          )}
          {missing.length > 0 && <span className="text-xs text-slate-400">Cần: {missing.join(', ')}</span>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={onClose} disabled={busy}>Huỷ</Button>
            <Button onClick={save} disabled={busy || missing.length > 0} className="px-6">
              {busy && <Loader2 size={15} className="animate-spin" />} {creating ? 'Thêm giọng' : 'Lưu thay đổi'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
