import { useCallback, useState, type FormEvent } from "react";
import {
  libraryApi,
  type Author,
  type Borrower,
  type LibraryCategory,
  type LibraryCopy,
  type LibraryItem,
  type LibraryLoan,
} from "../api/library";
import { useApi } from "../hooks/useApi";
import { DataTable, PageHeader, StatCard, StatusBadge } from "../components/UI";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import "./library.css";
import "./library-detail.css";
const messageOf = (e: unknown) =>
  e instanceof Error ? e.message : "The request could not be completed.";
function DigitalAction({ item }: { item: LibraryItem }) {
  return item.source_type === "uploaded_file" ? (
    <button className="button" onClick={() => libraryApi.download(item)}>
      Open / Download
    </button>
  ) : item.source_type === "external_url" ? (
    <a
      className="button"
      href={item.external_url ?? "#"}
      target="_blank"
      rel="noreferrer"
    >
      Open External Resource
    </a>
  ) : item.access_type !== "physical" ? (
    <span className="muted">Digital resource unavailable</span>
  ) : null;
}
function ItemDetail({
  item,
  onBack,
  admin = false,
  onManage,
  onIssue,
}: {
  item: LibraryItem;
  onBack: () => void;
  admin?: boolean;
  onManage?: () => void;
  onIssue?: () => void;
}) {
  return (
    <article className="panel">
      <button className="button secondary" onClick={onBack}>
        ← Back to catalogue
      </button>
      <PageHeader title={item.title} subtitle={item.subtitle ?? undefined} />
      <section className="library-detail-section"><h2>Bibliographic Information</h2><dl className="details">
        <div>
          <dt>Authors</dt>
          <dd>{item.authors.join(", ") || "Author not recorded"}</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{item.category_name ?? "Uncategorised"}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{item.item_type.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Access</dt>
          <dd>{item.access_type}</dd>
        </div>
        <div>
          <dt>ISBN</dt>
          <dd>{item.isbn ?? "—"}</dd>
        </div>
        <div>
          <dt>Edition</dt>
          <dd>{item.edition ?? "—"}</dd>
        </div>
        <div>
          <dt>Publisher</dt>
          <dd>{item.publisher ?? "—"}</dd>
        </div>
        <div>
          <dt>Publication year</dt>
          <dd>{item.publication_year ?? "—"}</dd>
        </div>
        <div><dt>Language</dt><dd>{item.language}</dd></div>
      </dl><p>{item.description}</p></section>
      {item.access_type!=="digital"&&<section className="library-detail-section"><h2>Availability</h2><div className="library-availability"><strong>{item.total_copies}<small>Physical copies</small></strong><strong>{item.available_copies}<small>Available</small></strong><strong>{Math.max(0,item.total_copies-item.available_copies)}<small>Borrowed</small></strong></div></section>}
      {item.access_type!=="physical"&&<section className="library-detail-section"><h2>Digital Resource</h2><p>{item.source_type==='uploaded_file'?item.original_filename:'External resource'}</p><DigitalAction item={item}/></section>}
      <div className="page-actions">
        {admin && onManage && item.access_type !== "digital" && (
          <button className="button" onClick={onManage}>
            Manage Physical Copies
          </button>
        )}
        {admin&&onIssue&&item.available_copies>0&&<button className="button primary" onClick={onIssue}>Issue Book</button>}
      </div>
    </article>
  );
}
function ResourceCard({
  item,
  onView,
  label = "View Resource",
}: {
  item: LibraryItem;
  onView: () => void;
  label?: string;
}) {
  return (
    <article className="panel">
      <div className="page-actions">
        <StatusBadge value={item.item_type} />
        <StatusBadge value={item.access_type} />
        {item.access_type !== "digital" && (
          <span>{item.available_copies} available</span>
        )}
      </div>
      <h2>{item.title}</h2>
      <p>{item.authors.join(", ") || "Author not recorded"}</p>
      <small>
        {[item.publisher, item.publication_year, item.category_name]
          .filter(Boolean)
          .join(" · ")}
      </small>
      <p>{item.description}</p>
      <button className="button secondary" onClick={onView}>
        {label}
      </button>
    </article>
  );
}
function Loans({
  rows,
  admin = false,
  onReturn,
}: {
  rows: LibraryLoan[];
  admin?: boolean;
  onReturn?: (id: string) => void;
}) {
  return rows.length ? (
    <DataTable
      rows={rows}
      columns={[
        ...(admin
          ? [{ key: "borrower_name" as keyof LibraryLoan, label: "Borrower" }]
          : []),
        { key: "title", label: "Resource" },
        { key: "accession_number", label: "Accession" },
        {
          key: "borrowed_at",
          label: "Borrowed",
          render: (r) => new Date(r.borrowed_at).toLocaleDateString(),
        },
        {
          key: "due_at",
          label: "Due",
          render: (r) => new Date(r.due_at).toLocaleDateString(),
        },
        {
          key: "returned_at",
          label: "Returned",
          render: (r) =>
            r.returned_at ? new Date(r.returned_at).toLocaleDateString() : "—",
        },
        {
          key: "status",
          label: "Status",
          render: (r) => (
            <StatusBadge value={r.is_overdue ? "Overdue" : r.status} />
          ),
        },
        ...(admin && onReturn
          ? [
              {
                key: "id" as keyof LibraryLoan,
                label: "Action",
                render: (r: LibraryLoan) =>
                  r.returned_at ? (
                    "Returned"
                  ) : (
                    <button
                      className="button secondary"
                      onClick={() => onReturn(r.id)}
                    >
                      Return Book
                    </button>
                  ),
              },
            ]
          : []),
      ]}
    />
  ) : (
    <EmptyState message="No loans in this view." />
  );
}
export function MemberLibraryPage({ role }: { role: "student" | "lecturer" }) {
  const [term, setTerm] = useState(""),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<LibraryItem>();
  const load = useCallback(
    () =>
      role === "student"
        ? libraryApi.studentCatalogue(search)
        : libraryApi.lecturerCatalogue(search),
    [role, search],
  );
  const items = useApi(load, [load]),
    loans = useApi(libraryApi.myLoans);
  if (selected)
    return (
      <section>
        <ItemDetail item={selected} onBack={() => setSelected(undefined)} />
        <section className="panel">
          <h2>My Loans</h2>
          {loans.loading ? (
            <LoadingState />
          ) : loans.error ? (
            <ErrorState error={loans.error} />
          ) : (
            <Loans rows={loans.data ?? []} />
          )}
        </section>
      </section>
    );
  return (
    <section>
      <PageHeader
        title="Library"
        subtitle="Search institution-approved books and digital learning resources."
      />
      <form
        className="search-row"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(term);
        }}
      >
        <label>
          Search catalogue
          <input
            aria-label="Search catalogue"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Title, author, ISBN, category…"
          />
        </label>
        <button className="button">Search</button>
      </form>
      {items.loading ? (
        <LoadingState />
      ) : items.error ? (
        <ErrorState error={items.error} />
      ) : items.data?.length ? (
        <div className="card-grid">
          {items.data.map((x) => (
            <ResourceCard key={x.id} item={x} onView={() => setSelected(x)} />
          ))}
        </div>
      ) : (
        <EmptyState message="No library resources match your search." />
      )}
      <section className="panel">
        <h2>My Loans</h2>
        {loans.loading ? (
          <LoadingState />
        ) : loans.error ? (
          <ErrorState error={loans.error} />
        ) : (
          <Loans rows={loans.data ?? []} />
        )}
      </section>
    </section>
  );
}
type Tab =
  | "overview"
  | "catalogue"
  | "add"
  | "maintenance"
  | "copies"
  | "loans";
export function AdminLibraryPage() {
  const [tab, setTab] = useState<Tab>("overview"),
    [revision, setRevision] = useState(0),
    [selected, setSelected] = useState<LibraryItem>(),
    [access, setAccess] = useState("physical"),
    [source, setSource] = useState("upload"),
    [loanView, setLoanView] = useState("active"),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const refresh = () => setRevision((x) => x + 1);
  const metrics = useApi(libraryApi.metrics, [revision]),
    items = useApi(libraryApi.items, [revision]),
    authors = useApi(libraryApi.authors, [revision]),
    categories = useApi(libraryApi.categories, [revision]);
  const copies = useApi(async () => {
    const eligible = (items.data ?? []).filter(
      (x) => x.access_type !== "digital",
    );
    return (
      await Promise.all(
        eligible.map(async (item) =>
          (await libraryApi.copies(item.id)).map((copy) => ({
            ...copy,
            itemTitle: item.title,
          })),
        ),
      )
    ).flat();
  }, [items.data, revision]);
  const borrowers = useApi(libraryApi.borrowers);
  const loans = useApi(() => libraryApi.loans(loanView), [loanView, revision]);
  async function act(
  action: () => Promise<unknown>,
  success: string,
): Promise<boolean> {
  setError("");
  setNotice("");

  try {
    await action();
    setNotice(success);
    refresh();
    return true;
  } catch (e) {
    setError(messageOf(e));
    return false;
  }
}
  async function addResource(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form),
      author_ids = f.getAll("author_ids").map(String);
    const succeeded = await act(async () => {
      const item = await libraryApi.createItem({
        title: f.get("title"),
        subtitle: f.get("subtitle") || null,
        author_ids,
        category_id: f.get("category_id") || null,
        item_type: f.get("item_type"),
        access_type: access,
        isbn: f.get("isbn") || null,
        edition: f.get("edition") || null,
        publisher: f.get("publisher") || null,
        publication_year: f.get("publication_year")
          ? Number(f.get("publication_year"))
          : null,
        language: f.get("language") || "English",
        description: f.get("description") || null,
        external_url:
          access !== "physical" && source === "external"
            ? f.get("external_url")
            : null,
        status: "active",
      });
      if (access !== "digital" && f.get("accession_number")) {
        try {
          await libraryApi.createCopy(item.id, {
            accession_number: f.get("accession_number"),
            barcode: f.get("barcode") || null,
            shelf_location: f.get("shelf_location") || null,
            acquisition_date: f.get("acquisition_date") || null,
            condition: f.get("condition") || "good",
            status: f.get("copy_status") || "available",
          });
        } catch {
          throw new Error("The catalogue record was created, but the initial physical copy could not be added. Open the resource to retry adding the copy.");
        }
      }
      if (access !== "physical" && source === "upload") {
        const file = f.get("file");
        if (file instanceof File && file.size) {
          try { await libraryApi.upload(item.id, file); }
          catch { throw new Error("The catalogue record was created, but the digital file upload failed. The resource is safe; open it to retry the upload."); }
        }
      }
    }, "Resource created successfully.");

return succeeded;
  }
  const tabs: [Tab, string][] = [
    ["overview", "Library Overview"],
    ["catalogue", "Catalogue"],
    ["add", "Add Resource"],
    ["loans", "Loans"],
    ["maintenance", "Authors & Categories"],
  ];
  if (selected && tab === "catalogue")
    return (
      <section>
        <ItemDetail
          item={selected}
          admin
          onBack={() => setSelected(undefined)}
          onManage={() => {
            setSelected(undefined);
            setTab("copies");
          }}
          onIssue={()=>{setSelected(undefined);setTab("loans")}}
        />
      </section>
    );
  return (
    <section>
      <PageHeader
        title="Library management"
        subtitle="Catalogue, inventory, digital resources and circulation."
      />
      <nav className="tabs" aria-label="Library management sections">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>
      {notice && (
        <p role="status" className="panel">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {tab === "overview" &&
        (metrics.loading ? (
          <LoadingState />
        ) : metrics.error ? (
          <ErrorState error={metrics.error} />
        ) : metrics.data ? (
          <div className="stats">
            <StatCard label="Catalogue" value={metrics.data.total_items} />
            <StatCard
              label="Available copies"
              value={metrics.data.available_copies}
            />
            <StatCard label="Borrowed" value={metrics.data.borrowed_copies} />
            <StatCard label="Overdue" value={metrics.data.overdue_loans} />
            <StatCard label="Digital" value={metrics.data.digital_resources} />
            <StatCard label="Categories" value={metrics.data.categories} />
          </div>
        ) : null)}
      {tab === "catalogue" &&
        (items.loading ? (
          <LoadingState />
        ) : items.data?.length ? (
          <div className="card-grid">
            {items.data.map((x) => (
              <ResourceCard
                key={x.id}
                item={x}
                label="View / Manage"
                onView={() => setSelected(x)}
              />
            ))}
          </div>
        ) : (
          <EmptyState message="No catalogue items." />
        ))}
      {tab === "maintenance" && (
        <div className="library-maintenance">
          <ManagementList
            title="Authors"
            empty="No authors have been added."
            rows={(authors.data ?? []).map((x) => x.display_name)}
            onSubmit={(f) =>
              act(
                () => libraryApi.createAuthor({first_name:f.get("first_name")||null,last_name:f.get("last_name")||null,display_name:f.get("display_name")}),
                "Author added.",
              )
            }
            fields={<><label>Display name<input name="display_name" required /></label><label>First name<input name="first_name" /></label><label>Last name<input name="last_name" /></label></>}
          />
          <ManagementList
            title="Categories"
            empty="No categories have been added."
            rows={(categories.data ?? []).map((x) => x.name)}
            onSubmit={(f) => act(() => libraryApi.createCategory({name:f.get("name"),description:f.get("description")||null,parent_id:f.get("parent_id")||null,is_active:true}),"Category added.")}
            fields={<><label>Category name<input name="name" required /></label><label>Parent category<select name="parent_id"><option value="">None</option>{categories.data?.map((x)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Description<textarea name="description" /></label></>}
          />
        </div>
      )}
      {tab === "add" && (
        <AddResourceForm authors={authors.data??[]} categories={categories.data??[]} access={access} setAccess={setAccess} source={source} setSource={setSource} onSubmit={addResource} onChanged={refresh} />
      )}
      {tab === "copies" && (
        <CopiesPanel
          items={items.data ?? []}
          copies={copies.data ?? []}
          onCreate={(id, f) =>
            act(
              () =>
                libraryApi.createCopy(id, {
                  accession_number: f.get("accession_number"),
                  barcode: f.get("barcode") || null,
                  shelf_location: f.get("shelf_location") || null,
                  acquisition_date: f.get("acquisition_date") || null,
                  condition: f.get("condition"),
                  status: f.get("status"),
                }),
              "Physical copy added.",
            )
          }
        />
      )}{" "}
      {tab === "loans" && (
        <LoansPanel
          view={loanView}
          setView={setLoanView}
          loans={loans.data ?? []}
          copies={copies.data ?? []}
          borrowers={borrowers.data ?? []}
          onIssue={(f) =>
            act(
              () =>
                libraryApi.issue({
                  copy_id: f.get("copy_id"),
                  borrower_user_id: f.get("borrower_user_id"),
                  due_at: f.get("due_at")
                    ? new Date(String(f.get("due_at"))).toISOString()
                    : null,
                }),
              "Loan issued.",
            )
          }
          onReturn={(id) =>
            act(() => libraryApi.returnLoan(id), "Book returned.")
          }
        />
      )}
    </section>
  );
}
function FormSection({title,eyebrow,children}:{title:string;eyebrow:string;children:React.ReactNode}){return <fieldset className="library-form-section"><legend><span>{eyebrow}</span>{title}</legend><div className="library-field-grid">{children}</div></fieldset>}
function AddResourceForm({authors,categories,access,setAccess,source,setSource,onSubmit,onChanged}:{authors:Author[];categories:LibraryCategory[];access:string;setAccess:(x:string)=>void;source:string;setSource:(x:string)=>void;onSubmit:(e:FormEvent<HTMLFormElement>)=>Promise<boolean>;onChanged:()=>void}){
  const [showAuthor,setShowAuthor]=useState(false),[showCategory,setShowCategory]=useState(false),[authorIds,setAuthorIds]=useState<string[]>([]),[categoryId,setCategoryId]=useState(""),[file,setFile]=useState<File>(),[inlineError,setInlineError]=useState(""),[authorDraft,setAuthorDraft]=useState({display_name:"",first_name:"",last_name:""}),[categoryDraft,setCategoryDraft]=useState({name:"",description:"",parent_id:""});
  async function addAuthor(){setInlineError("");try{const created=await libraryApi.createAuthor({display_name:authorDraft.display_name,first_name:authorDraft.first_name||null,last_name:authorDraft.last_name||null}) as Author;setAuthorIds(x=>[...x,created.id]);setShowAuthor(false);setAuthorDraft({display_name:"",first_name:"",last_name:""});onChanged()}catch(error){setInlineError(messageOf(error))}}
  async function addCategory(){setInlineError("");try{const created=await libraryApi.createCategory({name:categoryDraft.name,description:categoryDraft.description||null,parent_id:categoryDraft.parent_id||null,is_active:true}) as LibraryCategory;setCategoryId(created.id);setShowCategory(false);setCategoryDraft({name:"",description:"",parent_id:""});onChanged()}catch(error){setInlineError(messageOf(error))}}
  const accessOptions=[['physical','Physical','Library-held physical copy.'],['digital','Digital','Electronic resource available online.'],['hybrid','Hybrid','Physical and digital formats.']];
  return (
  <form
    className="library-resource-form"
    onSubmit={async (e) => {
  e.preventDefault();

  const form = e.currentTarget;

  const succeeded = await onSubmit(e);

  if (!succeeded) {
    return;
  }

  form.reset();

  setAuthorIds([]);
  setCategoryId("");
  setFile(undefined);

  setShowAuthor(false);
  setShowCategory(false);

  setAuthorDraft({
    display_name: "",
    first_name: "",
    last_name: "",
  });

  setCategoryDraft({
    name: "",
    description: "",
    parent_id: "",
  });

  setInlineError("");

  setAccess("physical");
  setSource("upload");
}}
  >
    <header className="library-form-header"><div><span>New catalogue record</span><h2>Add Resource</h2><p>Create the catalogue record, initial copy and digital access in one workflow.</p></div><strong>Fields marked * are required</strong></header>
    {inlineError&&<p role="alert" className="form-error">{inlineError}</p>}
    <FormSection eyebrow="A" title="Basic Information"><label>Title *<input name="title" required /></label><label>Subtitle<input name="subtitle" /></label><label className="library-full">Description<textarea name="description" rows={4} /></label></FormSection>
    <FormSection eyebrow="B" title="Author & Classification">
      <div className="library-composite"><label>Author(s) *<select aria-label="Authors" name="author_ids" multiple required value={authorIds} onChange={e=>setAuthorIds(Array.from(e.target.selectedOptions,x=>x.value))} size={Math.max(3,Math.min(5,authors.length))}>{authors.map(x=><option key={x.id} value={x.id}>{x.display_name}</option>)}</select></label><button type="button" className="library-inline-action" onClick={()=>setShowAuthor(x=>!x)}>+ Add New Author</button>{authorIds.length>0&&<div className="library-chips" aria-label="Selected authors">{authors.filter(x=>authorIds.includes(x.id)).map(x=><span key={x.id}>{x.display_name}</span>)}</div>}</div>
      <div className="library-composite"><label>Category *<select name="category_id" required value={categoryId} onChange={e=>setCategoryId(e.target.value)}><option value="">Select category</option>{categories.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><button type="button" className="library-inline-action" onClick={()=>setShowCategory(x=>!x)}>+ Add New Category</button></div>
      {showAuthor&&<div className="library-inline-form"><h3>Add a new author</h3><label>Display Name *<input aria-label="New author display name" value={authorDraft.display_name} onChange={e=>setAuthorDraft({...authorDraft,display_name:e.target.value})} required /></label><label>First Name<input value={authorDraft.first_name} onChange={e=>setAuthorDraft({...authorDraft,first_name:e.target.value})} /></label><label>Last Name<input value={authorDraft.last_name} onChange={e=>setAuthorDraft({...authorDraft,last_name:e.target.value})} /></label><div><button type="button" className="button primary" disabled={!authorDraft.display_name} onClick={addAuthor}>Save & Select Author</button><button type="button" className="button secondary" onClick={()=>setShowAuthor(false)}>Cancel</button></div></div>}
      {showCategory&&<div className="library-inline-form"><h3>Add a new category</h3><label>Category Name *<input aria-label="New category name" value={categoryDraft.name} onChange={e=>setCategoryDraft({...categoryDraft,name:e.target.value})} required /></label><label>Parent Category<select value={categoryDraft.parent_id} onChange={e=>setCategoryDraft({...categoryDraft,parent_id:e.target.value})}><option value="">None</option>{categories.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label className="library-full">Description<textarea value={categoryDraft.description} onChange={e=>setCategoryDraft({...categoryDraft,description:e.target.value})} /></label><div><button type="button" className="button primary" disabled={!categoryDraft.name} onClick={addCategory}>Save & Select Category</button><button type="button" className="button secondary" onClick={()=>setShowCategory(false)}>Cancel</button></div></div>}
      <label>Item Type *<select name="item_type" required>{[['book','Book'],['ebook','E-book'],['journal','Journal'],['article','Article'],['thesis','Thesis'],['report','Report'],['lecture_reference','Lecture Reference'],['other','Other']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><label>Language<input name="language" defaultValue="English" /></label>
    </FormSection>
    <FormSection eyebrow="C" title="Publication Details"><label>ISBN<input name="isbn" inputMode="numeric" /></label><label>Edition<input name="edition" /></label><label>Publisher<input name="publisher" /></label><label>Publication Year<input name="publication_year" type="number" min="1000" max="9999" /></label></FormSection>
    <FormSection eyebrow="D" title="Access / Format"><div className="library-access-cards library-full">{accessOptions.map(([value,label,help])=><label key={value} className={access===value?'selected':''}><input type="radio" name="access_type" value={value} checked={access===value} onChange={()=>setAccess(value)} /><strong>{label}</strong><small>{help}</small></label>)}</div></FormSection>
    {access!=="digital"&&<FormSection eyebrow="E" title="Physical Copy Details"><CopyFields/><label>Condition<select name="condition" defaultValue="good"><option>new</option><option>good</option><option>fair</option><option>poor</option><option>damaged</option></select></label><label>Copy Status<select name="copy_status" defaultValue="available"><option>available</option><option>reserved</option><option>damaged</option><option>withdrawn</option></select></label></FormSection>}
    {access!=="physical"&&<FormSection eyebrow="F" title="Digital Resource"><div className="library-source-switch library-full"><label className={source==='upload'?'selected':''}><input type="radio" name="source" checked={source==='upload'} onChange={()=>setSource('upload')} />Upload File</label><label className={source==='external'?'selected':''}><input type="radio" name="source" checked={source==='external'} onChange={()=>setSource('external')} />External Link</label></div>{source==='upload'?<label className="library-full library-file">Select File *<input aria-label="Upload File" name="file" type="file" accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt" required onChange={e=>setFile(e.target.files?.[0])}/><small>PDF, Word, PowerPoint, Excel or text documents.</small>{file&&<strong>{file.name} · {(file.size/1024).toFixed(1)} KB</strong>}</label>:<label className="library-full">HTTPS Resource URL *<input aria-label="External Resource URL" name="external_url" type="url" pattern="https://.*" placeholder="https://…" required/><small>Use a secure, institution-approved destination.</small></label>}</FormSection>}
    <footer className="library-form-footer"><button className="button primary">Create Resource</button><span>The catalogue item, copy and digital source will be created in sequence.</span></footer>
  </form>
  );
}
function ManagementList({
  title,
  empty,
  rows,
  fields,
  onSubmit,
}: {
  title: string;
  empty: string;
  rows: string[];
  fields: React.ReactNode;
  onSubmit: (f: FormData) => void;
}) {
  const singular = title === "Categories" ? "Category" : title.slice(0, -1);
  return (
    <div className="split">
      <form
        className="panel form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(new FormData(e.currentTarget));
          e.currentTarget.reset();
        }}
      >
        <h2>Add {singular}</h2>
        {fields}
        <button className="button">Add {singular}</button>
      </form>
      <section className="panel">
        <h2>{title}</h2>
        {rows.length ? (
          <ul>
            {rows.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        ) : (
          <EmptyState message={empty} />
        )}
      </section>
    </div>
  );
}
function CopyFields() {
  return (
    <>
      <label>
        Accession number
        <input name="accession_number" required />
      </label>
      <label>
        Barcode
        <input name="barcode" />
      </label>
      <label>
        Shelf location
        <input name="shelf_location" />
      </label>
      <label>
        Acquisition date
        <input name="acquisition_date" type="date" />
      </label>
    </>
  );
}
function CopiesPanel({
  items,
  copies,
  onCreate,
}: {
  items: LibraryItem[];
  copies: (LibraryCopy & { itemTitle?: string })[];
  onCreate: (id: string, f: FormData) => void;
}) {
  const physical = items.filter((x) => x.access_type !== "digital");
  return (
    <div className="split">
      <form
        className="panel form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          onCreate(String(f.get("item_id")), f);
          e.currentTarget.reset();
        }}
      >
        <h2>Add Physical Copy</h2>
        <label>
          Resource
          <select name="item_id" required>
            <option value="">Select resource</option>
            {physical.map((x) => (
              <option key={x.id} value={x.id}>
                {x.title}
              </option>
            ))}
          </select>
        </label>
        <CopyFields />
        <label>
          Condition
          <select name="condition">
            {["new", "good", "fair", "poor", "damaged"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select name="status">
            <option>available</option>
            <option>reserved</option>
            <option>damaged</option>
            <option>withdrawn</option>
          </select>
        </label>
        <button className="button">Add Physical Copy</button>
      </form>
      <section className="panel">
        <h2>Copy inventory</h2>
        {copies.length ? (
          <DataTable
            rows={copies}
            columns={[
              { key: "itemTitle", label: "Resource" },
              { key: "accession_number", label: "Accession" },
              { key: "barcode", label: "Barcode" },
              { key: "shelf_location", label: "Shelf" },
              { key: "condition", label: "Condition" },
              {
                key: "status",
                label: "Status",
                render: (r) => <StatusBadge value={r.status} />,
              },
            ]}
          />
        ) : (
          <EmptyState message="No physical copies have been added." />
        )}
      </section>
    </div>
  );
}
function LoansPanel({
  view,
  setView,
  loans,
  copies,
  borrowers,
  onIssue,
  onReturn,
}: {
  view: string;
  setView: (x: string) => void;
  loans: LibraryLoan[];
  copies: (LibraryCopy & { itemTitle?: string })[];
  borrowers: Borrower[];
  onIssue: (f: FormData) => void;
  onReturn: (id: string) => void;
}) {
  const available = copies.filter((x) => x.status === "available");
  return (
    <>
      <form
        className="panel form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          onIssue(new FormData(e.currentTarget));
          e.currentTarget.reset();
        }}
      >
        <h2>Issue Book</h2>
        <label>
          Available copy
          <select name="copy_id" required>
            <option value="">Select copy</option>
            {available.map((x) => (
              <option key={x.id} value={x.id}>
                {x.itemTitle} · {x.accession_number} ·{" "}
                {x.shelf_location ?? "Shelf not set"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Borrower
          <select name="borrower_user_id" required>
            <option value="">Select Student or Lecturer</option>
            {borrowers.map((x) => (
              <option key={x.user_id} value={x.user_id}>
                {x.name} · {x.identity} · {x.role}
              </option>
            ))}
          </select>
        </label>
        <label>
          Due date (optional)
          <input name="due_at" type="datetime-local" />
        </label>
        <button
          className="button"
          disabled={!available.length || !borrowers.length}
        >
          Issue Book
        </button>
      </form>
      <nav className="tabs" aria-label="Loan views">
        {["active", "overdue", "returned"].map((x) => (
          <button
            key={x}
            className={view === x ? "active" : ""}
            onClick={() => setView(x)}
          >
            {x}
          </button>
        ))}
      </nav>
      <section className="panel">
        <h2>{view[0].toUpperCase() + view.slice(1)} Loans</h2>
        <Loans
          rows={loans}
          admin
          onReturn={view === "returned" ? undefined : onReturn}
        />
      </section>
    </>
  );
}
