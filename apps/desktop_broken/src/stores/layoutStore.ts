import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface LayoutState {
  sizes: number[];
  setLayout: (sizes: number[]) => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      sizes: [20, 80],
      setLayout: (sizes) => set({ sizes }),
    }),
    {
      name: 'layout-storage',
    }
  )
);