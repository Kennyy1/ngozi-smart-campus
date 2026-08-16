export type Role =
  "student" | "lecturer" | "guardian" | "administrator" | "system_super_admin";
export interface AuthenticatedUser {
  id: string;
  institution_id: string;
  institution_code: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  is_active: boolean;
  is_verified: boolean;
  roles: string[];
}
export interface LoginRequest {
  institution_code: string;
  email: string;
  password: string;
}
export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}
export interface StudentProfile {
  student_id: string;
  matriculation_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string | null;
  programme_id: string | null;
  programme_name: string | null;
  programme_code: string | null;
  current_level: string | null;
  admission_year: number;
  enrollment_status: string;
}
export interface StudentDashboard extends StudentProfile {
  current_academic_session: string | null;
  current_semester: string | null;
  registered_course_count: number;
  active_course_count: number;
  attendance_summary: Record<string, unknown>;
  current_gpa: string | null;
  cgpa: string | null;
  academic_standing: string | null;
  progression_summary: unknown;
  clearance_summary: unknown;
  graduation_summary: unknown;
}
export interface StudentCourse {
  course_registration_id: string;
  course_offering_id: string;
  course_id: string;
  course_code: string;
  title: string;
  credit_units: number;
  course_type: string;
  semester_id: string;
  semester: string;
  academic_session_id: string;
  academic_session: string;
  registration_status: string;
}
export interface StudentAttendanceSummary {
  course_offering_id: string;
  course_code: string;
  course_title: string;
  total_sessions: number;
  present_count: number;
  absent_count: number;
  late_count: number;
  attendance_percentage: string;
}
export interface StudentResult {
  result_id: string;
  course_offering_id: string;
  course_code: string;
  course_title: string;
  academic_session_id: string;
  academic_session: string;
  semester_id: string;
  semester: string;
  credit_units: number;
  final_score: string;
  grade: string;
  grade_point: string;
  passed: boolean;
}
export interface AcademicPerformance {
  current_gpa: string | null;
  cgpa: string;
  cumulative_attempted_units: number;
  cumulative_earned_units: number;
  academic_standing: string;
  progression_summary: unknown;
  failed_courses: Record<string, unknown>[];
}
export interface TranscriptCourse {
  result_id: string;
  course_code: string;
  course_title: string;
  credit_units: number;
  final_score: string;
  grade_letter: string;
  grade_point: string;
  passed: boolean;
}
export interface TranscriptSemester {
  semester_id: string;
  semester_name: string;
  gpa: string;
  attempted_units: number;
  earned_units: number;
  courses: TranscriptCourse[];
}
export interface TranscriptSession {
  academic_session_id: string;
  academic_session_name: string;
  semesters: TranscriptSemester[];
}
export interface StudentTranscript {
  student_id: string;
  matriculation_number: string;
  student_name: string;
  programme_name: string;
  programme_code: string;
  cgpa: string;
  academic_standing: string;
  academic_sessions: TranscriptSession[];
}
export interface ClearanceItem {
  clearance_requirement_id: string;
  name: string;
  code: string;
  is_mandatory: boolean;
  status: string;
  remarks: string | null;
}
export interface StudentClearance {
  student_id: string;
  matriculation_number: string;
  student_name: string;
  is_fully_cleared: boolean;
  pending_count: number;
  requirements: ClearanceItem[];
}
export interface StudentDocument {
  document_id: string;
  type: string;
  reference: string;
  status: string;
  issued_at: string | null;
  verification_code: string;
}
export interface GuardianChild {student_id:string;matriculation_number:string;student_name:string;programme_name:string|null;current_level:string|null;enrollment_status:string;relationship_type:string;is_primary:boolean;can_view_results:boolean;can_view_attendance:boolean;can_view_academic_performance:boolean;can_view_transcript:boolean;can_view_clearance:boolean}
export interface GuardianDashboard {guardian_id:string;guardian_name:string;child_count:number;children:GuardianChild[]}
export interface ChildOverview {child:GuardianChild;result_count:number|null;attendance_percentage:string|null;current_gpa:string|null;cgpa:string|null;academic_standing:string|null;clearance:{is_fully_cleared:boolean;pending_count:number}|null}
export interface LecturerDashboard {
  lecturer_id: string;
  staff_number: string;
  name: string;
  department: string;
  employment_status: string;
  active_course_assignment_count: number;
  current_course_offering_count: number;
  upcoming_class_session_count: number;
  total_registered_students: number;
  pending_assessment_component_count: number;
  completed_examination_count: number;
}
export interface LecturerCourse {
  lecturer_assignment_id: string;
  course_offering_id: string;
  course_code: string;
  course_title: string;
  credit_units: number;
  academic_session: string;
  semester: string;
  status: string;
  registered_student_count: number;
}
export interface LecturerCourseStudent {
  course_registration_id: string;
  student_id: string;
  matriculation_number: string;
  student_name: string;
  current_level: string | null;
  registration_status: string;
}
export interface LecturerAttendance extends LecturerCourseStudent {
  total_sessions: number;
  present_count: number;
  absent_count: number;
  late_count: number;
  attendance_percentage: string;
}
export interface LecturerAssessment {
  component_id: string;
  title: string;
  type: string;
  maximum_score: string;
  weight: string;
  status: string;
  scheduled_date: string | null;
  due_date: string | null;
  registered_student_count: number;
  scored_student_count: number;
  unscored_student_count: number;
}
export interface LecturerExamination {
  examination_id: string;
  title: string;
  type: string;
  maximum_score: string;
  weight: string;
  examination_date: string;
  start_time: string;
  end_time: string;
  status: string;
  registered_student_count: number;
  scored_student_count: number;
  unscored_student_count: number;
}
export interface LecturerResult {
  result_id: string;
  student_id: string;
  matriculation_number: string;
  student_name: string;
  final_score: string;
  grade: string;
  grade_point: string;
  passed: boolean;
}
export interface LecturerResultOverview {
  course_offering_id: string;
  registered_student_count: number;
  published_result_count: number;
  missing_published_result_count: number;
  results: LecturerResult[];
}
export interface AdminDashboard {
  institution_id: string;
  institution_name: string;
  total_students: number;
  active_students: number;
  graduated_students: number;
  total_lecturers: number;
  active_lecturers: number;
  total_programmes: number;
  total_courses: number;
  current_academic_session: string | null;
  current_semester: string | null;
  active_course_offerings: number;
  active_course_registrations: number;
  published_results: number;
  pending_result_approvals: number;
  graduation_eligible_students: number | null;
  confirmed_graduations: number;
  issued_transcripts: number;
  issued_certificates: number;
  pending_mandatory_clearances: number;
}
export interface AdminStudentSummary {
  student_id: string;
  identity: Record<string, unknown>;
  programme: Record<string, unknown> | null;
  current_level: string | null;
  enrollment_status: string;
  course_registration_count: number;
  attendance_headline: Record<string, unknown>;
  academic_performance: unknown;
  progression: unknown;
  graduation_eligibility: unknown;
  clearance: unknown;
  transcript_status: string | null;
  graduation_status: string | null;
  document_statuses: Record<string, number>;
}
export interface AdminCourseOfferingSummary {
  course_offering_id: string;
  course: Record<string, unknown>;
  academic_session: Record<string, unknown>;
  semester: Record<string, unknown>;
  lecturer_assignments: Record<string, unknown>[];
  registered_student_count: number;
  class_session_count: number;
  attendance_headline: Record<string, unknown>;
  assessment_component_count: number;
  examination_count: number;
  result_status_summary: Record<string, number>;
}
export interface AdminStudentListItem {
  id: string;
  matriculation_number: string;
  first_name: string;
  last_name: string;
  programme_id: string;
  programme_name: string;
  current_level: string | null;
  enrollment_status: string;
}
export interface AdminCourseOfferingListItem {
  id: string;
  course_code: string;
  course_title: string;
  academic_session: string;
  semester: string;
  credit_units: number | null;
  status: string;
  registration_open: boolean;
}
