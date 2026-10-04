import { useState } from "react";
import "./swarmlens-fonts.css";

const points = [
  { rank: 1, time: "May 15 · 17:30", mag: 88, title: "Workstreams redistribute", summary: "Intention shifts sharply as one research stream winds down while side-project and governance work expands.", note: "A mixed population transition: completion in one stream, continued production elsewhere.", process: "Corrective coordination", conf: "Moderate", div: "Low" },
  { rank: 2, time: "May 12 · 17:30", mag: 100, title: "Research conclusion reverses", summary: "New judge data coincides with a sharp intention and communication transition around the #best experiment.", note: "The evidence neighborhood contains a major empirical update alongside negotiated consolidation of duplicate work.", process: "Corrective coordination", conf: "Moderate", div: "Low" },
  { rank: 3, time: "May 15 · 20:30", mag: 72, title: "Late-session consolidation", summary: "Participation and intentions redistribute toward completion, governance, and project wrap-up.", note: "Milestone production continues while several agents move into consolidation and audit work.", process: "Information diffusion", conf: "Moderate", div: "Low" },
  { rank: 4, time: "May 12 · 20:30", mag: 82, title: "Pipeline structure changes", summary: "All four detector views move around a structured proposer → skeptic → revision → scoring workflow.", note: "Research wrap-up overlaps with continued replication dependencies and later pipeline-failure findings.", process: "Delegation / role differentiation", conf: "Moderate", div: "Low" },
  { rank: 5, time: "May 13 · 20:00", mag: 64, title: "Replication wave emerges", summary: "Intention shifts toward Kimi, label-swap, replication and judge-robustness work.", note: "Replication-analysis revision appears alongside other active workstreams.", process: "Corrective coordination", conf: "Moderate", div: "Low" },
];

const signals = [
  { name: "Communication", color: "#5B7FA3", tint: "#EEF3F7" },
  { name: "Intention", color: "#A76565", tint: "#F8EFEF" },
  { name: "Participation", color: "#B08752", tint: "#F8F3E9" },
  { name: "Action type", color: "#88749C", tint: "#F3F0F6" },
];

export const SwarmLensEpisodeInvestigation = () => {
  const [selected, setSelected] = useState(1);
  const p = points[selected];

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

    <section className="px-10 py-12 max-w-[1440px] mx-auto">
      <div className="grid grid-cols-[1fr_auto] gap-8 items-end border-b border-[#c8d6cd] pb-10">
        <div>
          <div className="text-[15px] font-semibold tracking-[.14em] uppercase text-[#4b6959] mb-4">Episode / Incident Map</div>
          <h1 className="font-serif text-[64px] leading-[.98] text-[#294438]">Perform novel research!</h1>
          <p className="mt-6 text-[19px] text-[#5f6f66]">11 May — 18 May 2026 · 6,916 canonical records · five detected behavioral turning points</p>
        </div>
        <div className="text-right text-[16px] leading-7 text-[#5f6f66]">Ranked by behavioral change<br/><span className="text-[#4f735f]">●</span> marker size = transition magnitude</div>
      </div>

      <div className="mt-10 border-y border-[#d6e0da] py-14 relative">
        <div className="flex justify-between text-[14px] font-medium uppercase tracking-[.09em] text-[#64736a] mb-14">
          <span>May 11</span><span>May 12</span><span>May 13</span><span>May 14</span><span>May 15</span><span>May 16</span><span>May 17</span><span>May 18</span>
        </div>
        <div className="h-px bg-[#8ea094] relative mx-2">
          {points.map((x, i) => <button
            key={i}
            aria-label={`Select turning point ${x.rank}: ${x.title}`}
            onClick={() => setSelected(i)}
            className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer group focus:outline-none"
            style={{ left: [62, 24, 70, 31, 43][i] + "%" }}
          >
            <span
              className={`block rounded-full border-[3px] transition-all duration-150 group-hover:scale-110 ${selected === i ? "bg-[#4f735f] border-[#4f735f] scale-110 shadow-[0_0_0_4px_rgba(79,115,95,0.12)]" : "bg-[#fbfcfa] border-[#6f8a7a] group-hover:border-[#3f6552]"}`}
              style={{ width: 18 + x.mag / 4.8, height: 18 + x.mag / 4.8 }}
            />
            <span className={`absolute top-[calc(100%+11px)] left-1/2 -translate-x-1/2 text-[15px] font-semibold whitespace-nowrap ${selected === i ? "text-[#315441]" : "text-[#53655b]"}`}>#{x.rank}</span>
          </button>)}
        </div>

        <div className="mt-24">
          <div className="text-[15px] font-semibold uppercase tracking-[.12em] text-[#4b6959] mb-4">Detector signal families</div>
          <div className="grid grid-cols-4 max-w-[900px] border border-[#c8d6cd] text-[16px] bg-white/70">
            {signals.map(s => <div key={s.name} className="px-5 py-4 border-r last:border-r-0 border-[#c8d6cd] flex items-center gap-3" style={{ backgroundColor: s.tint }}>
              <span className="h-3.5 w-3.5 rounded-full shrink-0" style={{ backgroundColor: s.color }}/><span className="font-medium">{s.name}</span>
            </div>)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[1.55fr_.8fr] border-b border-[#c8d6cd] bg-[#fdfffd]">
        <div className="py-12 pr-12 border-r border-[#c8d6cd]">
          <div className="flex justify-between text-[15px] font-semibold uppercase tracking-[.11em] text-[#4b6959]"><span>Selected turning point #{p.rank}</span><span>{p.time} UTC</span></div>
          <h2 className="font-serif text-[44px] mt-5 text-[#294438]">{p.title}</h2>
          <div className="mt-9 grid grid-cols-2 gap-12">
            <div>
              <div className="text-[16px] font-semibold uppercase tracking-[.08em] mb-4 text-[#40594c]">What changed?</div>
              <p className="font-serif text-[27px] leading-9 text-[#2d3a33]">{p.summary}</p>
            </div>
            <div>
              <div className="text-[16px] font-semibold uppercase tracking-[.08em] mb-4 text-[#40594c]">Analyst interpretation</div>
              <p className="text-[19px] leading-8 text-[#55655c]">{p.note}</p>
            </div>
          </div>
        </div>
        <div className="py-12 pl-10">
          <div className="text-[16px] font-semibold uppercase tracking-[.08em] text-[#4b6959]">Possible social process</div>
          <div className="font-serif text-[32px] mt-4 text-[#294438]">{p.process}</div>
          <div className="mt-7 grid grid-cols-2 gap-5 text-[17px] text-[#536159]">
            <div><span className="block text-[14px] uppercase tracking-wide text-[#6d7c73] mb-1">Confidence</span><b>{p.conf}</b></div>
            <div><span className="block text-[14px] uppercase tracking-wide text-[#6d7c73] mb-1">Evidence diversity</span><b>{p.div}</b></div>
          </div>
          <button className="mt-9 cursor-pointer border border-[#799483] px-7 py-3.5 text-[17px] text-[#315441] bg-[#fdfefd] hover:bg-[#edf4ef] hover:border-[#4f735f] transition-colors">Investigate turning point →</button>
        </div>
      </div>
    </section>
  </main>;
};
