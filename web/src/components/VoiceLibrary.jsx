import { VoiceBrowser } from './VoiceModal'

export default function VoiceLibrary({ voices, onUse, onChanged }) {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Voice Library</h1>
      <p className="mb-6 text-sm text-slate-500">Duyệt giọng có sẵn và giọng bạn đã nhân bản.</p>
      <VoiceBrowser voices={voices} onUse={onUse} onChanged={onChanged} />
    </div>
  )
}
