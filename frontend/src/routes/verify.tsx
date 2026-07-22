import { createFileRoute } from "@tanstack/react-router"
import { useCallback, useRef, useState } from "react"

// Voice OTP / step-up authentication demo — the use case every voice-biometric
// deployment (app unlock, payment OTP, call-centre step-up) needs but lacks:
// the caller must SPEAK freshly issued digits (content match via ASR — a
// pre-recorded clone can't answer) AND the voice must pass the deepfake
// ensemble (a live TTS rig that answers correctly still fails). Two independent
// gates, one round-trip.

export const Route = createFileRoute("/verify")({ component: VerifyDemo })

const BACKEND = import.meta.env.VITE_API_URL || "http://localhost:8000"
const RECORD_MS = 6000

type VerifyResult = {
  passed: boolean; reason: string
  digits_expected: string; digits_heard: string; transcript: string
  language?: string; alert_level: string; risk_score: number
}
type Challenge = { challenge_id: string; prompt: string; digits: number[] }

const C = { cyan: "#5EEAD4", ok: "#22C55E", warn: "#F59E0B", threat: "#FF4D6D", text: "#F1F5F9", muted: "#64748B", surface: "#0F1117", faint: "rgba(255,255,255,0.08)" }

function VerifyDemo() {
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [phase, setPhase] = useState<"idle" | "recording" | "checking" | "done">("idle")
  const [result, setResult] = useState<VerifyResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [countdown, setCountdown] = useState(0)
  const recRef = useRef<MediaRecorder | null>(null)

  const start = useCallback(async () => {
    setError(null); setResult(null); setPhase("idle")
    try {
      const ch: Challenge = await (await fetch(`${BACKEND}/api/challenge`)).json()
      setChallenge(ch)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      recRef.current = rec
      const chunks: Blob[] = []
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        setPhase("checking")
        try {
          const fd = new FormData()
          fd.append("challenge_id", ch.challenge_id)
          fd.append("audio", new Blob(chunks, { type: rec.mimeType }), "response.webm")
          const r = await fetch(`${BACKEND}/api/challenge/verify`, { method: "POST", body: fd })
          if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`)
          setResult(await r.json())
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        }
        setPhase("done")
      }
      rec.start()
      setPhase("recording")
      // simple fixed window: enough to say 4 digits, short enough to feel live
      let left = RECORD_MS / 1000
      setCountdown(left)
      const iv = setInterval(() => { left -= 1; setCountdown(left); if (left <= 0) clearInterval(iv) }, 1000)
      setTimeout(() => rec.state !== "inactive" && rec.stop(), RECORD_MS)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setPhase("idle")
    }
  }, [])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-8 px-6" style={{ backgroundColor: "#0A0B0F", color: C.text }}>
      <div className="text-center max-w-xl">
        <div className="font-mono text-[12px] tracking-[0.3em]" style={{ color: C.cyan }}>DHWANI-KAVACH · VOICE OTP</div>
        <h1 className="mt-3 text-3xl font-semibold">Speak-to-authenticate, deepfake-proof</h1>
        <p className="mt-2 text-sm" style={{ color: C.muted }}>
          Fresh digits every attempt — a recording can't answer them. A cloned voice that
          answers correctly still fails the synthetic-voice check. Two gates, one step.
        </p>
      </div>

      <div className="w-full max-w-xl rounded-2xl p-8" style={{ backgroundColor: C.surface, border: `1px solid ${C.faint}` }}>
        {phase === "recording" && challenge ? (
          <div className="text-center">
            <div className="font-mono text-[11px] tracking-[0.2em]" style={{ color: C.threat }}>● RECORDING · {countdown}s</div>
            <div className="mt-4 text-sm" style={{ color: C.muted }}>Say these digits, clearly:</div>
            <div className="mt-2 font-mono text-5xl font-bold tracking-[0.3em]" style={{ color: C.cyan }}>
              {challenge.digits.join(" ")}
            </div>
          </div>
        ) : phase === "checking" ? (
          <div className="text-center font-mono text-sm animate-pulse" style={{ color: C.cyan }}>
            verifying — speech content + synthetic-voice ensemble…
          </div>
        ) : result ? (
          <div>
            <div className="text-center">
              <div className="font-mono font-bold text-4xl" style={{ color: result.passed ? C.ok : C.threat }}>
                {result.passed ? "✓ VERIFIED" : "✗ REJECTED"}
              </div>
              <div className="mt-2 text-sm" style={{ color: C.text }}>{result.reason}</div>
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3 font-mono text-[12px]" style={{ color: C.muted }}>
              <div>expected <span style={{ color: C.text }}>{result.digits_expected}</span></div>
              <div>heard <span style={{ color: C.text }}>{result.digits_heard || "—"}</span></div>
              <div>voice check <span style={{ color: result.alert_level === "GREEN" ? C.ok : result.alert_level === "AMBER" ? C.warn : C.threat }}>{result.alert_level}</span></div>
              <div>risk <span style={{ color: C.text }}>{result.risk_score}/100</span></div>
            </div>
            {result.transcript && (
              <div className="mt-4 text-[12px] italic" style={{ color: C.muted }}>"{result.transcript.trim()}"</div>
            )}
          </div>
        ) : (
          <div className="text-center text-sm" style={{ color: C.muted }}>
            Press start — you'll get 4 digits to read back within {RECORD_MS / 1000} seconds.
          </div>
        )}
      </div>

      <button onClick={start} disabled={phase === "recording" || phase === "checking"}
        className="rounded-full px-8 py-3 text-sm font-medium transition-colors disabled:opacity-40"
        style={{ border: `1px solid ${C.cyan}`, color: C.cyan }}>
        {phase === "done" ? "Try again" : "Start verification"}
      </button>

      {error && <div className="font-mono text-[12px]" style={{ color: C.threat }}>{error}</div>}

      <a href="/" className="font-mono text-[11px] underline-offset-4 hover:underline" style={{ color: C.muted }}>
        ← back to dashboard
      </a>
    </div>
  )
}
