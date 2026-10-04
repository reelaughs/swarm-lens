const INTERNAL_STAGE_TERM = /\bstage\s*(?:1|2(?:\.5)?|3|4)\b/gi;

const INVESTIGATOR_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bunder the supplied Stage\s*3 rule\b/gi, "in the available reconstructed evidence"],
  [/\bStage\s*2\.5\b/gi, "evidence brief"],
  [/\bStage\s*1\b/gi, "ingestion / validation"],
  [/\bStage\s*2\b/gi, "turning-point detector"],
  [/\bStage\s*3\b/gi, "evidence reconstruction"],
  [/\bStage\s*4\b/gi, "analyst interpretation"],
];

const INTERNAL_PROVENANCE_KEY = /(stage[1-4]|cache|sha256|fingerprint|request.?identity)/i;

function replaceAll(value: string, replacements: Array<[RegExp, string]>): string {
  return replacements.reduce((current, [pattern, replacement]) => {
    return current.replace(pattern, (_match, offset: number) => {
      const preceding = current.slice(0, offset).trimEnd();
      const startsSentence = preceding.length === 0 || /[.!?]$/.test(preceding);
      return startsSentence
        ? replacement.charAt(0).toUpperCase() + replacement.slice(1)
        : replacement;
    });
  }, value);
}

export function investigatorText(value: string): string {
  return replaceAll(value, INVESTIGATOR_REPLACEMENTS);
}

export function containsInternalStageTerm(value: string): boolean {
  INTERNAL_STAGE_TERM.lastIndex = 0;
  return INTERNAL_STAGE_TERM.test(value);
}

export function evidenceKindLabel(value: unknown): string {
  const kind = String(value ?? "evidence");
  if (kind === "deterministic_stage2_stage3_observation") {
    return "Reconstructed observation";
  }
  if (kind === "provenance_backed_raw_record") {
    return "Source-linked record";
  }
  return investigatorText(kind.replaceAll("_", " "));
}

export function investigatorStructure(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(investigatorStructure);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key
          .replace(/stage2/gi, "detector")
          .replace(/stage3/gi, "reconstruction")
          .replace(/stage4/gi, "interpretation"),
        investigatorStructure(item),
      ]),
    );
  }
  return typeof value === "string" ? investigatorText(value) : value;
}

export function publicProvenance(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(publicProvenance);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !INTERNAL_PROVENANCE_KEY.test(key))
        .map(([key, item]) => [key, publicProvenance(item)]),
    );
  }
  return typeof value === "string" ? investigatorText(value) : value;
}
