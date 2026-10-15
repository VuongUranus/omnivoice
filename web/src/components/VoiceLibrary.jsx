import { useState } from 'react'
import { Plus } from 'lucide-react'
import { VoiceBrowser } from './VoiceModal'
import VoiceEditor from './VoiceEditor'
import { Button } from './ui'

export default function VoiceLibrary({ voices, limits, onUse, onChanged }) {
  const [editing, setEditing] = useState(undefined) // undefined: đóng · null: thêm mới · object: sửa giọng

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight">Voice Library</h1>
          <p className="text-sm text-slate-500">Thêm, sửa hoặc xoá giọng có sẵn và giọng bạn đã nhân bản.</p>
        </div>
        <Button variant="dark" disabled={!limits} onClick={() => setEditing(null)}><Plus size={16} /> Thêm giọng</Button>
      </div>
      <VoiceBrowser manage voices={voices} onUse={onUse} onChanged={onChanged} onEdit={setEditing} />
      {editing !== undefined && limits && (
        <VoiceEditor voice={editing} limits={limits} onClose={() => setEditing(undefined)}
          onSaved={() => { setEditing(undefined); onChanged() }} />
      )}
    </div>
  )
}
