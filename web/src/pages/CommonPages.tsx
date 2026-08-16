import {Link} from 'react-router-dom';import {portalFor,useAuth} from '../features/auth/AuthContext';
export function UnauthorizedPage(){const {user}=useAuth();return <main className="standalone"><h1>Access restricted</h1><p>Your account does not have permission to view that portal.</p><Link className="button primary" to={user?portalFor(user.roles):'/login'}>Return to your portal</Link></main>}
export function NotFoundPage(){return <main className="standalone"><h1>Page not found</h1><p>The page you requested does not exist.</p><Link to="/">Go home</Link></main>}
