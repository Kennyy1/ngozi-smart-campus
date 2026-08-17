import {request} from './client';import type {LoginInput,LoginResponse,User} from '../types';
export const authApi={login:(input:LoginInput)=>request<LoginResponse>('/auth/login',{method:'POST',body:JSON.stringify(input)}),me:()=>request<User>('/auth/me')};
