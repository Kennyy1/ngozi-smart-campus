import { Link, useParams } from "react-router-dom";
import { lecturerApi } from "../api/lecturer";
import { DataTable, PageHeader, StatCard, StatusBadge } from "../components/UI";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useApi } from "../hooks/useApi";
import type {
  LecturerAssessment,
  LecturerAttendance,
  LecturerCourse,
  LecturerCourseStudent,
  LecturerExamination,
  LecturerResult,
} from "../types";
function AsyncPage<T>({
  title,
  load,
  children,
}: {
  title: string;
  load: () => Promise<T>;
  children: (data: T) => React.ReactNode;
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
export const LecturerDashboardPage = () => (
  <AsyncPage title="Dashboard" load={lecturerApi.dashboard}>
    {(d) => (
      <>
        <p className="welcome">
          Welcome, {d.name}. Your current teaching overview is below.
        </p>
        <div className="stats">
          <StatCard label="Department" value={d.department} />
          <StatCard
            label="Active assignments"
            value={d.active_course_assignment_count}
          />
          <StatCard
            label="Current offerings"
            value={d.current_course_offering_count}
          />
          <StatCard
            label="Upcoming sessions"
            value={d.upcoming_class_session_count}
          />
          <StatCard
            label="Registered students"
            value={d.total_registered_students}
          />
          <StatCard
            label="Pending assessments"
            value={d.pending_assessment_component_count}
          />
          <StatCard
            label="Completed examinations"
            value={d.completed_examination_count}
          />
        </div>
      </>
    )}
  </AsyncPage>
);
export const LecturerCoursesPage = () => (
  <AsyncPage title="Course offerings" load={lecturerApi.courses}>
    {(rows) => (
      <DataTable<LecturerCourse>
        rows={rows}
        columns={[
          { key: "course_code", label: "Code" },
          { key: "course_title", label: "Course" },
          { key: "academic_session", label: "Session" },
          { key: "semester", label: "Semester" },
          { key: "registered_student_count", label: "Students" },
          {
            key: "status",
            label: "Status",
            render: (r) => <StatusBadge value={r.status} />,
          },
          {
            key: "course_offering_id",
            label: "Open",
            render: (r) => (
              <Link
                to={`/lecturer/course-offerings/${r.course_offering_id}/students`}
              >
                View offering
              </Link>
            ),
          },
        ]}
      />
    )}
  </AsyncPage>
);
const offeringNav = (id: string) => (
  <nav className="tabs" aria-label="Course offering sections">
    {["students", "attendance", "assessments", "examinations", "results"].map(
      (section) => (
        <Link key={section} to={`/lecturer/course-offerings/${id}/${section}`}>
          {section}
        </Link>
      ),
    )}
  </nav>
);
function useOffering() {
  const { id } = useParams();
  return id ?? "";
}
export const CourseStudentsPage = () => {
  const id = useOffering();
  return (
    <AsyncPage title="Course students" load={() => lecturerApi.students(id)}>
      {(rows) => (
        <>
          {offeringNav(id)}
          <DataTable<LecturerCourseStudent>
            rows={rows}
            columns={[
              { key: "matriculation_number", label: "Matric number" },
              { key: "student_name", label: "Student" },
              { key: "current_level", label: "Level" },
              { key: "registration_status", label: "Status" },
            ]}
          />
        </>
      )}
    </AsyncPage>
  );
};
export const CourseAttendancePage = () => {
  const id = useOffering();
  return (
    <AsyncPage
      title="Course attendance"
      load={() => lecturerApi.attendance(id)}
    >
      {(rows) => (
        <>
          {offeringNav(id)}
          <DataTable<LecturerAttendance>
            rows={rows}
            columns={[
              { key: "matriculation_number", label: "Matric number" },
              { key: "student_name", label: "Student" },
              { key: "total_sessions", label: "Sessions" },
              { key: "present_count", label: "Present" },
              { key: "absent_count", label: "Absent" },
              { key: "late_count", label: "Late" },
              {
                key: "attendance_percentage",
                label: "Attendance",
                render: (r) => `${r.attendance_percentage}%`,
              },
            ]}
          />
        </>
      )}
    </AsyncPage>
  );
};
export const CourseAssessmentsPage = () => {
  const id = useOffering();
  return (
    <AsyncPage title="Assessments" load={() => lecturerApi.assessments(id)}>
      {(rows) => (
        <>
          {offeringNav(id)}
          <DataTable<LecturerAssessment>
            rows={rows}
            columns={[
              { key: "title", label: "Component" },
              { key: "type", label: "Type" },
              { key: "maximum_score", label: "Maximum" },
              { key: "weight", label: "Weight" },
              { key: "status", label: "Status" },
              { key: "scored_student_count", label: "Scored" },
              { key: "unscored_student_count", label: "Unscored" },
            ]}
          />
        </>
      )}
    </AsyncPage>
  );
};
export const CourseExaminationsPage = () => {
  const id = useOffering();
  return (
    <AsyncPage title="Examinations" load={() => lecturerApi.examinations(id)}>
      {(rows) => (
        <>
          {offeringNav(id)}
          <DataTable<LecturerExamination>
            rows={rows}
            columns={[
              { key: "title", label: "Examination" },
              { key: "type", label: "Type" },
              { key: "examination_date", label: "Date" },
              { key: "maximum_score", label: "Maximum" },
              { key: "weight", label: "Weight" },
              { key: "status", label: "Status" },
              { key: "scored_student_count", label: "Scored" },
              { key: "unscored_student_count", label: "Unscored" },
            ]}
          />
        </>
      )}
    </AsyncPage>
  );
};
export const CourseResultsPage = () => {
  const id = useOffering();
  return (
    <AsyncPage title="Results overview" load={() => lecturerApi.results(id)}>
      {(d) => (
        <>
          {offeringNav(id)}
          <div className="stats">
            <StatCard
              label="Registered students"
              value={d.registered_student_count}
            />
            <StatCard
              label="Published results"
              value={d.published_result_count}
            />
            <StatCard
              label="Missing results"
              value={d.missing_published_result_count}
            />
          </div>
          <DataTable<LecturerResult>
            rows={d.results}
            empty="No official results are available."
            columns={[
              { key: "student_name", label: "Student name" },
              { key: "matriculation_number", label: "Matriculation number" },
              { key: "final_score", label: "Final score" },
              { key: "grade", label: "Grade" },
              { key: "grade_point", label: "Grade point" },
              {
                key: "passed",
                label: "Pass status",
                render: (result) => (
                  <StatusBadge value={result.passed ? "passed" : "failed"} />
                ),
              },
            ]}
          />
        </>
      )}
    </AsyncPage>
  );
};
