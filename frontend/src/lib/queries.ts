import { QueryClient, useQuery } from "@tanstack/react-query";

import { api, ApiError } from "./api";
import type {
  AssessmentDef,
  AssessmentResult,
  CareerRole,
  CatalogueSkill,
  Certification,
  Completeness,
  Experience,
  FeatureRow,
  LatestReadiness,
  Me,
  Profile,
  Project,
  Roadmap,
  RoleGapAnalysis,
  RoleMatchSummary,
  ScaleLevel,
  SkillItem,
} from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => {
        if (error instanceof ApiError && [400, 401, 403, 404, 409, 422].includes(error.status)) return false;
        return count < 2;
      },
    },
  },
});

export const qk = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  skills: ["twin", "skills"] as const,
  completeness: ["twin", "completeness"] as const,
  projects: ["twin", "projects"] as const,
  experiences: ["twin", "experiences"] as const,
  certifications: ["twin", "certifications"] as const,
  assessments: ["twin", "assessments"] as const,
  features: ["twin", "features"] as const,
  snapshots: ["twin", "snapshots"] as const,
  roles: ["roles"] as const,
  catalogueSkills: ["catalogue", "skills"] as const,
  readinessLatest: ["readiness", "latest"] as const,
  readinessModel: ["readiness", "model"] as const,
  readinessHistory: ["readiness", "history"] as const,
  matches: ["gaps", "summary"] as const,
  roleGaps: (roleId: number, cfg: Record<string, number>) => ["gaps", "role", roleId, cfg] as const,
  roadmap: ["roadmap", "active"] as const,
  roadmaps: ["roadmaps"] as const,
  mentorStatus: ["mentor", "status"] as const,
  conversations: ["mentor", "conversations"] as const,
  documents: ["documents"] as const,
  timeline: ["progress", "timeline"] as const,
};

/** Twin-dependent queries to refresh after any profile mutation. */
export function invalidateTwin(): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["twin"] }),
    queryClient.invalidateQueries({ queryKey: qk.profile }),
    queryClient.invalidateQueries({ queryKey: ["gaps"] }),
    queryClient.invalidateQueries({ queryKey: ["roadmap"] }),
    queryClient.invalidateQueries({ queryKey: qk.readinessLatest }),
    queryClient.invalidateQueries({ queryKey: qk.timeline }),
    queryClient.invalidateQueries({ queryKey: ["graph"] }),
  ]).then(() => undefined);
}

export function useMe() {
  return useQuery({
    queryKey: qk.me,
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
}

export const useProfile = () => useQuery({ queryKey: qk.profile, queryFn: () => api<Profile>("/profile") });
export const useSkills = () =>
  useQuery({ queryKey: qk.skills, queryFn: () => api<{ items: SkillItem[]; proficiency_scale: ScaleLevel[] }>("/twin/skills") });
export const useCompleteness = () => useQuery({ queryKey: qk.completeness, queryFn: () => api<Completeness>("/twin/completeness") });
export const useProjects = () => useQuery({ queryKey: qk.projects, queryFn: () => api<Project[]>("/twin/projects") });
export const useExperiences = () => useQuery({ queryKey: qk.experiences, queryFn: () => api<Experience[]>("/twin/experiences") });
export const useCertifications = () => useQuery({ queryKey: qk.certifications, queryFn: () => api<Certification[]>("/twin/certifications") });
export const useAssessments = () =>
  useQuery({ queryKey: qk.assessments, queryFn: () => api<{ results: AssessmentResult[]; catalogue: AssessmentDef[] }>("/twin/assessments") });
export const useFeatures = () => useQuery({ queryKey: qk.features, queryFn: () => api<{ features: FeatureRow[] }>("/twin/features") });
export const useRoles = () =>
  useQuery({
    queryKey: qk.roles,
    queryFn: () => api<{ framework_note: string; proficiency_scale: ScaleLevel[]; roles: CareerRole[] }>("/roles"),
    staleTime: 300_000,
  });
export const useCatalogueSkills = () =>
  useQuery({ queryKey: qk.catalogueSkills, queryFn: () => api<{ skills: CatalogueSkill[] }>("/catalogue/skills"), staleTime: 300_000 });
export const useLatestReadiness = () => useQuery({ queryKey: qk.readinessLatest, queryFn: () => api<LatestReadiness>("/readiness/latest") });
export const useMatches = () =>
  useQuery({
    queryKey: qk.matches,
    queryFn: () => api<{ target_role_id: number | null; matches: RoleMatchSummary[]; disclaimer: string }>("/skill-gaps/summary"),
  });
export const useRoleGaps = (roleId: number | null | undefined, cfg: Record<string, number> = {}) =>
  useQuery({
    queryKey: qk.roleGaps(roleId ?? 0, cfg),
    queryFn: () => api<RoleGapAnalysis>(`/skill-gaps/roles/${roleId}`, { query: cfg }),
    enabled: Boolean(roleId),
    placeholderData: (prev) => prev,
  });
export const useRoadmap = () => useQuery({ queryKey: qk.roadmap, queryFn: () => api<Roadmap | { exists: false }>("/roadmaps/active") });
export const useMentorStatus = () =>
  useQuery({
    queryKey: qk.mentorStatus,
    queryFn: () =>
      api<{ available: boolean; chat_model: string; embed_model: string; runtime: string; queue: Record<string, number | null> }>(
        "/mentor/status",
      ),
    refetchInterval: 30_000,
  });
