import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { session } from "../api/client";
import { AuthProvider } from "../features/auth/AuthContext";
const user = (role: string) => ({
  id: "user-hidden",
  institution_id: "institution-hidden",
  institution_code: "NSC",
  email: `${role}@example.edu`,
  first_name: "Library",
  last_name: "User",
  phone: null,
  is_active: true,
  is_verified: true,
  roles: [role],
});
const item = {
  id: "item-raw-uuid",
  title: "Database Systems",
  subtitle: "Campus edition",
  description: "A practical database reference.",
  item_type: "book",
  isbn: "9780000000001",
  edition: "4th",
  publisher: "Campus Press",
  publication_year: 2025,
  language: "English",
  category_id: "category-raw-uuid",
  category_name: "Computer Science",
  cover_image_url: null,
  access_type: "hybrid",
  status: "active",
  source_type: "uploaded_file",
  original_filename: "database.pdf",
  mime_type: "application/pdf",
  file_size: 1000,
  external_url: null,
  authors: ["Ada Scholar"],
  available_copies: 1,
  total_copies: 2,
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
};
const copy = {
  id: "copy-raw-uuid",
  library_item_id: item.id,
  accession_number: "ACC-001",
  barcode: "BC-001",
  shelf_location: "A-12",
  acquisition_date: null,
  condition: "good",
  status: "available",
};
const loan = {
  id: "loan-raw-uuid",
  title: item.title,
  accession_number: copy.accession_number,
  borrower_name: "Grace Student",
  borrowed_at: "2026-08-01T10:00:00Z",
  due_at: "2026-08-15T10:00:00Z",
  returned_at: null,
  status: "active",
  is_overdue: false,
};
const response = (body: unknown) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
function renderLibrary(role: string, path: string) {
  session.set("token");
  const authorRows=[{id:"author-raw-uuid",display_name:"Ada Scholar"}],categoryRows=[{id:"category-raw-uuid",name:"Computer Science",description:null,is_active:true}];
  const fetchMock = vi.fn(
    (input: string | URL | Request, init?: RequestInit) => {
      const url = new URL(
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.href
              : input.url,
        ),
        method = init?.method ?? "GET",
        p = url.pathname;
      if (p === "/api/v1/auth/me") return response(user(role));
      if (p.endsWith("/library/metrics"))
        return response({
          total_items: 1,
          active_physical_copies: 2,
          available_copies: 1,
          borrowed_copies: 1,
          overdue_loans: 0,
          digital_resources: 1,
          categories: 1,
        });
      if (p.endsWith("/library/authors")){if(method==="POST"){const created={id:"author-new",display_name:"New Author"};authorRows.push(created);return response(created)}return response(authorRows)}
      if (p.endsWith("/library/categories")){if(method==="POST"){const created={id:"category-new",name:"New Category",description:null,is_active:true};categoryRows.push(created);return response(created)}return response(categoryRows)}
      if (p === "/api/v1/students")
        return response([
          {
            user_id: "student-raw-uuid",
            first_name: "Grace",
            last_name: "Student",
            matriculation_number: "NSC/2025/001",
            is_active: true,
          },
        ]);
      if (p === "/api/v1/lecturers")
        return response([
          {
            user_id: "lecturer-raw-uuid",
            first_name: "Alan",
            last_name: "Lecturer",
            staff_number: "STAFF-010",
            is_active: true,
          },
        ]);
      if (p.endsWith(`/library/items/${item.id}/copies`))
        return response(method === "POST" ? copy : [copy]);
      if (p.endsWith("/library/loans"))
        return response(method === "POST" ? loan : [loan]);
      if (p.endsWith(`/library/loans/${loan.id}/return`))
        return response({
          ...loan,
          status: "returned",
          returned_at: "2026-08-10T10:00:00Z",
        });
      if (p.endsWith("/library/my-loans")) return response([loan]);
      if (p.endsWith("/library/items"))
        return response(method === "POST" ? item : [item]);
      if (p.includes("/library/items/") && p.endsWith("/upload"))
        return response(item);
      if (p.includes("/library")) return response([item]);
      return response([]);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return {
    fetchMock,
    ...render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    ),
  };
}
beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});
describe("Phase 16 library UI", () => {
  it.each([
    ["student", "/student/library", "Student portal"],
    ["lecturer", "/lecturer/library", "Lecturer portal"],
  ])(
    "gives %s an actionable read-only catalogue and own loans",
    async (role, path, nav) => {
      renderLibrary(role, path);
      expect(
        await screen.findByRole("heading", { name: "Library" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("navigation", { name: nav })).toHaveTextContent(
        "Library",
      );
      expect(
        (await screen.findAllByText("Database Systems")).length,
      ).toBeGreaterThan(0);
      expect(screen.getByText("My Loans")).toBeInTheDocument();
      expect(screen.getByText("ACC-001")).toBeInTheDocument();
      expect(
        screen.queryByText(/Add Physical Copy|Issue Book|Add Resource/),
      ).not.toBeInTheDocument();
      await userEvent.click(
        screen.getByRole("button", { name: "View Resource" }),
      );
      expect(
        screen.getByRole("heading", { name: "Database Systems" }),
      ).toBeInTheDocument();
      expect(screen.getByText("9780000000001")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Open / Download" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Back to catalogue/ }),
      ).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("raw-uuid");
    },
  );
  it("supports Author and Category creation and human-readable selection", async () => {
    renderLibrary("administrator", "/admin/library");
    await screen.findByRole("heading", { name: "Library management" });
    await userEvent.click(screen.getByRole("button", { name: "Authors & Categories" }));
    expect(await screen.findByText("Ada Scholar")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Display name"), "New Author");
    await userEvent.click(screen.getByRole("button", { name: "Add Author" }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/library/authors"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(
      (await screen.findAllByText("Computer Science")).length,
    ).toBeGreaterThan(0);
    await userEvent.type(screen.getByLabelText("Category name"), "New Category");
    await userEvent.selectOptions(
      screen.getByLabelText("Parent category"),
      "Computer Science",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add Category" }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/library/categories"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(document.body).not.toHaveTextContent("raw-uuid");
  });
  it("exposes the structured resource form and conditional digital and physical controls", async () => {
    renderLibrary("administrator", "/admin/library");
    await screen.findByRole("heading", { name: "Library management" });
    await userEvent.click(screen.getByRole("button", { name: "Add Resource" }));
    const form = screen
      .getByRole("heading", { name: "Add Resource" })
      .closest("form")!;
    for (const section of ["Basic Information","Author & Classification","Publication Details","Access / Format","Physical Copy Details"])
      expect(within(form).getByRole("group",{name:new RegExp(section)})).toBeInTheDocument();
    for (const label of [/Title/,"Subtitle","Authors",/Category/,/Item Type/,"ISBN","Edition","Publisher",/Publication Year/,"Language","Description"])
      expect(within(form).getByLabelText(label)).toBeInTheDocument();
    expect(
      within(form).getByRole("option", { name: "Ada Scholar" }),
    ).toBeInTheDocument();
    expect(
      within(form).getByRole("option", { name: "Computer Science" }),
    ).toBeInTheDocument();
    expect(
      within(form).getByRole("group", { name: /Physical Copy Details/ }),
    ).toBeInTheDocument();
    await userEvent.click(within(form).getByRole("radio",{name:/^Digital/}));
    expect(form.querySelector('input[type="file"]')).toHaveAttribute("accept",expect.stringContaining(".pdf"));
    await userEvent.click(within(form).getByLabelText("External Link"));
    expect(
      within(form).getByLabelText("External Resource URL"),
    ).toHaveAttribute("pattern", "https://.*");
    expect(
      within(form).queryByRole("group", { name: /Physical Copy Details/ }),
    ).not.toBeInTheDocument();
  });
  it("creates and automatically selects normalized authors and categories inline",async()=>{renderLibrary("administrator","/admin/library");await screen.findByRole("heading",{name:"Library management"});await userEvent.click(screen.getByRole("button",{name:"Add Resource"}));await userEvent.click(screen.getByRole("button",{name:"+ Add New Author"}));await userEvent.type(screen.getByLabelText("New author display name"),"New Author");await userEvent.click(screen.getByRole("button",{name:"Save & Select Author"}));await waitFor(()=>expect(screen.getByLabelText("Authors")).toHaveValue(["author-new"]));expect(screen.getByLabelText("Selected authors")).toHaveTextContent("New Author");await userEvent.click(screen.getByRole("button",{name:"+ Add New Category"}));await userEvent.type(screen.getByLabelText("New category name"),"New Category");await userEvent.click(screen.getByRole("button",{name:"Save & Select Category"}));await waitFor(()=>expect(screen.getByLabelText(/Category/)).toHaveValue("category-new"));expect(document.body).not.toHaveTextContent("raw-uuid")});
  it("creates physical copies and issues and returns loans using human-readable selectors", async () => {
    renderLibrary("administrator", "/admin/library");
    await screen.findByRole("heading", { name: "Library management" });
    await userEvent.click(screen.getByRole("button", { name: "Catalogue" }));
    await userEvent.click(await screen.findByRole("button", { name: "View / Manage" }));
    await userEvent.click(screen.getByRole("button", { name: "Manage Physical Copies" }));
    expect(
      await screen.findByRole("heading", { name: "Add Physical Copy" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Database Systems" }),
    ).toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByLabelText("Resource"),
      "Database Systems",
    );
    await userEvent.type(screen.getByLabelText("Accession number"), "ACC-002");
    await userEvent.click(
      screen.getByRole("button", { name: "Add Physical Copy" }),
    );
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/copies"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Loans" }));
    expect(
      await screen.findByRole("heading", { name: "Issue Book" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: /Grace Student · NSC\/2025\/001 · student/,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /Database Systems · ACC-001 · A-12/ }),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("student-raw-uuid");
    await userEvent.selectOptions(
      screen.getByLabelText("Available copy"),
      copy.id,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Borrower"),
      "student-raw-uuid",
    );
    await userEvent.click(screen.getByRole("button", { name: "Issue Book" }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/library/loans"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Return Book" }),
    );
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/return"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
  it("opens Admin catalogue detail and preserves availability metadata", async () => {
    renderLibrary("administrator", "/admin/library");
    await screen.findByRole("heading", { name: "Library management" });
    await userEvent.click(screen.getByRole("button", { name: "Catalogue" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "View / Manage" }),
    );
    expect(screen.getByRole("heading",{name:"Availability"})).toBeInTheDocument();
    expect(screen.getByText("Physical copies").parentElement).toHaveTextContent("2");
    expect(screen.getByText("Available").parentElement).toHaveTextContent("1");
    expect(screen.getByText("Borrowed").parentElement).toHaveTextContent("1");
    expect(
      screen.getByRole("button", { name: "Manage Physical Copies" }),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("raw-uuid");
  });
  it("keeps Student out of Admin library management", async () => {
    renderLibrary("student", "/admin/library");
    expect(
      await screen.findByRole("heading", { name: /access restricted/i }),
    ).toBeInTheDocument();
  });
});
