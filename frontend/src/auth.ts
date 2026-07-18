const AUTH_KEY = "dpm_auth_session";

/** Demo credentials — override with VITE_LOGIN_USER / VITE_LOGIN_PASS */
export const DEMO_USER = import.meta.env.VITE_LOGIN_USER || "admin";
export const DEMO_PASS = import.meta.env.VITE_LOGIN_PASS || "admin123";

export function isAuthenticated(): boolean {
  try {
    return localStorage.getItem(AUTH_KEY) === "1";
  } catch {
    return false;
  }
}

export function login(username: string, password: string): boolean {
  if (username.trim() === DEMO_USER && password === DEMO_PASS) {
    localStorage.setItem(AUTH_KEY, "1");
    return true;
  }
  return false;
}

export function logout(): void {
  localStorage.removeItem(AUTH_KEY);
}
