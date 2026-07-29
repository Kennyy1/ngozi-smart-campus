# Ngozi Smart Campus Conceptual Data Model Version 1

This document defines the first conceptual data model for the Ngozi Smart Campus platform. It describes the principal entities, attributes, relationships, and architectural boundaries for a multi-tenant PostgreSQL deployment. It is an architectural specification rather than an executable database schema; implementation details such as exact PostgreSQL data types, indexes, migrations, and physical partitioning will be refined during later design stages.

## 1. Design Principles

- **Multi-tenancy through `institution_id`:** Institution-owned records carry an `institution_id` that establishes the tenant boundary. Queries and authorization decisions must apply this boundary consistently, while globally shared reference data should be limited to explicitly identified entities.
- **Separation of authentication and user profiles:** The `users` entity stores the common account identity and authentication state. Domain-specific information is held in entities such as `students` and `lecturers`, preventing academic profile concerns from becoming coupled to authentication.
- **Role-based access control:** Roles are assigned through `user_roles`, allowing a user to hold one or more roles within an institution. Authorization should combine role membership, institutional scope, and resource ownership where appropriate.
- **Data integrity through foreign keys and constraints:** Foreign keys preserve valid relationships between entities. Uniqueness, required-value, status, range, and temporal constraints should prevent invalid states at the database boundary.
- **Auditability:** Security-sensitive and material business operations should produce immutable or tightly controlled audit records that identify the actor, action, affected entity, outcome, and time.
- **Scalability:** Stable identifiers, tenant-aware indexing, bounded payloads, efficient relationship tables, and lifecycle policies should support growth in institutions, users, academic records, messages, integrations, and telemetry. High-volume event and log entities may later use partitioning and archival.
- **Middleware interoperability:** Integration entities use service-neutral identifiers, correlation references, request statuses, timestamps, and structured metadata so the platform can exchange data with heterogeneous institutional systems.
- **Protection of institutional data:** Institutional records must be isolated by tenant, governed by least-privilege access, and protected through encryption, retention controls, secure credential handling, and appropriate PostgreSQL access policies. Cross-institution access must be explicitly authorized and auditable.

## 2. Core Identity and Institutional Entities

### institutions

Represents each institution hosted by the platform and serves as the root of the tenant hierarchy.

Major fields:

- `id`: Primary identifier.
- `name`: Official institution name.
- `code`: Short, unique institutional code used in references and integrations.
- `domain`: Verified institutional internet or identity domain.
- `status`: Lifecycle state, such as active, suspended, or archived.
- `created_at`: Record creation timestamp.
- `updated_at`: Most recent modification timestamp.

An institution has many users, academic structures, communications, library records, integrations, audit records, and analytics records. The `code` and, where required by policy, the `domain` should be unique.

### institution_settings

Stores institution-specific configuration so that institutional policies and preferences are not hard-coded in application code.

Major fields:

- `id`: Primary identifier.
- `institution_id`: Owning institution; foreign key to `institutions`.
- `setting_key`: Stable configuration key, unique within the institution.
- `setting_value`: Stored configuration value, validated according to `value_type`.
- `value_type`: Declared value type, which may support string, integer, decimal, boolean, JSON, date, or another validated type.
- `description`: Human-readable explanation of the setting's purpose and expected use.
- `is_public`: Whether the setting may be exposed without privileged authorization.
- `created_at`: Record creation timestamp.
- `updated_at`: Most recent modification timestamp.

Each setting belongs to one institution, and `setting_key` must be unique within that institution. The `setting_value` must be validated according to its declared `value_type`. Sensitive secrets must not be stored as ordinary setting values; they must instead be held in a secure secret-management facility or represented by an encrypted credential reference.

Examples include GPA scale, semester structure, time zone, attendance policy, chatbot access policy, branding preferences, and notification defaults. Institution settings improve configurability and institutional adaptability by allowing each institution to govern supported behaviour without requiring changes to application source code.

### users

Represents the common account and authentication identity for a person using the platform.

Major fields:

- `id`: Primary identifier.
- `institution_id`: Owning institution; foreign key to `institutions`.
- `email`: Login and contact email, unique within the intended tenant scope.
- `password_hash`: One-way password hash; plaintext passwords must never be stored.
- `first_name`: User's given name.
- `last_name`: User's family name.
- `phone`: Optional contact telephone number.
- `is_active`: Whether the account may access the platform.
- `is_verified`: Whether required identity or email verification has been completed.
- `last_login_at`: Timestamp of the latest successful login.
- `created_at`: Record creation timestamp.
- `updated_at`: Most recent modification timestamp.

A user belongs to one institution, has many role assignments, and may have a student profile, lecturer profile, communication records, chatbot conversations, and audit activity. The exceptional `system_super_admin` role requires explicit platform-level governance and must not imply unrestricted application queries by default.

### roles

Defines named authorization roles.

Major fields:

- `id`: Primary identifier.
- `name`: Unique role name.
- `description`: Human-readable purpose and expected permissions.

Supported initial roles are:

- `student`
- `lecturer`
- `administrator`
- `librarian`
- `system_super_admin`

Roles may be global definitions reused by institutions, while their assignment and effective authorization remain institution-scoped.

### user_roles

Associates users with roles and records the tenant context of each assignment.

Major fields:

- `id`: Primary identifier.
- `user_id`: Foreign key to `users`.
- `role_id`: Foreign key to `roles`.
- `institution_id`: Foreign key to `institutions` and explicit tenant boundary.
- `assigned_at`: Timestamp at which the role was assigned.

Each row belongs to one user, one role, and one institution. A uniqueness constraint over `user_id`, `role_id`, and `institution_id` should prevent duplicate assignments. The assigned institution must be consistent with the user's institutional scope, except for carefully governed platform-level administration.

## 3. Academic Entities

### faculties

Represents a high-level academic division within an institution.

Major fields include `id`, `institution_id`, `name`, `code`, `description`, `status`, `created_at`, and `updated_at`. A faculty belongs to one institution and has many departments. Its code should be unique within the institution.

### departments

Represents an academic department within a faculty.

Major fields include `id`, `institution_id`, `faculty_id`, `name`, `code`, `description`, `status`, `created_at`, and `updated_at`. A department belongs to one institution and one faculty, and has many programmes, lecturers, and courses. The referenced faculty must belong to the same institution.

### programmes

Represents a programme of study offered by a department.

Major fields include `id`, `institution_id`, `department_id`, `name`, `code`, `award_type`, `duration_years`, `description`, `status`, `created_at`, and `updated_at`. A programme belongs to one department and has many students. Programme codes should be unique within the appropriate institutional scope.

### academic_sessions

Represents an institutional academic period, normally spanning an academic year.

Major fields include `id`, `institution_id`, `name`, `start_date`, `end_date`, `status`, `is_current`, `created_at`, and `updated_at`. An academic session belongs to one institution and has many semesters and course offerings. Its end date must follow its start date, and no more than one session should normally be current for an institution.

### semesters

Represents a subdivision of an academic session.

Major fields include `id`, `institution_id`, `academic_session_id`, `name`, `sequence_number`, `start_date`, `end_date`, `status`, `created_at`, and `updated_at`. A semester belongs to one academic session and has many course offerings. Its dates should fall within the parent session, and its sequence should be unique within that session.

### academic_calendar_events

Stores institution-specific academic and administrative events.

Major fields:

- `id`: Primary identifier.
- `institution_id`: Owning institution; foreign key to `institutions`.
- `academic_session_id`: Optional academic session associated with the event.
- `semester_id`: Optional semester associated with the event.
- `event_name`: Human-readable name of the event.
- `event_type`: Controlled classification of the event.
- `description`: Optional details about the event.
- `start_at`: Date and time at which the event begins.
- `end_at`: Date and time at which the event ends.
- `target_scope`: Intended audience scope, such as institution-wide, faculty, department, or programme.
- `faculty_id`: Optional targeted faculty.
- `department_id`: Optional targeted department.
- `programme_id`: Optional targeted programme.
- `is_public`: Whether the event may be visible before authentication.
- `status`: Lifecycle or publication state of the event.
- `created_by_user_id`: User who created the event.
- `created_at`: Record creation timestamp.
- `updated_at`: Most recent modification timestamp.

An event belongs to one institution and may optionally belong to an academic session or semester. Event types may include registration, examination, orientation, convocation, holiday, semester break, result publication, and institutional deadline. The `target_scope` determines whether the event is institution-wide or directed to a faculty, department, or programme, and the corresponding target reference should be required only where appropriate.

The `start_at` value must not occur after `end_at`. All referenced academic entities, including any session, semester, faculty, department, or programme, must belong to the same institution as the event. Public events may be visible before authentication, while restricted events require authorization.

### students

Represents the academic profile of a user enrolled as a student.

Major fields include `id`, `institution_id`, `user_id`, `programme_id`, `matriculation_number`, `admission_year`, `current_level`, `enrollment_status`, `graduation_date`, `created_at`, and `updated_at`. A student belongs to one institution, references one user account and one programme, and has many course enrolments and results. The user, programme, and student profile must share the same institutional scope. A matriculation number should be unique within an institution.

### lecturers

Represents the employment and academic profile of a user serving as a lecturer.

Major fields include `id`, `institution_id`, `user_id`, `department_id`, `staff_number`, `academic_title`, `employment_status`, `specialization`, `created_at`, and `updated_at`. A lecturer belongs to one institution and department, references one user account, and may teach many course offerings. The staff number should be unique within an institution.

### courses

Represents the stable catalogue definition of a course.

Major fields include `id`, `institution_id`, `department_id`, `code`, `title`, `description`, `credit_units`, `level`, `status`, `created_at`, and `updated_at`. A course belongs to one institution and normally one owning department. It has many course offerings across sessions and semesters. The course code should be unique within the institution or another explicitly defined catalogue scope.

### course_offerings

Represents a particular delivery of a course during a semester.

Major fields include `id`, `institution_id`, `course_id`, `academic_session_id`, `semester_id`, `lecturer_id`, `programme_id`, `level`, `section`, `capacity`, `status`, `created_at`, and `updated_at`. An offering belongs to one course, session, and semester, may be assigned to a lead lecturer, and has many enrolments and assessments. All referenced records must belong to the same institution, and the semester must belong to the stated session.

### course_enrollments

Represents a student's registration for a course offering.

Major fields include `id`, `institution_id`, `course_offering_id`, `student_id`, `enrolled_at`, `status`, `completion_status`, `created_at`, and `updated_at`. An enrolment belongs to one student and one course offering and may have many results. A student should not have duplicate active enrolments in the same offering.

### assessments

Represents a graded activity within a course offering.

Major fields include `id`, `institution_id`, `course_offering_id`, `title`, `assessment_type`, `maximum_score`, `weight_percentage`, `due_at`, `published_at`, `created_at`, and `updated_at`. An assessment belongs to one course offering and has many results. Maximum scores and weights must be positive, and the combined weighting for an offering should comply with institutional grading policy.

### results

Represents a student's recorded outcome for an assessment or, where explicitly designated, a consolidated course outcome.

Major fields include `id`, `institution_id`, `assessment_id`, `course_enrollment_id`, `student_id`, `score`, `grade`, `grade_points`, `status`, `graded_by_user_id`, `graded_at`, `published_at`, `created_at`, and `updated_at`. A result belongs to an enrolment and normally one assessment, and identifies the affected student and grading actor. The student must match the enrolment, scores must respect the assessment range, and duplicate results for the same assessment and enrolment must be prevented.

## 4. Communication Entities

### announcements

Represents authored information published to a defined institutional audience.

Major fields include `id`, `institution_id`, `author_user_id`, `title`, `body`, `priority`, `status`, `published_at`, `expires_at`, `created_at`, and `updated_at`. Targeting fields may include `target_scope`, `faculty_id`, `department_id`, `programme_id`, `course_offering_id`, and `role_id`.

The `target_scope` identifies institution-wide, faculty, department, programme, course, or role-based distribution. Constraints should require exactly the target reference appropriate to the chosen scope and ensure that the target belongs to the same institution. Multiple-target requirements can later be represented by a dedicated announcement-target association without changing the announcement's authorship model.

### notifications

Represents a platform-generated or user-generated notification and its delivery configuration.

Major fields include `id`, `institution_id`, `announcement_id`, `created_by_user_id`, `notification_type`, `title`, `body`, `delivery_channel`, `priority`, `status`, `scheduled_at`, `sent_at`, `created_at`, and `updated_at`. A notification may originate from an announcement or another platform event and has many recipients.

### notification_recipients

Associates notifications with individual recipients and tracks delivery state.

Major fields include `id`, `institution_id`, `notification_id`, `user_id`, `delivery_status`, `delivered_at`, `read_at`, `failure_reason`, and `created_at`. Each row belongs to one notification and one user. A uniqueness constraint should prevent duplicate recipient entries for the same notification and channel context.

## 5. Library Entities

### library_resources

Represents discoverable physical or digital library material, including books, journals, e-books, research papers, and institutional learning resources.

Major fields include `id`, `institution_id`, `resource_type`, `title`, `authors`, `publisher`, `publication_year`, `isbn_or_identifier`, `description`, `subject`, `language`, `format`, `location_or_url`, `total_copies`, `available_copies`, `access_level`, `status`, `created_at`, and `updated_at`. Physical inventory counts must not be negative, while digital resources may use access rules rather than copy counts.

### library_loans

Represents the lending lifecycle for a physical or controlled resource.

Major fields include `id`, `institution_id`, `library_resource_id`, `borrower_user_id`, `issued_by_user_id`, `borrowed_at`, `due_at`, `returned_at`, `renewal_count`, `status`, `fine_amount`, `created_at`, and `updated_at`. A loan belongs to one resource and borrower. Dates, availability, renewal limits, and loan status should be validated according to institutional policy.

### digital_resource_access_logs

Records auditable access to digital library materials without storing the resource content itself.

Major fields include `id`, `institution_id`, `library_resource_id`, `user_id`, `access_type`, `accessed_at`, `ip_address`, `user_agent`, `outcome`, and `session_reference`. These records support licensing, security, and usage analysis and must follow privacy and retention requirements.

## 6. AI Chatbot Entities

### chatbot_conversations

Represents a user's bounded interaction session with the institutional chatbot.

Major fields include `id`, `institution_id`, `user_id`, `title`, `status`, `started_at`, `last_message_at`, `ended_at`, `created_at`, and `updated_at`. A conversation belongs to one institution and user and has many messages and feedback records.

### chatbot_messages

Represents a message exchanged within a chatbot conversation.

Major fields include `id`, `institution_id`, `conversation_id`, `user_id`, `message_role`, `message_content`, `response_time_ms`, `confidence_score`, `model_or_service_reference`, `created_at`, and `updated_at`. `message_role` distinguishes supported participants such as user, assistant, or system-generated notice. `response_time_ms` is principally applicable to generated responses, and `confidence_score`, where meaningful, should use a constrained and documented range.

Only user-visible or operationally necessary message content may be retained. Private reasoning, hidden chain-of-thought, or other hidden model reasoning must not be stored.

### chatbot_feedback

Captures user evaluation of a chatbot response or conversation.

Major fields include `id`, `institution_id`, `conversation_id`, `message_id`, `user_id`, `feedback_rating`, `feedback_comment`, `created_at`, and `updated_at`. Feedback may reference a specific assistant message and should enforce an agreed rating range. Comments must be governed as potentially sensitive user-generated data.

## 7. Middleware and Integration Entities

The integration layer must support both production adapters and simulated Management Information System (MIS), Learning Management System (LMS), library, website, and communication services used for research and evaluation.

### service_integrations

Defines an institution's configured connection to an external or simulated service.

Major fields include `id`, `institution_id`, `service_type`, `name`, `base_endpoint`, `configuration_metadata`, `credential_reference`, `is_simulated`, `status`, `last_health_check_at`, `created_at`, and `updated_at`. Secrets must be stored in a secure secret facility or encrypted reference rather than exposed in ordinary configuration metadata.

### integration_requests

Records an inbound or outbound integration transaction.

Major fields include `id`, `institution_id`, `service_integration_id`, `direction`, `operation`, `correlation_id`, `external_reference`, `request_metadata`, `response_metadata`, `status`, `http_status`, `started_at`, `completed_at`, and `execution_time_ms`. Payload retention should be minimized or redacted to avoid replicating credentials or sensitive institutional data.

### synchronization_jobs

Represents a scheduled or manually initiated data synchronization process.

Major fields include `id`, `institution_id`, `service_integration_id`, `job_type`, `schedule_reference`, `cursor_or_checkpoint`, `status`, `records_processed`, `records_succeeded`, `records_failed`, `started_at`, `completed_at`, `created_at`, and `updated_at`. Checkpoints enable resumable and incremental synchronization.

### integration_errors

Captures a normalized failure associated with an integration request or synchronization job.

Major fields include `id`, `institution_id`, `service_integration_id`, `integration_request_id`, `synchronization_job_id`, `error_code`, `error_category`, `message`, `redacted_details`, `is_retryable`, `retry_count`, `occurred_at`, and `resolved_at`. Sensitive payloads, credentials, and tokens must not appear in error details.

## 8. Security, Audit and Monitoring Entities

### audit_logs

Provides an authoritative record of material user, administrator, and service actions.

Major fields include `id`, `institution_id`, `actor_user_id`, `actor_type`, `action`, `entity_type`, `entity_id`, `change_summary`, `ip_address`, `user_agent`, `status`, `correlation_id`, and `created_at`. Audit entries should be append-only in normal operation, should redact secrets, and should retain sufficient context to reconstruct who performed an action and what entity was affected.

### login_attempts

Records authentication attempts for security monitoring and abuse prevention.

Major fields include `id`, `institution_id`, `user_id`, `attempted_identifier`, `ip_address`, `user_agent`, `status`, `failure_reason`, `occurred_at`, and `correlation_id`. The attempted identifier should be normalized or protected where appropriate, and retention should be limited to security needs.

### system_events

Represents operational, security, and lifecycle events generated by platform components.

Major fields include `id`, `institution_id`, `source_service`, `event_type`, `severity`, `actor_user_id`, `entity_type`, `entity_id`, `message`, `event_metadata`, `status`, `correlation_id`, and `occurred_at`. Institution may be absent only for genuinely platform-wide events.

### api_request_logs

Records metadata about API activity for diagnostics, security, and performance analysis.

Major fields include `id`, `institution_id`, `actor_user_id`, `request_id`, `http_method`, `route_template`, `status_code`, `ip_address`, `user_agent`, `execution_time_ms`, `response_size_bytes`, and `occurred_at`. Query strings, credentials, authorization headers, and sensitive request or response bodies must not be logged.

## 9. Analytics Entities

### usage_metrics

Stores aggregated measurements over a defined interval.

Major fields include `id`, `institution_id`, `metric_name`, `metric_value`, `unit`, `aggregation_period`, `period_start`, `period_end`, `dimensions`, and `created_at`. Dimensions should use controlled, non-sensitive categories.

### feature_usage_events

Records a minimal event when a platform feature is used.

Major fields include `id`, `institution_id`, `feature_name`, `event_name`, `pseudonymous_actor_reference`, `session_reference`, `context_metadata`, and `occurred_at`. Direct user identification should be omitted unless a justified research or operational purpose requires it.

### performance_metrics

Stores technical measurements used to evaluate system behaviour.

Major fields include `id`, `institution_id`, `service_name`, `operation_name`, `metric_name`, `metric_value`, `unit`, `sample_count`, `percentile`, `status`, and `recorded_at`. Examples include request latency, throughput, error rate, queue depth, and resource utilization.

Analytics records must avoid unnecessary personal data. Collection should apply purpose limitation, data minimization, aggregation or pseudonymization, controlled retention, and institution-specific research governance.

## 10. Key Relationships

- An institution has many users; each tenant-scoped user belongs to an institution.
- An institution has many institution settings; each institution setting belongs to one institution.
- An institution has many academic calendar events; each academic calendar event belongs to one institution.
- An academic session has many academic calendar events; each event may optionally belong to an academic session.
- A semester may have many academic calendar events; each event may optionally belong to a semester.
- An institution has many faculties; each faculty belongs to one institution.
- A faculty has many departments; each department belongs to one faculty.
- A department has many programmes; each programme belongs to one department.
- A programme has many students; each student is associated with one programme at a given point in the initial model.
- A department has many lecturers; each lecturer has a home department in the initial model.
- A course has many course offerings; each offering represents a delivery of one course.
- A course offering has many enrolments; each enrolment associates one student with one offering.
- A user has many roles through `user_roles`; each assignment links one user and one role within an institutional scope.
- A user has many chatbot conversations; each conversation contains many chatbot messages.
- An institution has many service integrations; each integration may have many requests, synchronization jobs, and errors.

All tenant-owned relationships must preserve institutional consistency. A child record must not reference a parent from another institution, even where both identifiers are individually valid.

## 11. Initial Implementation Scope

The first database migration will implement only:

- `institutions`
- `institution_settings`
- `users`
- `roles`
- `user_roles`
- `faculties`
- `departments`
- `students`
- `lecturers`
- `audit_logs`

This scope establishes the tenant boundary, identity and authorization foundation, the initial academic hierarchy, core student and lecturer profiles, and baseline auditability. The remaining entities in this conceptual model will be added incrementally through later migrations as their requirements, constraints, access patterns, privacy rules, and integration contracts are validated.

The `academic_calendar_events` entity will be implemented during the academic module because it depends on academic sessions, semesters, faculties, departments, programmes, and users. It is therefore not included in the first migration.

## 12. Research Relevance

The conceptual model provides a structured basis for evaluating the Ngozi Smart Campus platform as a research artefact:

- **Scalability:** Tenant-scoped ownership, normalized operational entities, event-oriented telemetry, and future partitioning boundaries enable evaluation under increasing institutional, user, and transaction loads.
- **Interoperability:** Service-neutral integration records and support for simulated MIS, LMS, library, website, and communication services permit repeatable assessment of middleware exchanges and failure handling.
- **Security:** Explicit tenant boundaries, role assignments, audit trails, authentication monitoring, and data-minimization rules support evaluation of access control, traceability, and institutional data protection.
- **Usability:** Communication, notification, chatbot, feedback, and feature-usage entities provide evidence for assessing how effectively different user groups interact with platform services.
- **Performance:** API logs, integration timing, response-time fields, usage aggregates, and performance metrics support measurement of latency, throughput, reliability, and resource behaviour.
- **Institutional adaptability:** Configurable academic structures, tenant-specific integrations, flexible targeting, and institution-owned policies allow the model to be evaluated across institutions with different organisational and technological contexts. The `institution_settings` entity allows different universities to define their own policies and configuration without changing application source code.

Together, these characteristics allow functional outcomes and quality attributes to be studied without conflating conceptual design with premature physical implementation.
