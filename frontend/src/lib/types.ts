export type Role = "student" | "mentor" | "admin";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
}

export interface Me {
  user: User;
  csrf_token: string | null;
  onboarding_completed: boolean;
  email_verification_required: boolean;
}

export interface LoginResult {
  status: "authenticated" | "mfa_required";
  mfa_challenge: string | null;
  me: Me | null;
}

export interface Profile {
  degree: string | null;
  specialization: string | null;
  current_semester: number | null;
  graduation_year: number | null;
  cgpa: number | null;
  attendance_pct: number | null;
  academic_achievements: string;
  headline: string;
  career_interests: string[];
  learning_preferences: string[];
  weekly_hours: number;
  target_role_id: number | null;
  preferred_role_ids: number[];
  twin_version: number;
  onboarding_completed_at: string | null;
  attendance_consent: boolean;
}

export interface Signal {
  status: string;
  level: number;
  source: string;
  title?: string;
  assessment?: string;
  pct?: number;
  verification?: string;
  hypothetical?: boolean;
}

export interface SkillItem {
  skill_id: number;
  slug: string;
  name: string;
  category: string;
  kind: string;
  description: string;
  self_rating: number | null;
  estimated_level: number | null;
  status: string;
  trust: number;
  signals: Signal[];
}

export interface ScaleLevel {
  level: number;
  name: string;
  description: string;
}

export interface Requirement {
  skill_id: number;
  skill_slug: string;
  skill_name: string;
  category: string;
  required_level: number;
  importance: number;
  is_core: boolean;
  evidence_expected: string;
  alt_group: string | null;
  rationale: string;
}

export interface CareerRole {
  id: number;
  slug: string;
  name: string;
  summary: string;
  description: string;
  version: number;
  source_note: string;
  requirements: Requirement[];
}

export interface CatalogueSkill {
  id: number;
  slug: string;
  name: string;
  category: string;
  kind: string;
  description: string;
  prerequisites: { skill_id: number; min_level: number }[];
}

export interface EvidenceLink {
  id: string;
  skill_id: number;
  level_demonstrated: number;
  note: string;
}

export type Verification = "unverified" | "pending" | "verified" | "rejected";

export interface Project {
  id: string;
  title: string;
  summary: string;
  technologies: string[];
  repo_url: string | null;
  demo_url: string | null;
  is_deployed: boolean;
  team_size: number | null;
  started_on: string | null;
  completed_on: string | null;
  verification_status: Verification;
  skills: EvidenceLink[];
  created_at: string;
}

export interface Experience {
  id: string;
  kind: string;
  organization: string;
  title: string;
  description: string;
  start_date: string;
  end_date: string | null;
  outcome: string | null;
  verification_status: Verification;
  skills: EvidenceLink[];
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  issued_on: string | null;
  expires_on: string | null;
  credential_url: string | null;
  verification_status: Verification;
  skills: EvidenceLink[];
}

export interface AssessmentResult {
  id: string;
  assessment_id: number;
  assessment_name: string;
  kind: string;
  score: number;
  max_score: number;
  pct: number;
  taken_on: string;
  source: string;
  verification_status: Verification;
  notes: string;
}

export interface AssessmentDef {
  id: number;
  slug: string;
  name: string;
  kind: string;
  max_score: number;
  description: string;
  skills: string[];
}

export interface Completeness {
  overall: number;
  sections: { key: string; label: string; weight: number; score: number; complete: boolean; hint: string | null }[];
  known_skills: number;
  rated_skills: number;
  verified_assessments: number;
}

export interface Resource {
  id: number;
  title: string;
  provider: string;
  url: string;
  verification_status: string;
  est_hours?: [number, number];
  level?: [number, number];
  cost: string;
}

export interface Gap {
  skill_id: number;
  skill_slug: string;
  skill_name: string;
  category: string;
  required_level: number;
  estimated_level: number | null;
  status: string;
  trust: number;
  gap: number | null;
  coverage: number | null;
  importance: number;
  weight: number;
  is_core: boolean;
  evidence_expected: string;
  evidence_met: boolean;
  alt_group: string | null;
  alternatives: string[];
  prerequisites: { skill_id: number; skill_name: string; min_level: number; estimated_level: number | null; met: boolean }[];
  blocking_count: number;
  unlock_count: number;
  priority: number;
  action: string;
  action_text: string;
  rationale: string;
  hypothetical: boolean;
  resources?: Resource[];
}

export interface RoleGapAnalysis {
  config: Record<string, number>;
  role_id: number;
  role_slug: string;
  role_name: string;
  role_version: number;
  match: number;
  match_upper: number;
  known_share: number;
  evidence_strength: number | null;
  met_count: number;
  gap_count: number;
  unknown_count: number;
  gaps: Gap[];
  disclaimer: string;
}

export interface RoleMatchSummary {
  role_id: number;
  role_slug: string;
  role_name: string;
  role_version: number;
  match: number;
  match_upper: number;
  known_share: number;
  evidence_strength: number | null;
  met_count: number;
  gap_count: number;
  unknown_count: number;
  top_gaps: { skill: string; action: string; gap: number | null; priority: number }[];
}

export interface Contribution {
  feature: string;
  label: string;
  value: number | null;
  display_value: string;
  is_missing: boolean;
  contribution: number;
  direction: "raises" | "lowers" | "neutral";
}

export interface Warning {
  code: string;
  message: string;
  feature?: string;
}

export interface ReadinessResult {
  available: boolean;
  reason?: string;
  message?: string;
  model_version?: string;
  is_synthetic_model?: boolean;
  target_definition?: string;
  band?: string;
  band_label?: string;
  probability?: { value: number; rounding: string; test_ece: number } | null;
  calibrated_score?: number | null;
  calibration_validated?: boolean;
  known_input_share?: number;
  explanation?: { output_space: string; base_value: number; contributions: Contribution[]; top: Contribution[] };
  summary?: string;
  warnings?: Warning[];
  limitations?: string[];
  prediction_id?: string;
  snapshot_version?: number;
  created_at?: string;
}

export interface LatestReadiness {
  exists: boolean;
  prediction_id?: string;
  created_at?: string;
  band?: string;
  probability?: number | null;
  explanation?: { output_space: string; base_value: number; contributions: Contribution[]; summary: string };
  warnings?: Warning[];
  model_version?: string | null;
  is_synthetic_model?: boolean | null;
  snapshot_version?: number | null;
  stale?: boolean;
  model: { available: boolean; version: string | null; reason_unavailable: string | null };
}

export interface FeatureRow {
  name: string;
  label: string;
  value: number | null;
  unit: string;
  min: number;
  max: number;
  description: string;
}

export interface RoadmapItem {
  id: string;
  position: number;
  skill_id: number;
  skill_name: string;
  category: string | null;
  action: string;
  priority_score: number;
  reason: string;
  current_level: number | null;
  target_level: number;
  effort_hours: [number, number];
  prerequisites: string[];
  resource: (Resource & { est_hours: [number, number] }) | null;
  exercise: string;
  completion_criteria: string;
  status: "not_started" | "in_progress" | "completed" | "skipped";
  week_start: number;
  week_end: number;
  user_edited: boolean;
  note: string;
  completed_at: string | null;
}

export interface Roadmap {
  exists?: boolean;
  id: string;
  status: string;
  role_id: number;
  role_name: string | null;
  role_version: number;
  hours_per_week: number;
  generator_version: string;
  created_at: string;
  previous_roadmap_id: string | null;
  params: Record<string, unknown>;
  progress: { completed: number; total: number; share: number };
  stale: boolean;
  stale_reasons: string[];
  items: RoadmapItem[];
  weeks: { week: number; item_ids: string[] }[];
  months: { month: number; weeks: number[] }[];
  disclaimer: string;
  comparison_with_previous?: RoadmapComparison;
  warnings?: string[];
}

export interface RoadmapComparison {
  added: { skill: string; action: string }[];
  removed: { skill: string; action: string }[];
  moved: { skill: string; action: string; from: number; to: number }[];
  carried_progress: { skill: string; status: string }[];
}

export interface GraphNode {
  id: string;
  type: "student" | "skill" | "role" | "resource" | "assessment" | "project";
  label: string;
  position: [number, number, number];
  category?: string;
  kind?: string;
  level?: number | null;
  status?: string;
  required_level?: number;
  action?: string;
  priority?: number;
  url?: string;
  verification?: string;
  provider?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  provenance: "framework" | "evidence" | "self_reported" | "inferred";
  level?: number;
  min_level?: number;
  importance?: number;
  status?: string;
  because?: string;
}

export interface GraphPayload {
  role_id: number | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  counts: { nodes: number; edges: number };
  legend: { provenance: Record<string, string> };
}

export interface MentorSource {
  ref: string;
  title: string;
  section: string;
  scope: string;
  relevance: number;
  excerpt: string;
}

export interface DocumentItem {
  id: string;
  kind: "resume" | "job_description" | "knowledge";
  title: string;
  original_filename: string | null;
  mime_type: string;
  size_bytes: number;
  status: string;
  error: string | null;
  chunk_count: number;
  injection_flags: number;
  confirmed_at: string | null;
  retention_until: string | null;
  created_at: string;
  extracted: {
    skills?: { skill_id: number; name: string; category: string; matched: string[]; count: number; sections: string[]; weight?: number }[];
    suggestions?: { code: string; message: string }[];
    sections?: Record<string, number>;
    project_candidates?: string[];
    warnings?: string[];
    word_count?: number;
    note?: string;
  };
}

export interface Paged<T> {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
}
