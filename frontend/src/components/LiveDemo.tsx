import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
const BACKEND = import.meta.env.VITE_API_URL || "http://localhost:8000";


type Phase = "idle" | "analyzing" | "done";
type Verdict = "PROTECTED" | "REVIEW" | "CRITICAL";

const LAYERS = ["Neural · XLS-R deepfake", "Spectral Biometrics", "Breath Pattern", "Phase Coherence", "Active Liveness"];

const verdictColor = (v: Verdict) => (v === "PROTECTED" ? "#22C55E" : v === "CRITICAL" ? "#FF4D6D" : "#F59E0B");
type Action = "MONITOR" | "CHALLENGE" | "BLOCK";
const actionColor = (a?: Action) => (a === "BLOCK" ? "#FF4D6D" : a === "CHALLENGE" ? "#F59E0B" : "#22C55E");
const TACTIC_LABEL: Record<string, string> = {
  coaching: "Being coached", duress: "Under duress", scam_narrative: "Scam narrative",
  agent_pressure: "Pressuring agent", high_risk_intent: "High-risk request", third_party_benefit: "Pays a stranger",
};

function formatSize(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}

export default function LiveDemo() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [hover, setHover] = useState(false);
  const [amount, setAmount] = useState("");
  const [newBeneficiary, setNewBeneficiary] = useState(false);
  const [result, setResult] = useState<{
    score: number; verdict: Verdict; layers: number[];
    action?: Action; actionReason?: string; scam?: { score: number; tactics: string[] }; novelty?: number;
    campaign?: { repeat_voice?: boolean; cluster_size?: number; blocklist_hit?: boolean };
  } | null>(null);

  async function handleFile(f: File | null) {
    if (!f) return;
  
    setFile(f);
    setPhase("analyzing");
  
    try {
      const form = new FormData();
      form.append("audio", f, f.name);
      form.append("amount", amount || "0");
      form.append("new_beneficiary", String(newBeneficiary));

      console.log("Sending to:", `${BACKEND}/api/analyze`);
  
      const resp = await fetch(`${BACKEND}/api/analyze`, {
        method: "POST",
        body: form,
      });
  
      if (!resp.ok) {
        throw new Error(`Server error ${resp.status}`);
      }
  
      const data = await resp.json();
  
      console.log("Backend response:", data);
  
      let verdict: Verdict = "REVIEW";
  
      if (data.alert_level === "GREEN") {
        verdict = "PROTECTED";
      } else if (data.alert_level === "RED") {
        verdict = "CRITICAL";
      }
  
      if (data.alert_level === "AMBER") verdict = "REVIEW";

      setResult({
        score: data.risk_score,
        verdict,
        layers: [
          data.layer_breakdown?.aasist ?? 0,
          data.layer_breakdown?.mfcc ?? 0,
          data.layer_breakdown?.breath ?? 0,
          data.layer_breakdown?.phase ?? 0,
          data.layer_breakdown?.liveness ?? 0,
        ],
        action: data.action,
        actionReason: data.action_reason,
        scam: data.scam,
        novelty: data.novelty,
        campaign: data.campaign,
      });
  
      setPhase("done");
    } catch (err) {
      console.error("Analyze failed:", err);
      setPhase("idle");
    }
  }

  function reset() {
    setFile(null);
    setResult(null);
    setPhase("idle");
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div
      className="mx-auto w-full max-w-[640px] rounded-2xl p-8 md:p-10"
      style={{ backgroundColor: "#0F1117", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".wav,.mp3,.flac,.ogg,audio/*"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
      />

      {phase === "idle" && (
        <div className="mb-5 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 font-mono text-[11px] tracking-wider text-[#64748B]">
            TRANSFER ₹
            <input type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0"
              className="w-28 rounded-md bg-transparent px-2 py-1 text-[12px] text-[#F1F5F9] outline-none"
              style={{ border: "1px solid rgba(255,255,255,0.12)" }} />
          </label>
          <label className="flex items-center gap-2 font-mono text-[11px] tracking-wider text-[#64748B] cursor-pointer">
            <input type="checkbox" checked={newBeneficiary} onChange={(e) => setNewBeneficiary(e.target.checked)} />
            NEW BENEFICIARY
          </label>
          <span className="font-mono text-[10px] text-[#475569]">context → drives the Monitor/Challenge/Block decision</span>
        </div>
      )}

      <AnimatePresence mode="wait">
        {phase === "idle" && (
          <motion.button
            key="zone"
            type="button"
            onClick={() => inputRef.current?.click()}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            onDragOver={(e) => { e.preventDefault(); setHover(true); }}
            onDragLeave={() => setHover(false)}
            onDrop={(e) => { e.preventDefault(); setHover(false); handleFile(e.dataTransfer.files?.[0] ?? null); }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="w-full rounded-xl flex flex-col items-center justify-center text-center transition-colors"
            style={{
              padding: 48,
              border: `1.5px ${hover ? "solid" : "dashed"} ${hover ? "#5EEAD4" : "rgba(255,255,255,0.12)"}`,
              backgroundColor: hover ? "rgba(94,234,212,0.04)" : "transparent",
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#5EEAD4" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 16V4M6 10l6-6 6 6" />
              <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            </svg>
            <p className="mt-4 text-[15px] text-[#F1F5F9]">Drop audio here or click to browse</p>
            <p className="mt-1.5 font-mono text-[11px] text-[#64748B] tracking-wider">WAV · MP3 · FLAC · OGG</p>
          </motion.button>
        )}

        {phase === "analyzing" && file && (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="py-6"
          >
            <div className="flex items-center justify-between font-mono text-[12px] text-[#F1F5F9]">
              <span className="truncate pr-4">{file.name}</span>
              <span className="text-[#64748B]">{formatSize(file.size)}</span>
            </div>
            <div className="mt-6 h-[2px] w-full overflow-hidden" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
              <motion.div
                initial={{ width: "0%" }}
                animate={{ width: "100%" }}
                transition={{ duration: 2.5, ease: "linear" }}
                style={{ backgroundColor: "#5EEAD4", height: "100%" }}
              />
            </div>
            <div className="mt-4 flex items-center gap-2 font-mono text-[11px] tracking-wider text-[#64748B]">
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.2, repeat: Infinity }}
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: "#5EEAD4" }}
              />
              ANALYZING...
            </div>
          </motion.div>
        )}

        {phase === "done" && result && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div className="flex items-end justify-between">
              <div>
                <div className="font-mono text-[64px] leading-none font-bold" style={{ color: verdictColor(result.verdict) }}>
                  {String(result.score).padStart(2, "0")}
                </div>
                <div className="mt-2 font-mono text-[11px] tracking-[0.2em]" style={{ color: verdictColor(result.verdict) }}>
                  {result.verdict}
                </div>
              </div>
              <div className="font-mono text-[11px] text-[#64748B] text-right truncate max-w-[50%]">{file?.name}</div>
            </div>

            {/* fused decision */}
            <div className="mt-6 rounded-xl px-5 py-4" style={{ border: `1px solid ${actionColor(result.action)}` }}>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[10px] tracking-[0.2em] text-[#64748B]">RECOMMENDED ACTION</span>
                <span className="font-mono font-bold text-[15px] tracking-wider" style={{ color: actionColor(result.action) }}>
                  {result.action ?? "—"}
                </span>
              </div>
              {result.actionReason && <div className="mt-1.5 text-[12px] text-[#94A3B8]">{result.actionReason}</div>}
              {result.campaign?.blocklist_hit && (
                <div className="mt-2 text-[12px]" style={{ color: "#FF4D6D" }}>
                  ⚠ Known fraud voiceprint — this voice has been flagged before.
                </div>
              )}
              {result.campaign?.repeat_voice && !result.campaign?.blocklist_hit && (
                <div className="mt-2 text-[12px]" style={{ color: "#F59E0B" }}>
                  ↺ Repeat voice — same voiceprint seen across {result.campaign?.cluster_size ?? 2} calls (possible campaign).
                </div>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-[#64748B]">APP-FRAUD RISK {result.scam?.score ?? 0}/100</span>
                {(result.scam?.tactics ?? []).map((t) => (
                  <span key={t} className="rounded-full px-3 py-1 text-[11px]" style={{ border: "1px solid #F59E0B", color: "#F59E0B" }}>
                    {TACTIC_LABEL[t] ?? t}
                  </span>
                ))}
                <span className="font-mono text-[11px] ml-auto" style={{ color: (result.novelty ?? 0) >= 0.6 ? "#F59E0B" : "#64748B" }}>
                  NOVELTY {Math.round((result.novelty ?? 0) * 100)}%{(result.novelty ?? 0) >= 0.6 ? " · unknown" : ""}
                </span>
              </div>
            </div>

            <div className="mt-8 space-y-3">
              {LAYERS.map((name, i) => (
                <motion.div
                  key={name}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1, duration: 0.4 }}
                  className="grid grid-cols-[140px_1fr_36px] items-center gap-4"
                >
                  <div className="text-[12px] text-[#F1F5F9]">{name}</div>
                  <div className="h-[2px] w-full overflow-hidden" style={{ backgroundColor: "rgba(255,255,255,0.06)" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${result.layers[i]}%` }}
                      transition={{ delay: i * 0.1 + 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                      style={{ height: "100%", backgroundColor: "#5EEAD4" }}
                    />
                  </div>
                  <div className="font-mono text-[11px] text-[#64748B] text-right">{result.layers[i]}</div>
                </motion.div>
              ))}
            </div>

            <button
              onClick={reset}
              className="mt-8 text-[12px] text-[#64748B] hover:text-[#5EEAD4] transition-colors"
            >
              ← Analyze another file
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
