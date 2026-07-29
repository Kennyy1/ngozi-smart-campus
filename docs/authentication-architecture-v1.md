# Authentication and Authorization Architecture v1

## 1. Purpose

This document defines the initial architecture for identity verification, token management, tenant isolation, role-based authorization, and security auditing in the Ngozi Smart Campus platform. It establishes a production-oriented security boundary that is consistent with the platform's multi-tenant conceptual data model while remaining suitable for controlled research evaluation.

Authentication establishes the identity of a user or service. Authorization is the separate process of determining which actions that authenticated identity is permitted to perform. Successful authentication must never be interpreted as unrestricted access.

## 2. Security Principles

- **Tenant isolation by default:** Every institution-owned identity, role assignment, request, and protected resource must be evaluated within an explicit institutional boundary.
- **Least privilege:** Users, services, and administrators receive only the access required for their responsibilities.
- **Deny by default:** Requests are rejected unless an applicable authorization rule explicitly permits them.
- **Short-lived access tokens:** API access credentials have limited validity to reduce the impact of disclosure.
- **Rotating refresh tokens:** Every successful refresh replaces the presented refresh token and invalidates its predecessor.
- **Secure password hashing:** Passwords are protected using a modern, memory-hard, one-way password hashing algorithm.
- **Server-side authorization checks:** The API remains authoritative for access decisions regardless of client behaviour.
- **Auditability of sensitive actions:** Material authentication, authorization, credential, and role-management events produce controlled audit records.
- **Minimal token contents:** Tokens contain only the claims needed for their defined purpose.
- **No plaintext credential storage:** Passwords, refresh tokens, reset tokens, and other secrets are never persisted in plaintext.
- **Revocation support:** Long-lived credentials and sessions can be invalidated following logout, compromise, administrative action, or account-state changes.
- **Defence in depth:** Token validation, current account state, role checks, resource scope, secure storage, rate controls, and audit monitoring operate as complementary safeguards.

## 3. Tenant-Aware Login Identity

Users belong to institutions, and email addresses are unique within an institution rather than globally. The initial login identity therefore consists of:

- `institution_code`
- `email`
- `password`

The `institution_code` identifies the tenant in which the email address must be resolved. Requiring it avoids ambiguous global email lookup, makes the institutional boundary explicit at the start of authentication, and supports the same email address being valid at different institutions.

The login process must:

1. Resolve the institution by `institution_code`.
2. Verify that the institution is active.
3. Find the user using the resolved `institution_id` and normalized email address.
4. Verify that the user is active.
5. Verify the submitted password against `password_hash`.
6. Load the user's assigned roles within the institutional context.
7. Issue the appropriate access and refresh tokens.

Normalization rules for email addresses must be deterministic and consistently applied at account creation and lookup. Authentication failures should use generic responses and comparable processing behaviour so that a client cannot determine whether a particular institution, email address, or account exists.

## 4. Password Security

Passwords must never be stored in plaintext. The `users.password_hash` field stores only a one-way password hash, and Argon2id is the preferred password hashing algorithm. Password hashing and verification must use a trusted, actively maintained security library; unique salts and encoded algorithm parameters should be generated and managed by that library.

Stored hashes should be rehashed following successful verification when approved security parameters change. Application logs and audit logs must never contain passwords. Password reset tokens must likewise not be stored in plaintext; only a cryptographic hash or another purpose-built verification representation may be persisted.

Institution-level password policy should become configurable through `institution_settings` in a later implementation stage. Password strength controls should prioritize sufficient length and resistance to breached-password reuse rather than relying solely on arbitrary character-composition rules. Final numeric password and hashing parameters will be selected through implementation-time security review and performance evaluation.

## 5. Token Architecture

### Access token

An access token is a short-lived, signed credential used for API authorization. It contains a minimal set of validated claims and is not stored in the database in the initial design. Its limited lifetime constrains exposure, while signature and claim validation establish integrity and intended use.

### Refresh token

A refresh token is longer-lived than an access token, revocable, and rotated whenever it is used. The preferred design uses a cryptographically random opaque secret rather than a self-contained JWT. Only a cryptographic hash of the refresh token is stored by the server.

Refresh tokens belong to token families that represent related session history. Reuse of a rotated or revoked token indicates possible credential theft and should invalidate the related token family. Persisting this lifecycle will require a future `refresh_tokens` table and migration; that entity is not part of the current database model.

## 6. Access Token Claims

The proposed minimal access-token claims are:

- `sub`: User identifier.
- `institution_id`: Institutional tenant boundary.
- `roles`: Institution-scoped role names needed for efficient preliminary authorization.
- `type`: Fixed value `access`.
- `jti`: Unique token identifier.
- `iat`: Issuance time.
- `exp`: Expiry time.
- `iss`: Trusted issuer.
- `aud`: Intended audience.

Access tokens must not contain passwords, password hashes, sensitive personal data, or large user profiles. Role claims allow efficient authorization screening, but they can become stale before a token expires. Critical decisions may therefore require current database state, including the active status of the user and institution, current role assignments, resource ownership, or institutional policy.

## 7. Refresh Token Lifecycle

The refresh-token lifecycle is:

1. Issue a refresh token after successful authentication.
2. Return the opaque token to the client over a protected channel.
3. Store only a cryptographic hash of the token.
4. Associate the stored record with the user, institution, token family, expiry time, and appropriate device or session metadata.
5. Rotate the token whenever it is successfully used.
6. Revoke the previous token as part of the same controlled operation.
7. Detect attempted reuse of rotated, expired, or revoked tokens.
8. Revoke the related token family when reuse is detected.
9. Support logout from one session and logout from all sessions.
10. Delete or archive expired token records according to an approved retention policy.

Rotation should be atomic so that concurrent reuse cannot result in multiple valid descendants. Session metadata must be minimized, protected, and retained only for justified security and operational purposes.

## 8. Role-Based Access Control

Initial role-based access control uses the current `roles`, `user_roles`, `users`, and `institutions` entities. The initial role names are:

- `student`
- `lecturer`
- `administrator`
- `librarian`
- `system_super_admin`

Ordinary roles operate within an institution. The `user_roles.institution_id` value must match the user's institutional context, and tenant consistency must be checked whenever assignments are created or evaluated.

The `system_super_admin` role is platform-wide and exceptional. It requires explicit governance, narrowly controlled use, strong auditing, and additional policy checks; it must not imply unrestricted application queries by default.

Possession of a role does not automatically grant access to every record associated with that role. Authorization may additionally depend on ownership, department, faculty, programme, course, or institutional scope. All endpoint authorization must occur on the server. Hiding buttons or navigation options in a client improves usability but does not constitute authorization.

## 9. Permission Evolution

The initial implementation may use named roles and route-level role requirements. As policy complexity increases, the design may evolve to include:

- `permissions`
- `role_permissions`
- Institution-specific custom roles.
- Policy-based authorization.
- Resource ownership checks.
- Department and faculty scope rules.

These entities and mechanisms are deferred and must not be added to the current migration. Their later design should preserve tenant boundaries, support explainable decisions, and avoid incompatible role semantics across institutions.

## 10. Request Authentication Flow

For a protected request, the API must:

1. Receive the bearer access token.
2. Validate its signature using an approved algorithm and trusted key.
3. Validate its issuer and audience.
4. Validate its expiry.
5. Confirm that the token type is `access`.
6. Extract and validate the user and institution identifiers.
7. Locate the current user when the route's risk or policy requires current database state.
8. Verify that the institution and user remain active.
9. Enforce the required role, ownership rule, institutional scope, or other policy.
10. Record sensitive actions and denied access in audit logs where appropriate.

Malformed, expired, incorrectly scoped, or unverifiable tokens must fail closed. Tenant identifiers supplied through paths, query parameters, or request bodies must never override the validated tenant context without an explicitly authorized platform-level workflow.

## 11. API Endpoint Plan

The proposed future authentication endpoints are:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`

Registration will initially be administrator-controlled rather than exposed through public self-registration. This allows institutional identity, role assignment, and enrolment or employment status to be verified before access is granted.

## 12. Error Handling

Client-facing authentication and authorization responses should use controlled categories:

- `invalid credentials`
- `authentication required`
- `token expired`
- `token invalid`
- `permission denied`
- `account unavailable`

Internal logs may contain proportionate diagnostic detail and correlation identifiers, subject to access and retention controls. Client responses and internal records must not expose secrets, password hashes, token values, database errors, or account-enumeration information. Detailed failure reasons should be separated from generic client messages and made available only to authorized operational personnel.

## 13. Audit Events

Important audit actions include:

- `authentication.login_success`
- `authentication.login_failure`
- `authentication.logout`
- `authentication.logout_all`
- `authentication.token_refresh`
- `authentication.refresh_reuse_detected`
- `authentication.password_changed`
- `authentication.password_reset_requested`
- `authentication.password_reset_completed`
- `authorization.access_denied`
- `authorization.role_assigned`
- `authorization.role_removed`

Audit records should capture the institution where applicable, actor, action, affected entity, outcome, timestamp, and a correlation or request reference. Plaintext passwords, access tokens, refresh tokens, password reset tokens, and secrets must never be stored in audit details. Failed-login auditing must also avoid turning audit storage into a repository of sensitive submitted identifiers.

## 14. Client Storage Guidance

For the web application, secure, `HttpOnly`, and appropriate `SameSite` cookies are preferred where the deployment model permits them. Cookie-based authentication must include CSRF protection, secure transport, deliberate domain and path scope, and appropriate expiration. Browser `localStorage` should not hold long-lived secrets because script execution within the origin can expose them.

For Android, refresh credentials should be stored using platform-secure storage backed by operating-system security facilities where available. Access tokens should remain in memory where practical. Secrets must never be placed in logs, screenshots, backups, analytics payloads, crash reports, or ordinary application preferences.

## 15. Threats and Controls

| Threat | Planned controls |
| --- | --- |
| Credential stuffing | Rate controls, breached-password resistance, suspicious-login monitoring, generic failures, and future multifactor authentication. |
| Brute-force login attempts | Per-account and per-source throttling, progressive delays or bounded lockout controls, monitoring, and audited failures without enabling denial-of-service abuse. |
| User enumeration | Tenant-aware lookup, generic responses, controlled timing, and no disclosure of institution or account existence. |
| Token theft | Short access-token lifetime, secure transport and client storage, minimal claims, revocable refresh sessions, and incident-driven token-family revocation. |
| Refresh-token replay | Single-use rotation, hashed persistence, atomic replacement, reuse detection, and token-family invalidation. |
| Privilege escalation | Deny-by-default server policies, validated role assignments, exceptional governance for platform administration, resource-scope checks, and role-change auditing. |
| Cross-tenant access | Trusted `institution_id` context, tenant-scoped queries, same-institution relationship validation, policy tests, and audited denials. |
| Inactive-user access | Active-state checks at login, short-lived access tokens, current-state checks for critical operations, and session revocation. |
| Insecure logging | Structured redaction, prohibited secret fields, restricted log access, retention controls, and tests for sensitive-data leakage. |
| Weak secret management | Dedicated secret-management facilities, controlled key rotation, least-privilege access, no source-code secrets, and no ordinary-setting storage for credentials. |

## 16. Initial Implementation Scope

The first authentication implementation batch comprises:

- Security configuration.
- Argon2id password hashing utility.
- JWT access-token creation and validation.
- Tenant-aware credential verification service.
- Current-user authentication dependency.
- Role-checking dependency.
- Login endpoint.
- `/auth/me` endpoint.
- Tests that do not rely on external services.
- Audit integration where practical.

The following capabilities are explicitly deferred:

- Refresh-token persistence.
- Password reset.
- Email verification.
- Multifactor authentication.
- Single sign-on.
- OAuth federation.
- LDAP integration.
- Custom permissions.
- Biometric authentication.

Deferral does not weaken the controls required for the first batch. In particular, access tokens must remain short-lived, password storage must use Argon2id, authorization must remain server-side, and the architecture must retain a clear path to revocable refresh sessions.

## 17. Future Research and Evaluation Relevance

This architecture supports systematic evaluation of authentication latency from tenant resolution through token issuance, including the performance effects of password hashing parameters. Explicit institutional context and tenant-scoped role assignment enable tests of tenant isolation and authorization correctness across student, lecturer, administrator, and other institutional roles.

Structured audit events support evaluation of traceability, incident reconstruction, and the completeness of security monitoring without retaining prohibited secrets. Short-lived access tokens, future refresh-token rotation, generic error behaviour, and layered policy checks provide measurable controls against credential and token attacks.

The separation of authentication, role-based authorization, resource policy, and client storage also supports usability studies across user groups without conflating interface visibility with actual access control. The architecture can later accommodate biometric verification and intelligent anomaly-detection extensions, provided those capabilities are governed by consent, privacy, explainability, bias evaluation, institutional policy, and human oversight.
