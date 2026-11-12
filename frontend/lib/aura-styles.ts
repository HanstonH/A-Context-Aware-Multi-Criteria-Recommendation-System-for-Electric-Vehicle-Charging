/** Aura Design System — shared surface & interaction tokens */
export const aura = {
  /** Floating glass shell (sidebar, large panels) */
  glassShell:
    "bg-white/75 dark:bg-zinc-950/70 backdrop-blur-xl border-r border-white/30 dark:border-white/10 shadow-xl shadow-emerald-950/5",
  /** Standard elevated card */
  glassCard:
    "bg-white/80 dark:bg-zinc-900/65 backdrop-blur-md border border-white/40 dark:border-white/10 shadow-md shadow-black/5",
  /** Interactive card — hover lift */
  glassCardInteractive:
    "bg-white/80 dark:bg-zinc-900/65 backdrop-blur-md border border-white/40 dark:border-white/10 shadow-md hover:shadow-xl hover:border-primary/30 hover:-translate-y-0.5 active:scale-[0.99] transition-all duration-300",
  /** Inset search / input strip */
  glassInset:
    "bg-white/60 dark:bg-zinc-900/50 backdrop-blur-sm border border-white/50 dark:border-white/10 shadow-sm",
  /** Primary CTA */
  btnPrimary:
    "bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-lg shadow-emerald-600/25 hover:shadow-emerald-500/30 transition-all duration-300 active:scale-[0.98]",
  /** Icon / ghost control */
  btnGhost:
    "bg-white/70 dark:bg-zinc-800/70 backdrop-blur-md border border-white/40 dark:border-white/10 shadow-sm hover:shadow-md hover:bg-white/90 dark:hover:bg-zinc-800/90 active:scale-95 transition-all duration-300",
  /** FAB on map */
  fab:
    "bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/40 ring-2 ring-white/50 dark:ring-white/20 hover:scale-105 active:scale-95 transition-all duration-300",
  /** Section label */
  sectionTitle: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
  /** Low battery alert strip */
  alertLowBattery:
    "rounded-xl bg-destructive/10 backdrop-blur-sm border border-destructive/30 text-destructive px-3 py-2 text-xs font-medium shadow-sm",
} as const
