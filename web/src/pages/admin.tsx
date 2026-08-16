import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { adminApi } from "../api/admin";
import {
  DisplayValue,
  ObjectDetails,
  PageHeader,
  StatusBadge,
  humanize,
} from "../components/UI";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useApi } from "../hooks/useApi";
export {
  AdminDashboardPage,
  AdminOfferingsPage,
  AdminStudentsPage,
} from "./adminLists";

type Rec = Record<string, unknown>;
const rec = (value: unknown): Rec =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Rec)
    : {};
const array = (value: unknown): Rec[] =>
  Array.isArray(value)
    ? (value.filter(
        (item) => typeof item === "object" && item !== null,
      ) as Rec[])
    : [];
function AsyncPage<T>({
  title,
  load,
  children,
}: {
  title: string;
  load: () => Promise<T>;
  children: (data: T) => ReactNode;
}) {
  const { data, error, loading } = useApi(load);
  return (
    <section>
      <PageHeader title={title} />
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : data !== undefined ? (
        children(data)
      ) : (
        <EmptyState />
      )}
    </section>
  );
}
function SummaryCard({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={`panel summary-card ${className}`}>
      <h2>{title}</h2>
      {children}
    </article>
  );
}
function FieldGrid({ fields }: { fields: [string, unknown][] }) {
  return (
    <dl className="field-grid">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <DisplayValue value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
function SemesterSummaries({ value }: { value: unknown }) {
  const semesters = array(value);
  if (!semesters.length)
    return <EmptyState message="No semester summaries are available." />;
  return (
    <div className="semester-grid">
      {semesters.map((item, index) => (
        <article key={String(item.semester_id ?? index)}>
          <header>
            <span>Semester {index + 1}</span>
            <strong>Academic performance</strong>
          </header>
          <FieldGrid
            fields={[
              ["Attempted units", item.attempted_units],
              ["Earned units", item.earned_units],
              ["GPA", item.gpa],
              ["Total quality points", item.total_quality_points],
              ["Passed courses", item.passed_courses],
              ["Failed courses", item.failed_courses],
            ]}
          />
          <div className="identifier-row">
            <span>Session ID</span>
            <DisplayValue value={item.academic_session_id} subtle />
            <span>Semester ID</span>
            <DisplayValue value={item.semester_id} subtle />
          </div>
        </article>
      ))}
    </div>
  );
}
function Progression({ value }: { value: unknown }) {
  const item = rec(value);
  if (!Object.keys(item).length)
    return <EmptyState message="No progression evaluation is available." />;
  return (
    <FieldGrid
      fields={[
        ["Current level", item.current_level],
        ["Next level", item.next_level],
        ["CGPA", item.cgpa],
        ["Academic standing", item.academic_standing],
        ["Carryover courses", item.has_carryover_courses],
        ["Eligible for progression", item.eligible_for_progression],
        ["Progression reason", item.progression_reason],
      ]}
    />
  );
}
function DetailNavigation({ kind }: { kind: "student" | "offering" }) {
  const student = kind === "student";
  const parent = student ? "Students" : "Course Offerings";
  const destination = student ? "/admin/students" : "/admin/course-offerings";
  return (
    <div className="detail-navigation">
      <nav aria-label="Breadcrumb">
        <Link to="/admin/dashboard">Admin</Link>
        <span aria-hidden="true">/</span>
        <Link to={destination}>{parent}</Link>
        <span aria-hidden="true">/</span>
        <span>{student ? "Student Summary" : "Offering Summary"}</span>
      </nav>
      <Link className="back-link" to={destination}>
        ← Back to {parent}
      </Link>
    </div>
  );
}
function Graduation({ value, status }: { value: unknown; status: unknown }) {
  const item = rec(value);
  if (!Object.keys(item).length && !status)
    return <EmptyState message="No graduation evaluation is available." />;
  const reasons = Array.isArray(item.eligibility_reasons)
    ? item.eligibility_reasons.map(String).map(humanize).join(", ")
    : item.eligibility_reasons;
  return (
    <FieldGrid
      fields={[
        ["Status", status],
        ["Eligible for graduation", item.eligible_for_graduation],
        ["Programme", item.programme_name],
        ["Programme code", item.programme_code],
        ["Current level", item.current_level],
        ["Final level", item.final_level],
        ["CGPA", item.cgpa],
        ["Academic standing", item.academic_standing],
        ["Credit requirement configured", item.credit_requirement_configured],
        ["Meets credit requirement", item.meets_credit_requirement],
        ["Curriculum completion verified", item.curriculum_completion_verified],
        ["Has published results", item.has_published_results],
        ["Eligibility reasons", reasons],
      ]}
    />
  );
}
function Clearance({ value }: { value: unknown }) {
  const item = rec(value);
  if (!Object.keys(item).length)
    return <EmptyState message="No clearance summary is available." />;
  const requirements = array(item.requirements);
  return (
    <>
      <FieldGrid
        fields={[
          ["Fully cleared", item.is_fully_cleared],
          ["Total requirements", item.total_active_requirements],
          ["Mandatory", item.mandatory_requirements],
          ["Optional", item.optional_requirements],
          ["Cleared", item.cleared_count],
          ["Pending", item.pending_count],
          ["Rejected", item.rejected_count],
          ["Missing", item.missing_count],
        ]}
      />
      {requirements.length ? (
        <div className="clearance-grid">
          {requirements.map((requirement, index) => (
            <article
              key={String(requirement.clearance_requirement_id ?? index)}
            >
              <h3>{String(requirement.name ?? "Clearance requirement")}</h3>
              <FieldGrid
                fields={[
                  ["Code", requirement.code],
                  ["Mandatory", requirement.is_mandatory],
                  ["Status", requirement.status],
                  ["Remarks", requirement.remarks],
                  ["Evidence reference", requirement.evidence_reference],
                  ["Reviewed at", requirement.reviewed_at],
                ]}
              />
            </article>
          ))}
        </div>
      ) : (
        <EmptyState message="No clearance requirements are available." />
      )}
    </>
  );
}

export const AdminStudentPage = () => {
  const { studentId = "" } = useParams();
  return (
    <AsyncPage title="Student summary" load={() => adminApi.student(studentId)}>
      {(d) => {
        const performance = rec(d.academic_performance),
          identity = rec(d.identity),
          programme = rec(d.programme);
        const fallback =
          `${identity.first_name ?? ""} ${identity.last_name ?? ""}`.trim();
        const name = String(identity.full_name ?? (fallback || "Student"));
        return (
          <>
            <DetailNavigation kind="student" />
            <div className="summary-identity">
              <div>
                <span>Student record</span>
                <h2>{name}</h2>
                <p>
                  {String(
                    identity.matriculation_number ??
                      "Matriculation number unavailable",
                  )}
                </p>
              </div>
              <div className="summary-status">
                <StatusBadge value={d.enrollment_status} />
                <span className="subtle-value">Record ID: {d.student_id}</span>
              </div>
            </div>
            <div className="detail-grid">
              <SummaryCard title="Student profile">
                <FieldGrid
                  fields={[
                    ["Full name", identity.full_name],
                    ["Matriculation number", identity.matriculation_number],
                    ["Email", identity.email],
                  ]}
                />
              </SummaryCard>
              <SummaryCard title="Programme & enrollment">
                <FieldGrid
                  fields={[
                    ["Programme", programme.name],
                    ["Programme code", programme.code],
                    ["Current level", d.current_level],
                    ["Enrollment status", d.enrollment_status],
                    ["Course registrations", d.course_registration_count],
                  ]}
                />
              </SummaryCard>
              <SummaryCard title="Academic performance" className="span-2">
                <FieldGrid
                  fields={[
                    ["CGPA", performance.cgpa],
                    ["Academic standing", performance.academic_standing],
                    ["Attempted units", performance.cumulative_attempted_units],
                    ["Earned units", performance.cumulative_earned_units],
                    [
                      "Failed courses",
                      array(performance.failed_courses).length,
                    ],
                  ]}
                />
              </SummaryCard>
              <SummaryCard title="Semester summaries" className="span-full">
                <SemesterSummaries value={performance.semester_summaries} />
              </SummaryCard>
              <SummaryCard title="Progression" className="span-2">
                <Progression value={d.progression} />
              </SummaryCard>
              <SummaryCard title="Attendance">
                <FieldGrid
                  fields={Object.entries(rec(d.attendance_headline)).map(
                    ([key, value]) => [humanize(key), value],
                  )}
                />
              </SummaryCard>
              <SummaryCard title="Graduation" className="span-full">
                <Graduation
                  value={d.graduation_eligibility}
                  status={d.graduation_status}
                />
              </SummaryCard>
              <SummaryCard title="Clearance" className="span-full">
                <Clearance value={d.clearance} />
              </SummaryCard>
              <SummaryCard title="Documents & transcript">
                <FieldGrid
                  fields={[
                    ["Transcript status", d.transcript_status],
                    ...Object.entries(d.document_statuses).map(
                      ([key, value]): [string, unknown] => [
                        `${humanize(key)} documents`,
                        value,
                      ],
                    ),
                  ]}
                />
              </SummaryCard>
            </div>
          </>
        );
      }}
    </AsyncPage>
  );
};

export const AdminOfferingPage = () => {
  const { courseOfferingId = "" } = useParams();
  return (
    <AsyncPage
      title="Course offering summary"
      load={() => adminApi.offering(courseOfferingId)}
    >
      {(d) => (
        <>
          <DetailNavigation kind="offering" />
          <div className="summary-identity">
            <div>
              <span>Course offering</span>
              <h2>
                {String(d.course.code ?? "")} {String(d.course.title ?? "")}
              </h2>
              <p>
                {String(d.academic_session.name ?? "Session unavailable")} ·{" "}
                {String(d.semester.name ?? "Semester unavailable")}
              </p>
            </div>
            <span className="subtle-value">
              Offering ID: {d.course_offering_id}
            </span>
          </div>
          <div className="detail-grid">
            <SummaryCard title="Course">
              <ObjectDetails value={d.course} hideIds />
            </SummaryCard>
            <SummaryCard title="Academic period">
              <FieldGrid
                fields={[
                  ["Academic session", d.academic_session.name],
                  ["Semester", d.semester.name],
                ]}
              />
            </SummaryCard>
            <SummaryCard title="Operations" className="span-2">
              <FieldGrid
                fields={[
                  ["Registered students", d.registered_student_count],
                  ["Class sessions", d.class_session_count],
                  ["Assessment components", d.assessment_component_count],
                  ["Examinations", d.examination_count],
                ]}
              />
            </SummaryCard>
            <SummaryCard title="Attendance">
              <FieldGrid
                fields={Object.entries(d.attendance_headline).map(
                  ([key, value]) => [humanize(key), value],
                )}
              />
            </SummaryCard>
            <SummaryCard title="Results">
              <FieldGrid
                fields={Object.entries(d.result_status_summary).map(
                  ([key, value]) => [humanize(key), value],
                )}
              />
            </SummaryCard>
            <SummaryCard title="Lecturer assignments" className="span-full">
              <ObjectDetails value={d.lecturer_assignments} hideIds />
            </SummaryCard>
          </div>
        </>
      )}
    </AsyncPage>
  );
};
