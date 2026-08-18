import {render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,describe,expect,it,vi} from 'vitest';

import App from '../App';
import {session} from '../api/client';
import {AuthProvider} from '../features/auth/AuthContext';

const identity=(role:string)=>({id:`${role}-user`,institution_id:'institution-1',institution_code:'NSC',email:`${role}@example.edu`,first_name:'Portal',last_name:'User',phone:null,is_active:true,is_verified:true,roles:[role]});
const response=(body:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));

function mockApi(role:string){
  vi.stubGlobal('fetch',vi.fn((input:string|URL|Request)=>{
    const path=new URL(String(input)).pathname;
    if(path==='/api/v1/auth/me')return response(identity(role));
    if(path==='/api/v1/lecturer-portal/courses')return response([]);
    if(path.endsWith('/announcements')||path.endsWith('/timetable')||path==='/api/v1/notifications')return response([]);
    return response({detail:'Not found'},404);
  }));
}

function renderRoute(path:string,role?:string){
  if(role){session.set('valid-token');mockApi(role)}
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App/></AuthProvider></MemoryRouter>);
}

beforeEach(()=>sessionStorage.clear());

describe('Phase 15 authenticated portal routing',()=>{
  it('keeps a protected deep link pending until authentication restoration completes',async()=>{
    session.set('persisted-token');
    let restoreIdentity:(value:Response)=>void=()=>undefined;
    const pendingIdentity=new Promise<Response>(resolve=>{restoreIdentity=resolve});
    vi.stubGlobal('fetch',vi.fn((input:string|URL|Request)=>{
      const path=new URL(String(input)).pathname;
      if(path==='/api/v1/auth/me')return pendingIdentity;
      if(path==='/api/v1/student-portal/announcements')return response([]);
      return response({detail:'Not found'},404);
    }));

    render(<MemoryRouter initialEntries={['/student/announcements']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByRole('heading',{name:/welcome back/i})).not.toBeInTheDocument();
    restoreIdentity(await response(identity('student')));
    expect(await screen.findByRole('heading',{name:'Announcements'})).toBeInTheDocument();
  });

  it('restores the token and identity after an application remount',async()=>{
    session.set('persisted-token');
    mockApi('student');
    const first=render(<MemoryRouter initialEntries={['/student/announcements']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole('heading',{name:'Announcements'})).toBeInTheDocument();
    first.unmount();
    render(<MemoryRouter initialEntries={['/student/announcements']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole('heading',{name:'Announcements'})).toBeInTheDocument();
    const meCalls=vi.mocked(fetch).mock.calls.filter(([input])=>String(input).includes('/api/v1/auth/me'));
    expect(meCalls).toHaveLength(2);
    expect(session.get()).toBe('persisted-token');
    expect(sessionStorage).toHaveLength(1);
    expect(sessionStorage.getItem('ngozi_access_token')).toBe('persisted-token');
  });

  it.each([
    ['/student/announcements','Announcements','/api/v1/student-portal/announcements'],
    ['/student/timetable','Timetable','/api/v1/student-portal/timetable'],
    ['/student/notifications','Notifications','/api/v1/notifications'],
  ])('restores a Student session for direct entry to %s',async(path,heading,endpoint)=>{
    renderRoute(path,'student');
    expect(await screen.findByRole('heading',{name:heading})).toBeInTheDocument();
    expect(screen.getByRole('navigation',{name:'Student portal'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/log out/i})).toBeInTheDocument();
    expect(session.get()).toBe('valid-token');
    await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining(endpoint),expect.objectContaining({headers:expect.any(Headers)})));
    const requestCall=vi.mocked(fetch).mock.calls.find(([input])=>String(input).includes(endpoint));
    expect((requestCall?.[1]?.headers as Headers).get('Authorization')).toBe('Bearer valid-token');
  });

  it('redirects an unauthenticated communication route to Login',async()=>{
    renderRoute('/student/announcements');
    expect(await screen.findByRole('heading',{name:/welcome back/i})).toBeInTheDocument();
  });

  it('clears an invalid restored token and redirects the deep link to Login',async()=>{
    session.set('expired-token');
    vi.stubGlobal('fetch',vi.fn(()=>response({detail:'Token expired'},401)));
    render(<MemoryRouter initialEntries={['/student/notifications']}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole('heading',{name:/welcome back/i})).toBeInTheDocument();
    expect(session.get()).toBeNull();
  });

  it.each([
    ['lecturer','/student/announcements'],
    ['student','/lecturer/announcements'],
    ['student','/guardian/announcements'],
    ['guardian','/admin/announcements'],
  ])('rejects %s access to %s',async(role,path)=>{
    renderRoute(path,role);
    expect(await screen.findByRole('heading',{name:/access restricted/i})).toBeInTheDocument();
  });

  it.each([
    ['lecturer','/lecturer/announcements','Lecturer portal'],
    ['lecturer','/lecturer/timetable','Lecturer portal'],
    ['lecturer','/lecturer/notifications','Lecturer portal'],
    ['guardian','/guardian/announcements','Guardian portal'],
    ['guardian','/guardian/notifications','Guardian portal'],
    ['administrator','/admin/announcements','Administrative portal'],
    ['administrator','/admin/notifications','Administrative portal'],
  ])('renders %s communication route %s inside its PortalLayout',async(role,path,navigation)=>{
    renderRoute(path,role);
    expect(await screen.findByRole('navigation',{name:navigation})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/log out/i})).toBeInTheDocument();
  });

  it.each([
    ['student','/student/announcements','Student portal',['Announcements','Timetable','Notifications']],
    ['lecturer','/lecturer/announcements','Lecturer portal',['Announcements','Timetable','Notifications']],
    ['guardian','/guardian/announcements','Guardian portal',['Announcements','Notifications']],
    ['administrator','/admin/announcements','Administrative portal',['Announcements','Notifications']],
  ])('shows the %s Phase 15 navigation entries',async(role,path,navigation,labels)=>{
    renderRoute(path,role);
    const nav=await screen.findByRole('navigation',{name:navigation});
    for(const label of labels)expect(nav).toHaveTextContent(label);
  });
});
