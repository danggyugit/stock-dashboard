import { create } from "zustand";

interface AppState {
  selectedTicker: string | null;
  compareTickers: string[];
  sidebarOpen: boolean;
  theme: "light" | "dark";
  setSelectedTicker: (ticker: string | null) => void;
  addCompareTicker: (ticker: string) => void;
  removeCompareTicker: (ticker: string) => void;
  clearCompareTickers: () => void;
  toggleSidebar: () => void;
  setTheme: (theme: "light" | "dark") => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedTicker: null,
  compareTickers: [],
  sidebarOpen: false,
  theme: "light",

  setSelectedTicker: (ticker) => set({ selectedTicker: ticker }),

  addCompareTicker: (ticker) =>
    set((state) => {
      if (state.compareTickers.includes(ticker) || state.compareTickers.length >= 5) {
        return state;
      }
      return { compareTickers: [...state.compareTickers, ticker] };
    }),

  removeCompareTicker: (ticker) =>
    set((state) => ({
      compareTickers: state.compareTickers.filter((t) => t !== ticker),
    })),

  clearCompareTickers: () => set({ compareTickers: [] }),

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setTheme: (theme) => set({ theme }),
}));
