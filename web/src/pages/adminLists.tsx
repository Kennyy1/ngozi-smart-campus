import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/admin";
import { DataTable, PageHeader, StatCard, StatusBadge } from "../components/UI";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useApi } from "../hooks/useApi";
import type {
  AdminCourseOfferingListItem,
  AdminStudentListItem,
} from "../types";
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
export const AdminDashboardPage = () => (
  <AsyncPage title="Institution overview" load={adminApi.dashboard}>
    {(d) => (
      <>
        <div className="context-banner">
          <div>
            <span>Academic context</span>
            <strong>{d.institution_name}</strong>
          </div>
          <dl>
            <div>
              <dt>Session</dt>
              <dd>{d.current_academic_session ?? "Not configured"}</dd>
            </div>
            <div>
              <dt>Semester</dt>
              <dd>{d.current_semester ?? "Not configured"}</dd>
            </div>
          </dl>
        </div>
        <div className="stats primary-stats">
          <StatCard label="Total students" value={d.total_students} />
          <StatCard label="Active students" value={d.active_students} />
          <StatCard label="Lecturers" value={d.total_lecturers} />
          <StatCard label="Programmes" value={d.total_programmes} />
          <StatCard label="Courses" value={d.total_courses} />
          <StatCard
            label="Active offerings"
            value={d.active_course_offerings}
          />
          <StatCard
            label="Registrations"
            value={d.active_course_registrations}
          />
          <StatCard label="Published results" value={d.published_results} />
        </div>
        <div className="quick-grid">
          <article>
            <span className="quick-icon" aria-hidden="true">
              ♙
            </span>
            <div>
              <h3>Student records</h3>
              <p>Select a student to review their consolidated summary.</p>
              <Link className="button primary" to="/admin/students">
                View Students
              </Link>
            </div>
          </article>
          <article>
            <span className="quick-icon" aria-hidden="true">
              ▤
            </span>
            <div>
              <h3>Course offerings</h3>
              <p>Select an offering to review its operational summary.</p>
              <Link className="button secondary" to="/admin/course-offerings">
                View Course Offerings
              </Link>
            </div>
          </article>
        </div>
      </>
    )}
  </AsyncPage>
);
export const AdminStudentsPage = () => (
  <AsyncPage title="Students" load={adminApi.students}>
    {(rows) => (
      <>
        <p className="page-intro">
          Select a student to view their consolidated administrative and
          academic record.
        </p>
        <DataTable<AdminStudentListItem>
          rows={rows}
          columns={[
            { key: "matriculation_number", label: "Matriculation number" },
            {
              key: "first_name",
              label: "Student",
              render: (r) => (
                <strong>
                  {r.first_name} {r.last_name}
                </strong>
              ),
            },
            { key: "programme_name", label: "Programme" },
            { key: "current_level", label: "Level" },
            {
              key: "enrollment_status",
              label: "Status",
              render: (r) => <StatusBadge value={r.enrollment_status} />,
            },
            {
              key: "id",
              label: "Action",
              render: (r) => (
                <Link className="table-action" to={`/admin/students/${r.id}`}>
                  View Summary →
                </Link>
              ),
            },
          ]}
        />
      </>
    )}
  </AsyncPage>
);
export const AdminOfferingsPage = () => (
  <AsyncPage title="Course offerings" load={adminApi.offerings}>
    {(rows) => (
      <>
        <p className="page-intro">
          Select a course offering to review its current operational summary.
        </p>
        <DataTable<AdminCourseOfferingListItem>
          rows={rows}
          columns={[
            { key: "course_code", label: "Code" },
            { key: "course_title", label: "Course" },
            { key: "academic_session", label: "Session" },
            { key: "semester", label: "Semester" },
            { key: "credit_units", label: "Units" },
            {
              key: "status",
              label: "Status",
              render: (r) => <StatusBadge value={r.status} />,
            },
            {
              key: "id",
              label: "Action",
              render: (r) => (
                <Link
                  className="table-action"
                  to={`/admin/course-offerings/${r.id}`}
                >
                  View Summary →
                </Link>
              ),
            },
          ]}
        />
      </>
    )}
  </AsyncPage>
);
