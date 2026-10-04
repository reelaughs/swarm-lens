import type { AnalysisRun, DatasetRecord, EpisodeViewModel, InvestigationScope } from "./types";
import { validateEpisode } from "./loadEpisode";

const API_ROOT = `${import.meta.env.BASE_URL}api`;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  const value = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) throw new Error(value?.detail || `Request failed (${response.status}).`);
  return value as T;
}

export async function uploadDataset(file: File): Promise<DatasetRecord> {
  const form = new FormData();
  form.set("adapter_id", "ai_village");
  form.set("bundle", file);
  return requestJson<DatasetRecord>("/datasets", { method: "POST", body: form });
}

export function getDataset(datasetId: string): Promise<DatasetRecord> {
  return requestJson(`/datasets/${encodeURIComponent(datasetId)}`);
}

export async function getScopes(datasetId: string): Promise<InvestigationScope[]> {
  const value = await requestJson<{ scopes: InvestigationScope[] }>(
    `/datasets/${encodeURIComponent(datasetId)}/scopes`,
  );
  return value.scopes;
}

export function createRun(datasetId: string, scopeId: string): Promise<AnalysisRun> {
  return requestJson("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, scope_id: scopeId }),
  });
}

export function getRun(runId: string): Promise<AnalysisRun> {
  return requestJson(`/runs/${encodeURIComponent(runId)}`);
}

export function approveInterpretation(runId: string): Promise<AnalysisRun> {
  return requestJson(`/runs/${encodeURIComponent(runId)}/interpret`, { method: "POST" });
}

export function retryRun(runId: string): Promise<AnalysisRun> {
  return requestJson(`/runs/${encodeURIComponent(runId)}/retry`, { method: "POST" });
}

export async function loadRuntimeEpisode(runId: string): Promise<EpisodeViewModel> {
  const value = await requestJson<unknown>(`/runs/${encodeURIComponent(runId)}/view-model`);
  validateEpisode(value);
  return value;
}
