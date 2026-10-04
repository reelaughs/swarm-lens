import { useEffect, useState } from "react";
import { createRun, getDataset, getScopes } from "../data/api";
import type { DatasetRecord, InvestigationScope } from "../data/types";
import { utcDate } from "../lib/format";

interface Props {
  datasetId: string;
  onRunCreated: (runId: string) => void;
}

export function DatasetPage({ datasetId, onRunCreated }: Props) {
  const [dataset, setDataset] = useState<DatasetRecord | null>(null);
  const [scopes, setScopes] = useState<InvestigationScope[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const next = await getDataset(datasetId);
        if (!active) return;
        setDataset(next);
        if (next.status === "ready_for_episode_selection") {
          setScopes(await getScopes(datasetId));
        } else if (next.status !== "failed") {
          timer = window.setTimeout(refresh, 1000);
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Validation status is unavailable.");
      }
    };
    void refresh();
    return () => { active = false; if (timer) window.clearTimeout(timer); };
  }, [datasetId]);

  const start = async (scope: InvestigationScope) => {
    setStarting(scope.scope_id);
    setError(null);
    try {
      const run = await createRun(datasetId, scope.scope_id);
      onRunCreated(run.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The analysis run could not be created.");
      setStarting(null);
    }
  };

  return (
    <main className="page-shell workflow-page">
      <div className="eyebrow">Dataset validation</div>
      <h1>{dataset?.status === "ready_for_episode_selection" ? "Choose an episode" : "Validating dataset"}</h1>
      {!dataset && !error && <p>Reading the uploaded bundle…</p>}
      {dataset?.status === "validating" && <p>The bundle is being checked for safe structure, schema integrity, and analyzable episodes.</p>}
      {dataset?.status === "failed" && <div className="workflow-error"><strong>Validation failed</strong><p>{dataset.error}</p></div>}
      {error && <p className="workflow-error" role="alert">{error}</p>}
      {scopes.length > 0 && (
        <section className="scope-list" aria-label="Available investigation episodes">
          {scopes.map((scope) => (
            <article className="scope-card" key={scope.scope_id}>
              <div>
                <h2>{scope.title}</h2>
                <p>
                  {utcDate.format(new Date(scope.start))} — {scope.end ? utcDate.format(new Date(scope.end)) : "Ongoing"}
                </p>
                {scope.warnings.map((warning) => <small key={warning}>{warning}</small>)}
                {!scope.runnable && <p className="scope-blocker">Unavailable: {scope.blocking_reason}</p>}
              </div>
              <button
                className="outline-button"
                disabled={!scope.runnable || starting !== null}
                onClick={() => void start(scope)}
              >
                {starting === scope.scope_id ? "Starting…" : "Run analysis"}
              </button>
            </article>
          ))}
        </section>
      )}
      <p className="workflow-note">Custom investigation windows are planned; this version supports authoritative closed episodes.</p>
    </main>
  );
}
