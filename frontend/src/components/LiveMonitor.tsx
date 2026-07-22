import { useCallback, useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useWebSocket } from "@/hooks/use-websocket"
import { useMicStream } from "@/hooks/use-mic-stream"
import { decodeTo16kMono, streamPcm, TARGET_SR } from "@/lib/audio-stream"

const BACKEND = import.meta.env.VITE_API_URL || "http://localhost:8000"
const WS_URL = BACKEND.replace(/^http/, "ws") + "/ws/analyze"

type AlertLevel = "GREEN" | "AMBER" | "RED" | "UNCERTAIN"
type Scam = { score: number; tactics: string[]; transcript?: string; language?: string }
type Action = "MONITOR" | "CHALLENGE" | "BLOCK"
type Quality = { ok: boolean; score: number; reason: string; snr_db?: number; rms?: number; clip_frac?: number }
type Replay = { suspect: boolean; score: number; reason: string }
type Result = {
  risk_score: number; alert_level: AlertLevel; layer_breakdown: Record<string, number>
  quality?: Quality; replay?: Replay
  novelty?: number; scam?: Scam; action?: Action; action_reason?: string
  mode?: "shadow" | "enforce"; enforced?: boolean; call_max?: number
}
type WsMsg = Result | { error: string }
type Alert = { id: number; time: string; risk: number; level: AlertLevel; layer: string }

const C = { cyan: "#5EEAD4", ok: "#22C55E", warn: "#F59E0B", threat: "#FF4D6D", info: "#38BDF8", text: "#F1F5F9", muted: "#64748B", surface: "#0F1117", faint: "rgba(255,255,255,0.07)" }
// "aasist" is the historical KEY the backend still emits for the primary neural
// slot — today that slot is the XLS-R + W2VAASIST detector, so label it honestly.
const LAYERS: [string, string][] = [["aasist", "Neural · XLS-R deepfake"], ["clone_v3", "Neural · Clone specialist"], ["mfcc", "Spectral Biometrics"], ["breath", "Breath Pattern"], ["phase", "Phase Coherence"], ["liveness", "Active Liveness"]]
const levelColor = (l?: AlertLevel) => (l === "RED" ? C.threat : l === "AMBER" ? C.warn : l === "GREEN" ? C.ok : l === "UNCERTAIN" ? C.info : C.muted)
const bandColor = (score: number) => (score >= 70 ? C.threat : score >= 40 ? C.warn : C.ok)
const actionColor = (a?: Action) => (a === "BLOCK" ? C.threat : a === "CHALLENGE" ? C.warn : C.ok)
const TACTIC_LABEL: Record<string, string> = {
  coaching: "Being coached", duress: "Under duress", scam_narrative: "Scam narrative",
  agent_pressure: "Pressuring agent", high_risk_intent: "High-risk request", third_party_benefit: "Pays a stranger",
}

function topLayer(b: Record<string, number>): string {
  let best = "", bv = -1
  for (const [k, label] of LAYERS) { const v = b[k] ?? 0; if (v > bv) { bv = v; best = label } }
  return best
}

export default function LiveMonitor() {
  const [result, setResult] = useState<Result | null>(null)
  const [shadow, setShadow] = useState(false)  // false = enforce (acts), true = shadow (advisory)
  const [mode, setMode] = useState<"idle" | "file" | "mic">("idle")
  const [fileName, setFileName] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState<string | null>(null)
  // time-to-flag: problem statement requires "High Risk within the first 10
  // seconds" — measure it and show it, per session (reset on each new stream).
  const [flaggedAt, setFlaggedAt] = useState<number | null>(null)
  const startTsRef = useRef<number | null>(null)
  const flaggedRef = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const stopVisualRef = useRef<(() => void) | null>(null)
  const seq = useRef(0)

  const onMessage = useCallback((msg: WsMsg) => {
    if ("error" in msg) { setError(msg.error); return }
    setResult(msg)
    if (msg.alert_level === "RED" && !flaggedRef.current && startTsRef.current !== null) {
      flaggedRef.current = true
      setFlaggedAt((performance.now() - startTsRef.current) / 1000)
    }
    setAlerts((a) => [{ id: ++seq.current, time: new Date().toLocaleTimeString(), risk: msg.risk_score, level: msg.alert_level, layer: topLayer(msg.layer_breakdown) }, ...a].slice(0, 12))
  }, [])
  // URL carries the policy mode; flipping it reconnects with the new mode.
  const { status, send, reconnect } = useWebSocket<WsMsg>(`${WS_URL}?shadow=${shadow}`, onMessage)
  const mic = useMicStream(send)

  const cleanup = useCallback(() => {
    stopVisualRef.current?.(); stopVisualRef.current = null
    abortRef.current?.abort()
    mic.stop()
  }, [mic])
  // Tear down ONLY on unmount. Keying this effect on `cleanup` (which changes
  // every render) would stop the mic/visualizer on every verdict — a churn loop.
  const cleanupRef = useRef(cleanup); cleanupRef.current = cleanup
  useEffect(() => () => cleanupRef.current(), [])

  const analyzeFile = useCallback(async (file: File) => {
    cleanup(); setError(null); setResult(null); setFileName(file.name); setMode("file")
    startTsRef.current = performance.now(); flaggedRef.current = false; setFlaggedAt(null)
    reconnect()
    try {
      const pcm = await decodeTo16kMono(file)
      stopVisualRef.current = playAndVisualize(pcm, canvasRef.current)
      abortRef.current = new AbortController()
      await streamPcm(pcm, send, { signal: abortRef.current.signal })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setMode("idle")
    }
  }, [cleanup, reconnect, send])

  const toggleMic = useCallback(async () => {
    if (mode === "mic") { cleanup(); setMode("idle"); return }
    cleanup(); setError(null); setResult(null); setMode("mic")
    startTsRef.current = performance.now(); flaggedRef.current = false; setFlaggedAt(null)
    reconnect()
    try {
      const analyser = await mic.start()
      stopVisualRef.current = renderSpectrogram(canvasRef.current, analyser)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setMode("idle")
    }
  }, [mode, cleanup, reconnect, mic])

  const risk = result?.risk_score ?? 0
  const color = levelColor(result?.alert_level)
  const R = 90, CIRC = Math.PI * R, pct = risk / 100

  return (
    <div className="rounded-2xl p-8 md:p-10" style={{ backgroundColor: C.surface, border: `1px solid ${C.faint}` }}>
      {/* status + controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-mono text-[11px] tracking-wider" style={{ color: C.muted }}>
          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ backgroundColor: status === "open" ? C.ok : status === "connecting" ? C.cyan : C.threat }} />
          {status === "open" ? "LIVE SOCKET CONNECTED" : status === "connecting" ? "CONNECTING…" : "DETECTOR OFFLINE"}
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShadow((s) => !s)}
            title="Shadow = score & log but take no action (pilot). Enforce = act on verdicts."
            className="rounded-full px-4 py-2 text-[12px] font-medium transition-colors"
            style={{ border: `1px solid ${shadow ? C.muted : C.ok}`, color: shadow ? C.muted : C.ok }}>
            {shadow ? "◐ Shadow (advisory)" : "● Enforce (live)"}
          </button>
          <button onClick={() => inputRef.current?.click()} disabled={mode !== "idle"}
            className="rounded-full px-4 py-2 text-[12px] font-medium transition-colors disabled:opacity-40"
            style={{ border: `1px solid ${C.cyan}`, color: C.cyan, backgroundColor: "transparent" }}>
            {mode === "file" ? `Streaming ${fileName ?? ""}…` : "Stream a file"}
          </button>
          <button onClick={toggleMic} disabled={mode === "file"}
            className="rounded-full px-4 py-2 text-[12px] font-medium transition-colors disabled:opacity-40"
            style={{ border: `1px solid ${mode === "mic" ? C.threat : C.cyan}`, color: mode === "mic" ? C.threat : C.cyan }}>
            {mode === "mic" ? "■ Stop microphone" : "● Use microphone"}
          </button>
          <input ref={inputRef} type="file" accept=".wav,.mp3,.flac,.ogg,.webm,.m4a,audio/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) analyzeFile(f); e.target.value = "" }} />
        </div>
      </div>

      {/* input-quality banner — the honest "can't judge" state (Problem 3).
          When the mic/line is too degraded to trust the score, we abstain
          (UNCERTAIN) and tell the caller exactly what to fix. */}
      {result?.quality && !result.quality.ok && (
        <div className="mt-6 rounded-xl px-5 py-3 flex items-center gap-3"
          style={{ border: `1px solid ${C.info}`, backgroundColor: "rgba(56,189,248,0.06)" }}>
          <span className="font-mono text-[13px]" style={{ color: C.info }}>◑ INPUT QUALITY LOW</span>
          <span className="text-[13px]" style={{ color: C.text }}>{result.quality.reason}</span>
          <span className="font-mono text-[11px] ml-auto" style={{ color: C.muted }}>
            quality {result.quality.score}/100{typeof result.quality.snr_db === "number" ? ` · SNR ${result.quality.snr_db} dB` : ""} · verdict held
          </span>
        </div>
      )}

      {/* HIGH RISK banner — the problem statement's literal expected outcome:
          "flag the call as High Risk within the first 10 seconds". We show the
          measured time-to-flag against that budget. */}
      {result?.alert_level === "RED" && (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
          className="mt-6 rounded-xl px-5 py-3 flex flex-wrap items-center gap-3"
          style={{ border: `1px solid ${C.threat}`, backgroundColor: "rgba(255,77,109,0.08)" }}>
          <span className="font-mono font-bold text-[14px] tracking-wider" style={{ color: C.threat }}>
            ⚠ HIGH RISK
          </span>
          <span className="text-[13px]" style={{ color: C.text }}>
            synthetic artifacts detected — micro-imperfections in pitch/frequency
          </span>
          {flaggedAt !== null && (
            <span className="font-mono text-[11px] ml-auto" style={{ color: flaggedAt <= 10 ? C.ok : C.warn }}>
              flagged at {flaggedAt.toFixed(1)}s · 10s budget {flaggedAt <= 10 ? "✓" : "exceeded"}
            </span>
          )}
        </motion.div>
      )}

      <div className="mt-8 grid gap-8 md:grid-cols-2 items-center">
        {/* live gauge */}
        <div className="flex flex-col items-center">
          <svg width="220" height="130" viewBox="0 0 220 130">
            <path d={`M 20 110 A ${R} ${R} 0 0 1 200 110`} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" strokeLinecap="round" />
            <path d={`M 20 110 A ${R} ${R} 0 0 1 200 110`} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - pct)} style={{ transition: "stroke-dashoffset 0.5s, stroke 0.4s" }} />
          </svg>
          <div className="-mt-6 text-center">
            <div className="font-mono font-bold text-[56px] leading-none" style={{ color }}>{String(risk).padStart(2, "0")}</div>
            <div className="mt-2 font-mono text-[11px] tracking-[0.2em]" style={{ color }}>
              {result ? `${risk} / 100 · ${result.alert_level}` : mode !== "idle" ? "ANALYZING…" : "WAITING FOR AUDIO"}
            </div>
            {result && (
              <div className="mt-1.5 font-mono text-[11px] tracking-[0.2em]" style={{ color: bandColor(result.call_max ?? risk) }}>
                PEAK {String(result.call_max ?? risk).padStart(2, "0")}
              </div>
            )}
          </div>
        </div>

        {/* live spectrogram */}
        <div>
          <div className="font-mono text-[11px] tracking-wider mb-2" style={{ color: C.muted }}>LIVE SPECTROGRAM</div>
          <div className="relative">
            <canvas ref={canvasRef} width={512} height={150} className="w-full rounded-lg" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
            {/* artifact-window highlight: the newest ~4s region (right edge) is
                the window the detector just scored — outline it when it reads RED
                so "analyzes the spectrogram" is visibly true. */}
            {result?.alert_level === "RED" && (
              <div className="absolute top-0 right-0 h-full rounded-r-lg pointer-events-none"
                style={{ width: "23%", border: `1px solid ${C.threat}`, backgroundColor: "rgba(255,77,109,0.10)" }}>
                <span className="absolute bottom-1 right-1.5 font-mono text-[9px] tracking-wider" style={{ color: C.threat }}>
                  ARTIFACT WINDOW
                </span>
              </div>
            )}
          </div>
          <div className="font-mono text-[10px] mt-2" style={{ color: C.muted }}>128-band · {TARGET_SR / 1000} kHz · 4s window, 2s hop</div>
        </div>
      </div>

      {/* shield decision: fused action + scam-script + novelty */}
      <div className="mt-8 grid gap-3 md:grid-cols-[auto_1fr] md:items-center">
        <div className="rounded-xl px-5 py-3 flex items-center gap-3" style={{ border: `1px solid ${actionColor(result?.action)}` }}>
          <span className="font-mono text-[10px] tracking-[0.2em]" style={{ color: C.muted }}>RECOMMENDED ACTION</span>
          <span className="font-mono font-bold text-[15px] tracking-wider" style={{ color: actionColor(result?.action) }}>
            {result?.action ?? "—"}
          </span>
          {result?.mode === "shadow" && (
            <span className="rounded-full px-2 py-0.5 text-[9px] tracking-wider" style={{ border: `1px solid ${C.muted}`, color: C.muted }}>
              SHADOW · ADVISORY
            </span>
          )}
        </div>
        <div className="text-[12px]" style={{ color: C.muted }}>
          {result?.action_reason || "Fuses synthetic-voice, APP-fraud/coercion and transaction context into one decision."}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] tracking-wider" style={{ color: C.muted }}>
          APP-FRAUD RISK {result?.scam?.score ?? 0}/100
        </span>
        {result?.scam?.language && (
          <span className="font-mono text-[10px] uppercase rounded px-1.5 py-0.5" style={{ border: `1px solid ${C.faint}`, color: C.muted }}>
            {result.scam.language}
          </span>
        )}
        {(result?.scam?.tactics ?? []).map((t) => (
          <span key={t} className="rounded-full px-3 py-1 text-[11px]" style={{ border: `1px solid ${C.warn}`, color: C.warn }}>
            {TACTIC_LABEL[t] ?? t}
          </span>
        ))}
        {!result?.scam?.tactics?.length && (
          <span className="text-[11px]" style={{ color: C.muted }}>no coercion / APP-fraud signals detected</span>
        )}
        {result?.replay?.suspect && (
          <span className="rounded-full px-3 py-1 text-[11px]" title={result.replay.reason}
            style={{ border: `1px solid ${C.threat}`, color: C.threat }}>
            Loudspeaker replay suspected
          </span>
        )}
        <span className="font-mono text-[11px] ml-auto" style={{ color: (result?.novelty ?? 0) >= 0.6 ? C.warn : C.muted }}>
          NOVELTY {Math.round((result?.novelty ?? 0) * 100)}%{(result?.novelty ?? 0) >= 0.6 ? " · unknown signature" : ""}
        </span>
      </div>

      {/* per-layer bars */}
      <div className="mt-8 space-y-3">
        {LAYERS.map(([key, name], i) => {
          const score = result?.layer_breakdown[key] ?? 0
          return (
            <div key={key} className="grid grid-cols-[140px_1fr_36px] items-center gap-4">
              <div className="text-[12px]" style={{ color: C.text }}>{name}</div>
              <div className="h-[2px] w-full overflow-hidden" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
                <motion.div animate={{ width: `${score}%` }} transition={{ duration: 0.5, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
                  style={{ height: "100%", backgroundColor: score >= 70 ? C.threat : score >= 40 ? C.warn : C.cyan }} />
              </div>
              <div className="font-mono text-[11px] text-right" style={{ color: C.muted }}>{score}</div>
            </div>
          )
        })}
      </div>

      {/* alert history */}
      <div className="mt-8 pt-6" style={{ borderTop: `1px solid ${C.faint}` }}>
        <div className="font-mono text-[11px] tracking-wider mb-3" style={{ color: C.muted }}>ALERT HISTORY</div>
        <div className="max-h-48 overflow-y-auto space-y-1.5">
          {alerts.length === 0 && <div className="font-mono text-[11px]" style={{ color: C.muted }}>No windows scored yet — stream a file or start the mic.</div>}
          <AnimatePresence initial={false}>
            {alerts.map((a) => (
              <motion.div key={a.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="grid grid-cols-[80px_1fr_auto] items-center gap-3 font-mono text-[11px]" style={{ color: C.muted }}>
                <span>{a.time}</span>
                <span>call-{String(a.id).padStart(4, "0")} · {a.layer}</span>
                <span style={{ color: levelColor(a.level) }}>{a.level} · {a.risk}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      {error && <div className="mt-4 font-mono text-[11px]" style={{ color: C.threat }}>{error}</div>}

      {/* live demos (frontend routes) + backend product pages */}
      <div className="mt-8 pt-6 flex flex-wrap items-center gap-4" style={{ borderTop: `1px solid ${C.faint}` }}>
        <span className="font-mono text-[10px] tracking-[0.2em]" style={{ color: C.muted }}>LIVE DEMOS</span>
        {[
          ["Live Call (WebRTC)", "/call"],
          ["Voice OTP", "/verify"],
        ].map(([label, path]) => (
          <a key={path} href={path}
            className="font-mono text-[11px] underline-offset-4 hover:underline"
            style={{ color: C.cyan }}>
            {label} ↗
          </a>
        ))}
        <span className="font-mono text-[10px] tracking-[0.2em] ml-4" style={{ color: C.muted }}>BANK PRODUCT PAGES</span>
        {[
          ["Cases · Evidence", "/cases"],
          ["Campaigns", "/campaigns"],
          ["Governance", "/governance"],
          ["Metrics", "/metrics"],
        ].map(([label, path]) => (
          <a key={path} href={`${BACKEND}${path}`} target="_blank" rel="noreferrer"
            className="font-mono text-[11px] underline-offset-4 hover:underline"
            style={{ color: C.cyan }}>
            {label} ↗
          </a>
        ))}
      </div>
    </div>
  )
}

/** Scrolling 128-band spectrogram from a live AnalyserNode. Returns a stop fn. */
function renderSpectrogram(canvas: HTMLCanvasElement | null, analyser: AnalyserNode | null): () => void {
  if (!canvas || !analyser) return () => {}
  const ctx = canvas.getContext("2d")
  if (!ctx) return () => {}
  const w = canvas.width, h = canvas.height
  ctx.clearRect(0, 0, w, h)
  const bins = analyser.frequencyBinCount
  const data = new Uint8Array(bins)
  let raf = 0, stopped = false, last = 0
  const colH = h / bins + 1
  const draw = (t: number) => {
    if (stopped) return
    raf = requestAnimationFrame(draw)
    // ~30fps cap: enough for a live feel, half the main-thread cost of 60fps.
    if (t - last < 33) return
    last = t
    analyser.getByteFrequencyData(data)
    // Scroll left with a GPU-accelerated self-blit instead of a per-frame
    // getImageData/putImageData CPU readback (that readback froze the tab).
    ctx.drawImage(canvas, -1, 0)
    ctx.clearRect(w - 1, 0, 1, h)
    for (let i = 0; i < bins; i++) {
      const v = data[i] / 255
      ctx.fillStyle = `hsl(${175 - v * 120}, 80%, ${10 + v * 50}%)`
      ctx.fillRect(w - 1, h - (i / bins) * h, 1, colH)
    }
  }
  raf = requestAnimationFrame(draw)
  return () => { stopped = true; cancelAnimationFrame(raf) }
}

/** Play decoded PCM through an AnalyserNode and draw its spectrogram. Returns a stop fn. */
function playAndVisualize(pcm: Float32Array, canvas: HTMLCanvasElement | null): () => void {
  if (!canvas) return () => {}
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const ac = new AC()
  const buffer = ac.createBuffer(1, pcm.length, TARGET_SR)
  buffer.copyToChannel(new Float32Array(pcm), 0)  // fresh ArrayBuffer-backed copy (TS5.8 typed-array generics)
  const src = ac.createBufferSource()
  src.buffer = buffer
  const analyser = ac.createAnalyser()
  analyser.fftSize = 256
  src.connect(analyser)
  analyser.connect(ac.destination)
  src.start()
  const stopDraw = renderSpectrogram(canvas, analyser)
  const stop = () => { stopDraw(); try { src.stop() } catch { /* already stopped */ } ; ac.close().catch(() => {}) }
  src.onended = stop
  return stop
}
