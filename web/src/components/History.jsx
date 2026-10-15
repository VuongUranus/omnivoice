import { Play, Trash2, Download } from 'lucide-react'
import { api } from '../api'
import { Button, Card, PageHeader, fmtDur } from './ui'

export default function History({ items, onPlay, onChanged }) {
  const clear = async () => {
    if (confirm('Xoá toàn bộ lịch sử?')) { await api.clearHistory(); onChanged() }
  }
  return (
    <>
      <PageHeader title="Lịch sử" subtitle="Các bản âm thanh đã tạo gần đây (tối đa 50).">
        {items.length > 0 && <Button variant="danger" onClick={clear}><Trash2 size={16} /> Xoá tất cả</Button>}
      </PageHeader>
      {items.length === 0 ? (
        <Card className="py-16 text-center text-sm text-slate-500">Chưa có bản ghi nào. Hãy tạo giọng nói đầu tiên!</Card>
      ) : (
        <div className="space-y-3">
          {items.map((it) => (
            <Card key={it.id} className="flex items-center gap-4 !p-4">
              <button onClick={() => onPlay(it)} className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-500/15">
                <Play size={18} className="ml-0.5" />
              </button>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{it.text}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {it.avatar} {it.voice_name} · {fmtDur(it.duration)} · {it.time_str}
                </p>
              </div>
              <a href={it.audio_url} download={`${it.id}.wav`} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"><Download size={18} /></a>
              <button onClick={async () => { await api.deleteHistory(it.id); onChanged() }}
                className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"><Trash2 size={18} /></button>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
