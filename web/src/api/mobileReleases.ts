import {request} from './client';
export interface PublicMobileRelease{platform:'android';version:string;version_code:number;filename:string;file_size:number;sha256:string;release_notes:string;released_at:string;download_url:string}
export interface MobileRelease extends PublicMobileRelease{id:string;status:'draft'|'published'|'retired';is_latest:boolean;created_by_user_id:string;created_at:string;updated_at:string}
export const publicMobileApi={latest:()=>request<PublicMobileRelease>('/public/mobile-app/android/latest')};
export const mobileReleaseApi={list:()=>request<MobileRelease[]>('/mobile-app-releases'),upload:(form:FormData)=>request<MobileRelease>('/mobile-app-releases/upload',{method:'POST',body:form}),publish:(id:string)=>request<MobileRelease>(`/mobile-app-releases/${encodeURIComponent(id)}/publish`,{method:'POST'}),retire:(id:string)=>request<MobileRelease>(`/mobile-app-releases/${encodeURIComponent(id)}/retire`,{method:'POST'})};
