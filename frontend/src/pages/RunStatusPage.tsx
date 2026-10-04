import { useEffect, useState } from "react";
import { approveInterpretation, getRun, retryRun } from "../data/api";
import type { AnalysisRun } from "../data/types";

interface Props {
  runId: string;
  onOpen: (run: AnalysisRun) => void;
}

const PHASE_LABELS: Record<string, string> = {
  deterministic_analysis_queued: "Waiting for the local analysis worker",
  canonicalizing: "Building and validating canonical events",
  detecting_behavioral_changes: "Detecting population-level behavioral changes",
  exporting_context: "Collecting nearby context",
  building_evidence_brief: "Building the compact evidence brief",
  reconstructing_evidence: "Reconstructing source-linked evidence",
  deterministic_analysis_complete: "Deterministic analysis complete",
  interpretation_approved: "Analyst interpretation approved",
  generating_analyst_interpretation: "Generating bounded analyst interpretations",
  packaging_runtime_investigation: "Packaging the investigation",
  completed: "Investigation ready",
};

export function RunStatusPage({ runId, onOpen }: Props) {
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const next = await getRun(runId);
        if (!active) return;
        setRun(next);
        if (!["completed", "failed", "awaiting_interpretation_approval"].includes(next.status)) {
          timer = window.setTimeout(refresh, 1200);
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Run status is unavailable.");
      }
    };
    void refresh();
    return () => { active = false; if (timer) window.clearTimeout(timer); };
  }, [runId, refreshKey]);

  const interpret = async () => {
    setActing(true); setError(null);
    try {
      setRun(await approveInterpretation(runId));
      setRefreshKey((value) => value + 1);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Interpretation could not start."); }
    finally { setActing(false); }
  };

  const retry = async () => {
    setActing(true); setError(null);
    try {
      setRun(await retryRun(runId));
      setRefreshKey((value) => value + 1);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The run could not be retried."); }
    finally { setActing(false); }
  };

  return (
    <main className="page-shell workflow-page run-status-page">
      <div className="eyebrow">Swarm investigation</div>
      <h1>{run?.status === "completed" ? "Investigation ready" : "Analysis in progress"}</h1>
      {!run && !error && <p>Loading run status…</p>}
      {run && <div className="run-phase"><span>{run.status.replaceAll("_", " ")}</span><strong>{PHASE_LABELS[run.phase] || run.phase.replaceAll("_", " ")}</strong></div>}
      {run?.status === "awaiting_interpretation_approval" && (
        <section className="interpretation-approval">
          <h2>Deterministic analysis is complete</h2>
          <p>
            Continue to generate bounded analyst interpretations with the configured model. This may
            incur API usage. The source evidence, detector ranking, and reconstruction will not be changed.
          </p>
          <button className="outline-button" disabled={acting} onClick={() => void interpret()}>
            {acting ? "Starting…" : "Generate analyst interpretation"}
          </button>
        </section>
      )}
      {run?.status === "failed" && (
        <section className="workflow-error">
          <h2>Run failed</h2><p>{run.error}</p>
          {run.retryable && <button className="outline-button" disabled={acting} onClick={() => void retry()}>Retry using existing artifacts</button>}
        </section>
      )}
      {run?.status === "completed" && (
        <button className="outline-button" onClick={() => onOpen(run)}>Open investigation →</button>
      )}
      {error && <p className="workflow-error" role="alert">{error}</p>}
    </main>
  );
}
