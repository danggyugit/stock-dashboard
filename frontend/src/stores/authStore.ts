import { create } from "zustand";
import apiClient from "@/api/client";

interface User {
  id: number;
  email: string;
  name: string;
  avatar_url: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credential: string) => Promise<void>;
  logout: () => void;
  restore: () => Promise<void>;
}

const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("stockdash_token"),
  isAuthenticated: !!localStorage.getItem("stockdash_token"),

  login: async (credential: string) => {
    const { data } = await apiClient.post("/auth/google", { credential });
    const { token, user } = data;
    localStorage.setItem("stockdash_token", token);
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("stockdash_token");
    set({ user: null, token: null, isAuthenticated: false });
  },

  restore: async () => {
    const token = get().token;
    if (!token) return;
    try {
      const { data } = await apiClient.get("/auth/me");
      set({ user: data, isAuthenticated: true });
    } catch {
      // Token expired or invalid
      localStorage.removeItem("stockdash_token");
      set({ user: null, token: null, isAuthenticated: false });
    }
  },
}));

export default useAuthStore;
