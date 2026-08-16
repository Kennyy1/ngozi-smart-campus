import {request} from './client'; import type {AuthenticatedUser,LoginRequest,LoginResponse} from '../types';
export const authApi={login:(body:LoginRequest)=>request<LoginResponse>('/auth/login',{method:'POST',body:JSON.stringify(body)}),me:()=>request<AuthenticatedUser>('/auth/me')};
