import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AdminOfferingPage, AdminStudentPage } from "../pages/admin";
import { EmptyState } from "../components/States";
import { humanize } from "../components/UI";
import { adminApi } from "../api/admin";
vi.mock("../api/admin", () => ({
  adminApi: { student: vi.fn(), offering: vi.fn() },
}));
const studentSummary = {
  student_id: "5ae0e1bb-6998-4d85-a36e-38cff38345ba",
  identity: {
    full_name: "Ada Okafor",
    matriculation_number: "NSC/2025/001",
    email: "ada@example.edu",
  },
  programme: {
    name: "Bachelor of Science in Computing and Informatics",
    code: "BSCI",
  },
  current_level: "400",
  enrollment_status: "active",
  course_registration_count: 8,
  attendance_headline: { total: 10, present: 9 },
  academic_performance: {
    cgpa: "4.20",
    academic_standing: "good_standing",
    cumulative_attempted_units: 80,
    cumulative_earned_units: 76,
    failed_courses: [],
    semester_summaries: [],
  },
  progression: {
    current_level: "400",
    next_level: null,
    cgpa: "4.20",
    academic_standing: "good_standing",
    has_carryover_courses: false,
    eligible_for_progression: false,
    progression_reason: "next_level_not_configured",
  },
  graduation_eligibility: null,
  clearance: null,
  transcript_status: "not_evaluated",
  graduation_status: null,
  document_statuses: {},
};
const offeringSummary = {
  course_offering_id: "off-1",
  course: { code: "CSC401", title: "Distributed Systems" },
  academic_session: { name: "2025/2026" },
  semester: { name: "First Semester" },
  lecturer_assignments: [],
  registered_student_count: 3,
  class_session_count: 4,
  attendance_headline: { total: 10 },
  assessment_component_count: 2,
  examination_count: 1,
  result_status_summary: { published: 2 },
};
describe("Admin summary cleanup", () => {
  it("renders Student response, human values, and deterministic back navigation", async () => {
    vi.mocked(adminApi.student).mockResolvedValue(studentSummary);
    render(
      <MemoryRouter initialEntries={["/admin/students/student-1"]}>
        <Routes>
          <Route
            path="/admin/students/:studentId"
            element={<AdminStudentPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText(
        "Bachelor of Science in Computing and Informatics",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Good Standing").length).toBeGreaterThan(0);
    expect(screen.getByText("Next Level Not Configured")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "← Back to Students" }),
    ).toHaveAttribute("href", "/admin/students");
  });
  it("renders Offering response and deterministic back navigation", async () => {
    vi.mocked(adminApi.offering).mockResolvedValue(offeringSummary);
    render(
      <MemoryRouter initialEntries={["/admin/course-offerings/off-1"]}>
        <Routes>
          <Route
            path="/admin/course-offerings/:courseOfferingId"
            element={<AdminOfferingPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      (await screen.findAllByText("Distributed Systems", { exact: false }))
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: "← Back to Course Offerings" }),
    ).toHaveAttribute("href", "/admin/course-offerings");
  });
  it("formats machine values without changing the source value", () => {
    const source = "enrollment_status_ineligible";
    expect(humanize(source)).toBe("Enrollment Status Ineligible");
    expect(source).toBe("enrollment_status_ineligible");
  });
  it("keeps an empty state readable", () => {
    render(<EmptyState />);
    expect(screen.getByText("Nothing to show")).toBeInTheDocument();
    expect(screen.getByText(/no records are available/i)).toBeInTheDocument();
  });
});
