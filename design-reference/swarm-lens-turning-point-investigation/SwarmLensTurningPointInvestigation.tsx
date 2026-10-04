import { useState } from "react";
import "./swarmlens-fonts.css";

const evidence = [
  { t: "17:02", kind: "CHAT", agent: "Claude Haiku 4.5", text: "Confirmed as a fresh unstructured-pair participant for Session 4 Task 4; no prior Task 4 exposure." },
  { t: "17:08", kind: "CHAT", agent: "Claude Opus 4.7", text: "Major news with N=4 (Kimi included): raw self-preference collapses; the interpretation changes materially." },
  { t: "17:18", kind: "SESSION GOAL", agent: "GPT-5.1", text: "Continue post-experiment work and help interpret Task 4 results once scorers finish." },
  { t: "17:30", kind: "DETECTOR", agent: "Population boundary", text: "Intention shifts sharply; communication and participation move in the same neighborhood." },
  { t: "17:34", kind: "CHAT", agent: "Kimi K2.6", text: "Acknowledges duplicate analysis work and consolidates toward the retained research artifact." },
  { t: "17:41", kind: "SESSION GOAL", agent: "Research workstream", text: "Update robustness interpretation under the expanded four-judge panel." },
];

const signals = [
  { label: "Communication", value: "+1.8σ", color: "#5B7FA3", tint: "#EEF3F7" },
  { label: "Intention", value: "+3.4σ", color: "#A76565", tint: "#F8EFEF" },
  { label: "Participation", value: "+1.2σ", color: "#B08752", tint: "#F8F3E9" },
  { label: "Action type", value: "+2.1σ", color: "#88749C", tint: "#F3F0F6" },
];

export const SwarmLensTurningPointInvestigation = () => {
  const [raw, setRaw] = useState(false);

  return <main className="swarmlens-shell min-h-screen bg-[#fbfcfa] text-[#29312c] font-sans">
    <header className="h-24 border-b border-[#c8d6cd] flex items-center justify-between px-10 bg-[#fdfefd]">
      <div>
        <span className="font-serif text-[34px] tracking-[-0.01em] text-[#294438]">SwarmLens</span>
        <span className="ml-5 text-[15px] uppercase tracking-[.15em] text-[#587063]">What changed the swarm?</span>
      </div>
      <div className="flex gap-8 text-[16px] text-[#55635b] items-center">
        <span>AI Village</span><span>Retrospective forensics</span>
        <span className="border border-[#bfd0c4] rounded-full px-4 py-2 bg-[#f1f6f2] text-[#3f594b] text-[15px]">Frozen pipeline · v0.1</span>
      </div>
    </header>

    <section className="max-w-[1440px] mx-auto px-10 py-10">
      <div className="text-[17px] text-[#4b6959] mb-8">← Incident map</div>

      <div className="flex justify-between border-b border-[#c8d6cd] pb-9">
        <div>
          <div className="text-[15px] font-semibold uppercase tracking-[.12em] text-[#4b6959]">Turning point #2 · May 12 · 17:30 UTC</div>
          <h1 className="font-serif text-[56px] mt-3 text-[#294438]">Research conclusion reverses</h1>
        </div>
        <div className="text-right text-[16px] leading-7 text-[#5f6f66]"><b>Behavioral-change rank #2</b><br/>Source-linked reconstruction</div>
      </div>

      <div className="grid grid-cols-[1.8fr_1fr]">
        <div className="pr-10 border-r border-[#c8d6cd]">
          <section className="py-11 border-b border-[#c8d6cd]">
            <div className="text-[16px] font-semibold uppercase tracking-[.1em] text-[#4b6959]">01 · What changed?</div>
            <p className="font-serif text-[34px] leading-[1.28] mt-5 max-w-3xl text-[#2d3a33]">New judge data coincides with a sharp intention and communication transition around the #best experiment.</p>
            <div className="mt-9 grid grid-cols-4 border border-[#c8d6cd] bg-white/60">
              {signals.map(s => <div className="p-5 border-r last:border-r-0 border-[#c8d6cd]" key={s.label} style={{ backgroundColor: s.tint }}>
                <div className="flex items-center gap-2.5 text-[15px] font-semibold" style={{ color: s.color }}><span className="h-3 w-3 rounded-full" style={{ backgroundColor: s.color }}/>{s.label}</div>
                <div className="mt-2 text-[19px] font-semibold text-[#314139]">{s.value}</div>
              </div>)}
            </div>
          </section>

          <section className="py-11">
            <div className="flex justify-between items-end">
              <div className="text-[16px] font-semibold uppercase tracking-[.1em] text-[#4b6959]">02 · Evidence sequence</div>
              <div className="text-[15px] text-[#68776e]">−90m / boundary / +120m</div>
            </div>
            <div className="mt-8">{evidence.map((e, i) => <div key={i} className={`grid grid-cols-[82px_135px_180px_1fr] gap-5 py-6 border-t border-[#d6e0da] ${e.kind === "DETECTOR" ? "bg-[#eef4f0] -mx-3 px-3" : ""}`}>
              <span className="font-mono text-[15px] text-[#536159]">{e.t}</span>
              <span className={`text-[15px] font-semibold tracking-wide ${e.kind === "DETECTOR" ? "text-[#3f6b55]" : "text-[#4b6959]"}`}>{e.kind}</span>
              <span className="text-[16px] font-medium text-[#435249]">{e.agent}</span>
              <span className="font-serif text-[21px] leading-7 text-[#2d3a33]">{e.text}</span>
            </div>)}</div>
          </section>
        </div>

        <aside className="pl-10 py-11">
          <section className="pb-10 border-b border-[#c8d6cd]">
            <div className="text-[16px] font-semibold uppercase tracking-[.1em] text-[#4b6959]">03 · Analyst interpretation</div>
            <p className="font-serif text-[30px] leading-9 mt-5 text-[#2d3a33]">The evidence neighborhood contains a major empirical update alongside negotiated consolidation of duplicate research work.</p>
            <p className="mt-6 text-[17px] leading-7 text-[#58675f]">This describes the neighborhood around the detected transition. It does not establish what caused the population-level change.</p>
          </section>

          <section className="py-10 border-b border-[#c8d6cd]">
            <div className="text-[16px] font-semibold uppercase tracking-[.1em] text-[#4b6959]">04 · Possible social process</div>
            <h3 className="font-serif text-[34px] mt-4 text-[#294438]">Corrective coordination</h3>
            <div className="mt-7 grid grid-cols-2 gap-6 text-[17px]">
              <div><span className="block text-[14px] uppercase tracking-wide text-[#6d7c73] mb-1">Confidence</span><b className="text-[19px]">Moderate</b></div>
              <div><span className="block text-[14px] uppercase tracking-wide text-[#6d7c73] mb-1">Evidence diversity</span><b className="text-[19px]">Low</b></div>
            </div>
            <div className="mt-7 text-[17px] leading-7 border-l-[3px] border-[#6f8a7a] pl-5 bg-[#eef4f0] py-4 pr-4 text-[#44554b]">Three supported signatures arise primarily from one underlying evidence chain. Treat them as correlated interpretations, not independent confirmations.</div>
            <div className="mt-7 text-[17px] leading-7"><b>Supported signatures:</b> correction / redirect · response / revision · cross-agent corrective follow-through</div>
            <div className="mt-6 text-[17px] leading-7"><b>Alternative explanation:</b> the exchange may formalize consolidation already underway rather than initiate a new adjustment.</div>
          </section>

          <section className="py-10">
            <button onClick={() => setRaw(!raw)} className="w-full cursor-pointer flex items-center justify-between text-left border-y border-[#c8d6cd] py-5 px-2 group hover:bg-[#edf4ef] transition-colors">
              <span className="text-[16px] font-semibold uppercase tracking-[.1em] text-[#4b6959]">05 · Provenance / raw trace</span>
              <span className="text-[26px] leading-none text-[#587063] group-hover:text-[#315441]">{raw ? "−" : "+"}</span>
            </button>
            {raw && <div className="mt-5 font-mono text-[14px] leading-7 bg-[#f1f6f2] p-6 border border-[#c8d6cd] text-[#435249]">
              <div>swl-e-0037 · chat_messages</div>
              <div>swl-e-0038 · agent_talk link</div>
              <div>swl-e-0020 · session_goal</div>
              <div className="mt-4 text-[#5f6f66]">Canonical source ids preserved in frozen evidence bundle.</div>
            </div>}
          </section>
        </aside>
      </div>
    </section>
  </main>;
};
