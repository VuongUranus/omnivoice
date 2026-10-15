// Chuyển bản thu âm của trình duyệt (webm/mp4) sang WAV PCM16 mono.
// Server chỉ nhận wav/mp3/flac/ogg/m4a và đọc WAV không cần ffmpeg.
export async function blobToWavFile(blob, name = 'recording.wav') {
  const Ctx = window.AudioContext || window.webkitAudioContext
  const ctx = new Ctx()
  try {
    const audio = await ctx.decodeAudioData(await blob.arrayBuffer())
    const n = audio.length
    const channels = Array.from({ length: audio.numberOfChannels }, (_, c) => audio.getChannelData(c))
    const buf = new ArrayBuffer(44 + n * 2)
    const v = new DataView(buf)
    const str = (o, s) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)))
    str(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); str(8, 'WAVE'); str(12, 'fmt ')
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
    v.setUint32(24, audio.sampleRate, true); v.setUint32(28, audio.sampleRate * 2, true)
    v.setUint16(32, 2, true); v.setUint16(34, 16, true)
    str(36, 'data'); v.setUint32(40, n * 2, true)
    for (let i = 0; i < n; i++) {
      let s = 0
      for (const ch of channels) s += ch[i]
      s = Math.max(-1, Math.min(1, s / channels.length))
      v.setInt16(44 + i * 2, Math.round(s * 0x7fff), true)
    }
    return new File([buf], name, { type: 'audio/wav' })
  } finally {
    ctx.close()
  }
}
