import { create } from "zustand";

interface User {
  email: string;
  name: string;
  avatar_url: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (credential: string) => Promise<void>;
  logout: () => void;
  restore: () => Promise<void>;
}

const STORAGE_KEY = "stockdash_user";

function decodeGoogleJwt(credential: string): { email: string; name: string; picture: string } {
  const base64 = credential.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  const payload = JSON.parse(atob(base64));
  return { email: payload.email ?? "", name: payload.name ?? "", picture: payload.picture ?? "" };
}

function getApprovedEmails(): string[] {
  const raw = import.meta.env.VITE_APPROVED_EMAILS ?? "";
  return raw
    .split(",")
    .map((e: string) => e.trim().toLowerCase())
    .filter(Boolean);
}

const useAuthStore = create<AuthState>((set) => ({
  user: (() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    } catch {
      return null;
    }
  })(),
  isAuthenticated: !!localStorage.getItem(STORAGE_KEY),

  login: async (credential: string) => {
    const { email, name, picture } = decodeGoogleJwt(credential);

    const approved = getApprovedEmails();
    if (approved.length > 0 && !approved.includes(email.toLowerCase())) {
      const err = new Error("Access not yet approved. Please contact the administrator.") as Error & { status: number };
      err.status = 403;
      throw err;
    }

    const user: User = { email, name, avatar_url: picture };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    set({ user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem(STORAGE_KEY);
    set({ user: null, isAuthenticated: false });
  },

  restore: async () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const user = JSON.parse(stored) as User;
        set({ user, isAuthenticated: true });
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  },
}));

export default useAuthStore;
