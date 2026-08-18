import {apiUrl,request,session} from './client';
export interface LibraryItem{id:string;title:string;subtitle:string|null;description:string|null;item_type:string;isbn:string|null;edition:string|null;publisher:string|null;publication_year:number|null;language:string;category_name:string|null;cover_image_url:string|null;access_type:string;status:string;source_type:string|null;original_filename:string|null;file_size:number|null;external_url:string|null;authors:string[];available_copies:number;total_copies:number}
export interface LibraryLoan{id:string;title:string;accession_number:string;borrowed_at:string;due_at:string;returned_at:string|null;status:string;is_overdue:boolean;borrower_name?:string|null}
export interface LibraryCategory{id:string;name:string;description:string|null;is_active:boolean}
export interface Author{id:string;display_name:string}
export interface LibraryMetrics{total_items:number;active_physical_copies:number;available_copies:number;borrowed_copies:number;overdue_loans:number;digital_resources:number;categories:number}
export interface LibraryCopy{id:string;library_item_id:string;accession_number:string;barcode:string|null;shelf_location:string|null;acquisition_date:string|null;condition:string;status:string}
export interface Borrower{user_id:string;name:string;identity:string;role:'student'|'lecturer'}
const query=(values:Record<string,string>)=>{const p=new URLSearchParams();Object.entries(values).forEach(([k,v])=>v&&p.set(k,v));return p.size?`?${p}`:''};
export const libraryApi = {
  catalogue: (filters: Record<string, string> = {}) =>
    request<LibraryItem[]>(`/library/catalogue${query(filters)}`),

  studentCatalogue: (q = "") =>
    request<LibraryItem[]>(`/student-portal/library${query({ q })}`),

  lecturerCatalogue: (q = "") =>
    request<LibraryItem[]>(`/lecturer-portal/library${query({ q })}`),

  myLoans: () =>
    request<LibraryLoan[]>("/library/my-loans?view=all"),

  metrics: () =>
    request<LibraryMetrics>("/library/metrics"),

  items: () =>
    request<LibraryItem[]>("/library/items"),

  categories: () =>
    request<LibraryCategory[]>("/library/categories"),

  authors: () =>
    request<Author[]>("/library/authors"),

  copies: (itemId: string) =>
    request<LibraryCopy[]>(`/library/items/${itemId}/copies`),

  loans: (view = "active") =>
    request<LibraryLoan[]>(`/library/loans?view=${view}`),

  createItem: (body: unknown) =>
    request<LibraryItem>("/library/items", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createCopy: (itemId: string, body: unknown) =>
    request<LibraryCopy>(`/library/items/${itemId}/copies`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createCategory: (body: unknown) =>
    request("/library/categories", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createAuthor: (body: unknown) =>
    request("/library/authors", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  upload: (itemId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);

    return request<LibraryItem>(`/library/items/${itemId}/upload`, {
      method: "POST",
      body,
    });
  },

  async borrowers() {
    interface Student {
      user_id: string;
      first_name: string;
      last_name: string;
      matriculation_number: string;
      is_active: boolean;
    }

    interface Lecturer {
      user_id: string;
      first_name: string;
      last_name: string;
      staff_number: string;
      is_active: boolean;
    }

    const [students, lecturers] = await Promise.all([
      request<Student[]>("/students?is_active=true"),
      request<Lecturer[]>("/lecturers?is_active=true"),
    ]);

    return [
      ...students.map((x) => ({
        user_id: x.user_id,
        name: `${x.first_name} ${x.last_name}`,
        identity: x.matriculation_number,
        role: "student" as const,
      })),
      ...lecturers.map((x) => ({
        user_id: x.user_id,
        name: `${x.first_name} ${x.last_name}`,
        identity: x.staff_number,
        role: "lecturer" as const,
      })),
    ];
  },

  issue: (body: unknown) =>
    request("/library/loans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  returnLoan: (id: string) =>
    request(`/library/loans/${id}/return`, {
      method: "POST",
    }),

  async download(item: LibraryItem) {
    const token = session.get();

    const response = await fetch(
      apiUrl(`/library/items/${item.id}/download`),
      {
        headers: token
          ? { Authorization: `Bearer ${token}` }
          : {},
      },
    );

    if (response.status === 401) {
      session.clear();
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (!response.ok) {
      throw new Error("Unable to download this resource.");
    }

    const blob = await response.blob();

    const contentDisposition = response.headers.get("Content-Disposition");

    const filenameMatch = contentDisposition?.match(
      /filename\*?=(?:UTF-8''|")?([^";]+)/i,
    );

    const filename = filenameMatch
      ? decodeURIComponent(filenameMatch[1].replace(/"/g, ""))
      : item.original_filename ?? item.title;

    const url = URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = "none";

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
