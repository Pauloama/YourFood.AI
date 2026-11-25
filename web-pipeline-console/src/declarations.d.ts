interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module 'lucide-react' {
  import type { ComponentType, SVGProps } from 'react';
  export type LucideIcon = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; color?: string }>;
  export const Activity: LucideIcon;
  export const Cpu: LucideIcon;
  export const Database: LucideIcon;
  export const Download: LucideIcon;
  export const FileCode2: LucideIcon;
  export const LogOut: LucideIcon;
  export const Play: LucideIcon;
  export const RefreshCw: LucideIcon;
  export const Shield: LucideIcon;
  export const Sparkles: LucideIcon;
}
