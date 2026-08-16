export function LoadingState(){return <div className="state" role="status"><span className="spinner" aria-hidden="true"/>Loading…</div>}
export function ErrorState({error}:{error?:Error}){return <div className="state error" role="alert"><strong>Something went wrong</strong><span>{error?.message??'The page could not be loaded.'}</span></div>}
export function EmptyState({message='No records are available yet.'}:{message?:string}){return <div className="state"><strong>Nothing to show</strong><span>{message}</span></div>}
