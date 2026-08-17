const TOKEN_KEY='ngozi_access_token';
const API_BASE_URL=(import.meta.env.VITE_API_BASE_URL as string|undefined)?.replace(/\/$/,'')??'http://127.0.0.1:8000/api/v1';
export const publicApiUrl=(path:string)=>/^https?:\/\//i.test(path)?path:new URL(path,API_BASE_URL).toString();
export class ApiError extends Error {constructor(message:string,public status:number,public details?:unknown){super(message);this.name='ApiError'}}
export const session={get:()=>sessionStorage.getItem(TOKEN_KEY),set:(token:string)=>sessionStorage.setItem(TOKEN_KEY,token),clear:()=>sessionStorage.removeItem(TOKEN_KEY)};
type UnauthorizedHandler=()=>void;
let onUnauthorized:UnauthorizedHandler|undefined;
export const setUnauthorizedHandler=(handler:UnauthorizedHandler|undefined)=>{onUnauthorized=handler};
export async function request<T>(path:string,options:RequestInit={}):Promise<T>{
 const token=session.get(); const headers=new Headers(options.headers); headers.set('Accept','application/json');
 if(options.body&&!(options.body instanceof FormData))headers.set('Content-Type','application/json'); if(token)headers.set('Authorization',`Bearer ${token}`);
 let response:Response; try{response=await fetch(`${API_BASE_URL}${path}`,{...options,headers})}catch{throw new ApiError('Unable to reach the campus service. Please try again.',0)}
 if(response.status===401&&token){session.clear();onUnauthorized?.()}
 if(!response.ok){let detail:unknown;try{detail=await response.json()}catch{detail=undefined}const message=typeof detail==='object'&&detail!==null&&'detail' in detail&&typeof detail.detail==='string'?detail.detail:response.status===403?'You do not have permission to view this page.':response.status===404?'The requested record was not found.':'The request could not be completed.';throw new ApiError(message,response.status,detail)}
 if(response.status===204)return undefined as T; return response.json() as Promise<T>;
}
