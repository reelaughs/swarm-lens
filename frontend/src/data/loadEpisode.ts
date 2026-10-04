import type { EpisodeCatalog, EpisodeCatalogEntry, EpisodeViewModel } from "./types";

const DATA_ROOT = `${import.meta.env.BASE_URL}data/`;
const CATALOG_PATH = `${DATA_ROOT}episodes.json`;
const SAFE_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SAFE_DATA_FILE = /^[a-z0-9]+(?:-[a-z0-9]+)*\.json$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDateTime(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && Number.isFinite(Date.parse(value));
}

function validateCatalogEntry(value: unknown, index: number): asserts value is EpisodeCatalogEntry {
  if (!isRecord(value)) throw new Error(`Catalog episode ${index + 1} is not an object.`);
  if (typeof value.slug !== "string" || !SAFE_SLUG.test(value.slug)) {
    throw new Error(`Catalog episode ${index + 1} has an invalid slug.`);
  }
  if (typeof value.title !== "string" || value.title.length === 0) {
    throw new Error(`Catalog episode ${value.slug} has no title.`);
  }
  if (!isDateTime(value.start) || !isDateTime(value.end) || Date.parse(value.start) >= Date.parse(value.end)) {
    throw new Error(`Catalog episode ${value.slug} has an invalid interval.`);
  }
  if (!Number.isInteger(value.turningPointCount) || Number(value.turningPointCount) < 1) {
    throw new Error(`Catalog episode ${value.slug} has an invalid turning-point count.`);
  }
  if (typeof value.dataFile !== "string" || !SAFE_DATA_FILE.test(value.dataFile)) {
    throw new Error(`Catalog episode ${value.slug} has an unsafe data file.`);
  }
  if (value.status !== undefined) {
    if (!isRecord(value.status) || typeof value.status.id !== "string" || typeof value.status.label !== "string") {
      throw new Error(`Catalog episode ${value.slug} has invalid status metadata.`);
    }
  }
}

export function validateEpisodeCatalog(value: unknown): asserts value is EpisodeCatalog {
  if (!isRecord(value)) throw new Error("Episode catalog is not an object.");
  if (value.catalogVersion !== "1.0") throw new Error("Unsupported episode-catalog version.");
  if (!Array.isArray(value.episodes)) throw new Error("Episode catalog has no episode list.");

  const slugs = new Set<string>();
  value.episodes.forEach((entry, index) => {
    validateCatalogEntry(entry, index);
    if (slugs.has(entry.slug)) throw new Error(`Episode catalog contains duplicate slug ${entry.slug}.`);
    slugs.add(entry.slug);
  });
}

export function validateEpisode(
  value: unknown,
  expected?: EpisodeCatalogEntry,
): asserts value is EpisodeViewModel {
  if (!isRecord(value)) throw new Error("Episode data is not an object.");
  const candidate = value as Partial<EpisodeViewModel>;
  if (candidate.viewModelVersion !== "1.0") throw new Error("Unsupported view-model version.");
  if (!candidate.presentation || typeof candidate.presentation.label !== "string") {
    throw new Error("Episode presentation metadata is invalid.");
  }
  if (!candidate.episode || typeof candidate.episode.slug !== "string") {
    throw new Error("Episode metadata is invalid.");
  }
  if (!Array.isArray(candidate.signalFamilies) || candidate.signalFamilies.length !== 4) {
    throw new Error("Episode detector-family metadata is invalid.");
  }
  if (!Array.isArray(candidate.turningPoints)) throw new Error("Episode turning points are missing.");

  const count = candidate.episode.turningPointCount;
  if (!Number.isInteger(count) || count < 1 || candidate.turningPoints.length !== count) {
    throw new Error("Episode turning-point count is invalid.");
  }
  const ranks = candidate.turningPoints.map((item) => item.rank);
  const ranksAreValid = ranks.every((rank, index) => Number.isInteger(rank) && rank === index + 1);
  if (!ranksAreValid || new Set(ranks).size !== ranks.length) {
    throw new Error("Behavioral-change ranks must be unique, contiguous positive integers in ascending order.");
  }

  if (expected) {
    const mismatches: string[] = [];
    if (candidate.episode.slug !== expected.slug) mismatches.push("slug");
    if (candidate.episode.goalText !== expected.title) mismatches.push("title");
    if (candidate.episode.start !== expected.start) mismatches.push("start timestamp");
    if (candidate.episode.end !== expected.end) mismatches.push("end timestamp");
    if (candidate.episode.turningPointCount !== expected.turningPointCount) mismatches.push("turning-point count");
    if (mismatches.length > 0) {
      throw new Error(`Catalog/view-model mismatch for ${expected.slug}: ${mismatches.join(", ")}.`);
    }
  }
}

async function fetchJson(path: string, label: string): Promise<unknown> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${label} (${response.status}).`);
  return response.json() as Promise<unknown>;
}

export async function loadEpisodeCatalog(): Promise<EpisodeCatalog> {
  const value = await fetchJson(CATALOG_PATH, "episode catalog");
  validateEpisodeCatalog(value);
  return value;
}

export async function loadEpisode(entry: EpisodeCatalogEntry): Promise<EpisodeViewModel> {
  const value = await fetchJson(`${DATA_ROOT}${entry.dataFile}`, `episode ${entry.slug}`);
  validateEpisode(value, entry);
  return value;
}
