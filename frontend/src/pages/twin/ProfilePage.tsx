import { UserRound } from "lucide-react";
import { useSearchParams } from "react-router";

import { PageHeader } from "@/components/layout/AppShell";
import { TabPanel, Tabs } from "@/components/ui/overlay";
import { useAssessments, useCertifications, useExperiences, useProfile, useProjects, useSkills } from "@/lib/queries";

import { AcademicSection } from "./sections/AcademicSection";
import { AssessmentsSection } from "./sections/AssessmentsSection";
import { CertificationsSection, ExperienceSection, ProjectsSection } from "./sections/EvidenceSections";
import { HistorySection } from "./sections/HistorySection";
import { SkillsSection } from "./sections/SkillsSection";

export function ProfilePage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "academic";
  const profile = useProfile();
  const skills = useSkills();
  const projects = useProjects();
  const experiences = useExperiences();
  const certs = useCertifications();
  const assessments = useAssessments();
  const rated = skills.data?.items.filter((s) => s.status !== "unknown").length;

  return (
    <div>
      <PageHeader icon={UserRound} eyebrow="Digital twin" title="Twin profile"
        description={`Everything TwinPath knows about you, versioned. Current twin version: v${profile.data?.twin_version ?? "—"}.`} />
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })}
        items={[
          { value: "academic", label: "Academic" },
          { value: "skills", label: "Skills", count: rated },
          { value: "projects", label: "Projects", count: projects.data?.length },
          { value: "experience", label: "Experience", count: experiences.data?.length },
          { value: "certifications", label: "Certifications", count: certs.data?.length },
          { value: "assessments", label: "Assessments", count: assessments.data?.results.length },
          { value: "history", label: "History" },
        ]}>
        <div className="pt-6">
          <TabPanel value="academic"><AcademicSection /></TabPanel>
          <TabPanel value="skills"><SkillsSection /></TabPanel>
          <TabPanel value="projects"><ProjectsSection /></TabPanel>
          <TabPanel value="experience"><ExperienceSection /></TabPanel>
          <TabPanel value="certifications"><CertificationsSection /></TabPanel>
          <TabPanel value="assessments"><AssessmentsSection /></TabPanel>
          <TabPanel value="history"><HistorySection /></TabPanel>
        </div>
      </Tabs>
    </div>
  );
}
