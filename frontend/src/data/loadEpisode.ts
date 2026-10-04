import type { EpisodeViewModel } from "./types";

const DATA_PATH = `${import.meta.env.BASE_URL}data/perform-novel-research.json`;

export function validateEpisode(value: unknown): asserts value is EpisodeViewModel {
  if (!value || typeof value !== "object") throw new Error("Episode data is not an object.");
  const candidate = value as Partial<EpisodeViewModel>;
  if (candidate.viewModelVersion !== "1.0") throw new Error("Unsupported view-model version.");
  if (candidate.episode?.slug !== "perform-novel-research") throw new Error("Unexpected episode data.");
  const ranks = candidate.turningPoints?.map((item) => item.rank).join(",");
  if (ranks !== "1,2,3,4,5") throw new Error("Frozen Stage 2 rank order is invalid.");
}

export async function loadEpisode(): Promise<EpisodeViewModel> {
  const response = await fetch(DATA_PATH);
  if (!response.ok) throw new Error(`Could not load episode data (${response.status}).`);
  const value: unknown = await response.json();
  validateEpisode(value);
  return value;
}
