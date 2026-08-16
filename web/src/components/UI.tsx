import type { ReactNode } from "react";
import { EmptyState } from "./States";
export function humanize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
export function DisplayValue({
  value,
  subtle = false,
}: {
  value: unknown;
  subtle?: boolean;
}) {
  if (value === null || value === undefined || value === "")
    return <span className="muted-value">Not available</span>;
  if (typeof value === "boolean") return <StatusBadge value={value} />;
  if (typeof value === "string") {
    const isIdentifier =
      /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value) ||
      /^https?:\/\//i.test(value) ||
      (!value.includes(" ") && value.length > 32);
    return (
      <span
        className={`${isIdentifier ? "identifier-value" : "text-value"}${subtle ? " subtle-value" : ""}`}
      >
        {value.includes("_") ? humanize(value) : value}
      </span>
    );
  }
  return <span>{String(value)}</span>;
}
export const PageHeader = ({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) => (
  <header className="page-header">
    <div>
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  </header>
);
export const StatCard = ({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) => (
  <article className="stat-card">
    <span>{label}</span>
    <strong>{value ?? "—"}</strong>
  </article>
);
export const StatusBadge = ({ value }: { value: string | boolean }) => {
  const raw = typeof value === "boolean" ? (value ? "yes" : "no") : value;
  return (
    <span className={`badge badge-${raw.toLowerCase().replace(/\s/g, "-")}`}>
      {humanize(raw)}
    </span>
  );
};
export function DataTable<T extends object>({
  rows,
  columns,
  empty = "No records found.",
}: {
  rows: T[];
  columns: { key: keyof T; label: string; render?: (row: T) => ReactNode }[];
  empty?: string;
}) {
  if (!rows.length) return <EmptyState message={empty} />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={String(c.key)} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={String(
                ("id" in row && row.id) ||
                  ("result_id" in row && row.result_id) ||
                  ("course_offering_id" in row && row.course_offering_id) ||
                  index,
              )}
            >
              {columns.map((c) => (
                <td key={String(c.key)}>
                  {c.render ? (
                    c.render(row)
                  ) : (
                    <DisplayValue value={row[c.key]} />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function ObjectDetails({
  value,
  hideIds = false,
}: {
  value: unknown;
  hideIds?: boolean;
}) {
  if (value === null || value === undefined) return <EmptyState />;
  if (typeof value !== "object") return <DisplayValue value={value} />;
  if (Array.isArray(value))
    return value.length ? (
      <div className="detail-list">
        {value.map((item, i) => (
          <ObjectDetails key={i} value={item} hideIds={hideIds} />
        ))}
      </div>
    ) : (
      <EmptyState />
    );
  const entries = Object.entries(value as Record<string, unknown>).filter(
    ([key]) =>
      !hideIds ||
      (key !== "id" && !key.endsWith("_id") && !key.endsWith("_ids")),
  );
  if (!entries.length) return <EmptyState />;
  return (
    <dl className="details">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{humanize(key)}</dt>
          <dd>
            {typeof item === "object" && item !== null ? (
              <ObjectDetails value={item} hideIds={hideIds} />
            ) : (
              <DisplayValue value={item} />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
