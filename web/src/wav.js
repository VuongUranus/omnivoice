// Giải mã / mã hoá audio ngay trong trình duyệt (Web Audio API), không cần ffmpeg hay server.

// Giải mã file/blob audio bất kỳ mà trình duyệt đọc được (wav, mp3, m4a, ogg, webm…). Kết quả ở sample rate của trình duyệt.
export async function decodeAudio(blob) {
  const Ctx = window.AudioContext || window.webkitAudioContext
  const ctx = new Ctx()
  try {
    return await ctx.decodeAudioData(await blob.arrayBuffer())
  } finally {
    ctx.close()
  }
}

// channels: mảng Float32Array (mỗi kênh một mảng, cùng độ dài, giá trị -1..1) -> ArrayBuffer WAV PCM16
export function encodeWav(channels, sampleRate) {
  const ch = channels.length
  const n = channels[0].length
  const bytes = n * ch * 2
  const buf = new ArrayBuffer(44 + bytes)
  const v = new DataView(buf)
  const str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)))
  str(0, 'RIFF'); v.setUint32(4, 36 + bytes, true); str(8, 'WAVE'); str(12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, ch, true)
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * ch * 2, true)
  v.setUint16(32, ch * 2, true); v.setUint16(34, 16, true)
  str(36, 'data'); v.setUint32(40, bytes, true)
  let o = 44
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < ch; c++) {
      v.setInt16(o, Math.round(Math.max(-1, Math.min(1, channels[c][i])) * 0x7fff), true)
      o += 2
    }
  }
  return buf
}

// Chuyển bản thu âm của trình duyệt (webm/mp4) sang WAV PCM16 mono.
// Server chỉ nhận wav/mp3/flac/ogg/m4a và đọc WAV không cần ffmpeg.
export async function blobToWavFile(blob, name = 'recording.wav') {
  const audio = await decodeAudio(blob)
  const n = audio.length
  const channels = Array.from({ length: audio.numberOfChannels }, (_, c) => audio.getChannelData(c))
  const mono = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    let s = 0
    for (const ch of channels) s += ch[i]
    mono[i] = s / channels.length
  }
  return new File([encodeWav([mono], audio.sampleRate)], name, { type: 'audio/wav' })
}
