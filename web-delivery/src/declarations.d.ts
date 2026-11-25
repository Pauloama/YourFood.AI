interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module 'lucide-react' {
  import type { ComponentType, SVGProps } from 'react';
  export type LucideIcon = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; color?: string }>;
  export const ArrowRight: LucideIcon;
  export const BarChart3: LucideIcon;
  export const CheckCircle2: LucideIcon;
  export const Clock: LucideIcon;
  export const LogOut: LucideIcon;
  export const Plus: LucideIcon;
  export const PlusCircle: LucideIcon;
  export const Search: LucideIcon;
  export const ShieldCheck: LucideIcon;
  export const ShoppingBag: LucideIcon;
  export const Sparkles: LucideIcon;
  export const Star: LucideIcon;
  export const Store: LucideIcon;
  export const Trash2: LucideIcon;
  export const UtensilsCrossed: LucideIcon;
}
