import * as SecureStore from 'expo-secure-store';
const TOKEN_KEY='ngozi_access_token';
export const authStorage={getToken:()=>SecureStore.getItemAsync(TOKEN_KEY),setToken:(token:string)=>SecureStore.setItemAsync(TOKEN_KEY,token),clear:()=>SecureStore.deleteItemAsync(TOKEN_KEY)};
