export type SignalId = "communication" | "intention" | "participation" | "action_type";
export type Confidence = "low" | "moderate" | "high";
export type InterpretationRole = "best_supported_candidate" | "plausible_alternative";

export interface EpisodeCatalogEntry {
  slug: string;
  title: string;
  start: string;
  end: string;
  turningPointCount: number;
  dataFile: string;
  status?: {
    id: string;
    label: string;
  };
}

export interface EpisodeCatalog {
  catalogVersion: "1.0";
  episodes: EpisodeCatalogEntry[];
}

export interface DistributionChange {
  label: string;
  before: number;
  after: number;
  delta: number;
}

export interface Signal {
  id: SignalId;
  label: string;
  eligible: boolean;
  jensenShannonDivergence: number | null;
  standardizedScore: number | null;
  distributionChanges: DistributionChange[];
}

export interface ActivitySide {
  start: string;
  end: string;
  eventCount: number;
  chatCount: number;
  sessionCount: number;
  highLevelEventCount: number;
  distinctAgents: number;
}

export interface CompactEvidence {
  id: string;
  timestamp: string;
  relation: "before" | "after";
  agentName: string | null;
  agentModel: string | null;
  eventKind: string | null;
  actionType: string | null;
  roomId: string | null;
  text: string | null;
  categories: string[];
  selectionReasons: string[];
  provenance: Record<string, unknown>;
}

export interface RankedPrecedingEvidence {
  rank: number;
  logicalItemId: string;
  timestamp: string;
  minutesBeforeBoundary: number;
  agentId: string | null;
  agentName: string | null;
  sourceType: string | null;
  eventKind: string | null;
  actionType: string | null;
  roomId: string | null;
  text: string | null;
  provenance: Record<string, unknown>;
  scoreComponents: Record<string, number | null>;
  aggregateScore: number | null;
  evidenceLabel: string | null;
  antecedentSupport: string | null;
  antecedentSupportDetails: Record<string, unknown>;
  populationLevelAlignment: Record<string, unknown>;
  uptake: Record<string, unknown>;
  behavioralFollowThrough: Record<string, unknown>;
  persistence: Record<string, unknown>;
}

export interface SupportedSignature {
  signature_id: string;
  rationale: string;
  evidence_ids: string[];
}

export interface EvidenceGroup {
  group_id: string;
  summary: string;
  evidence_ids: string[];
  supported_signature_ids: string[];
  independence_rationale: string;
  relational_evidence: boolean;
}

export interface AlternativeExplanation {
  summary: string;
  evidence_ids: string[];
}

export interface Hypothesis {
  hypothesis_id: string;
  display_name: string;
  interpretation_role: InterpretationRole;
  proposed_confidence: Confidence;
  displayed_confidence: Confidence;
  allowed_confidence_cap: Confidence;
  confidence_cap_reasons: string[];
  summary: string;
  supported_signatures: SupportedSignature[];
  supported_signature_count: number;
  contradicted_counter_signatures: Array<{
    counter_signature_id: string;
    rationale: string;
    evidence_ids: string[];
  }>;
  unknown_signature_ids: string[];
  alternative_explanations: AlternativeExplanation[];
  caveats: string[];
  evidence_groups: EvidenceGroup[];
  independent_evidence_group_count: number;
  evidence_diversity: "low" | "moderate" | "high";
  correlated_evidence_caveat: string | null;
}

export interface SocialProcessEvaluation {
  result: "candidate_hypotheses" | "no_clear_social_process_match";
  rationale: string;
  supporting_evidence_ids: string[];
  hypotheses: Hypothesis[];
  comparative_rationale: null | {
    primary_hypothesis_id: string;
    statement: string;
    evidence_ids: string[];
  };
}

export interface ReferencedEvidence {
  evidenceId: string;
  record: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

export interface TurningPoint {
  rank: number;
  comparisonId: string;
  timestamp: string;
  timelinePositionPercent: number;
  aggregateDetectorScore: number;
  contributingComponents: string[];
  windowSizeReliable: boolean;
  signals: Signal[];
  deterministicDescriptions: string[];
  activity: {
    windowSizeMinutes: number;
    before: ActivitySide;
    after: ActivitySide;
  };
  contextFlags: string[];
  externalContextEvents: unknown[];
  compactEvidence: CompactEvidence[];
  reconstruction: {
    windows: Record<string, unknown>;
    rankedPrecedingEvidence: RankedPrecedingEvidence[];
    persistenceObservations: unknown[];
    structuralObservations: Record<string, unknown>;
    nullFindings: string[];
    caveats: string[];
  };
  interpretation: {
    status: string;
    schemaVersion: string;
    analystNote: { summary: string; supporting_evidence_ids: string[] };
    interpretiveStatements: Array<{
      statement: string;
      supporting_evidence_ids: string[];
      uncertainty: string;
    }>;
    socialProcessEvaluation: SocialProcessEvaluation;
  };
  referencedEvidence: ReferencedEvidence[];
  sourcePaths: Record<string, string>;
}

export interface EpisodeViewModel {
  viewModelVersion: "1.0";
  presentation: {
    label: string;
    scope: string;
    methodologicalGuardrails: string[];
  };
  episode: {
    slug: string;
    goalId: string;
    goalText: string;
    start: string;
    end: string;
    recordCount: number;
    recordCountsByKind: Record<string, number>;
    uniqueAgentCount: number;
    turningPointCount: number;
  };
  signalFamilies: Array<{ id: SignalId; label: string }>;
  turningPoints: TurningPoint[];
  sourceIdentity: Record<string, unknown>;
}
