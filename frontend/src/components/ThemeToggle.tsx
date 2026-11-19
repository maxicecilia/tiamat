import { Monitor, Moon, Sun } from 'lucide-react'
import { SKINS, type Theme, useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

const modes: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

/** Skin picker plus light/dark mode for the boring skin. */
export function ThemeToggle() {
  const { theme, setTheme, skin, setSkin } = useTheme()
  return (
    <div className="flex flex-col gap-2">
      <div role="group" aria-label="Skin" className="flex flex-col gap-0.5">
        <span className="px-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">Theme</span>
        {SKINS.map((s) => (
          <button
            key={s.value}
            aria-pressed={skin === s.value}
            onClick={() => setSkin(s.value)}
            className={cn(
              'flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground',
              skin === s.value && 'bg-sidebar-accent text-foreground',
            )}
          >
            <span className="flex shrink-0 -space-x-1" aria-hidden>
              {s.swatch.slice(0, 3).map((c) => (
                <span key={c} className="size-3 rounded-full ring-1 ring-black/40" style={{ background: c }} />
              ))}
            </span>
            {s.label}
          </button>
        ))}
      </div>
      {skin === 'boring' && (
        <div role="radiogroup" aria-label="Mode" className="flex rounded-md border p-0.5">
          {modes.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              role="radio"
              aria-checked={theme === value}
              aria-label={label}
              title={label}
              onClick={() => setTheme(value)}
              className={cn(
                'flex flex-1 items-center justify-center rounded-sm py-1 text-muted-foreground hover:text-foreground',
                theme === value && 'bg-sidebar-accent text-foreground',
              )}
            >
              <Icon className="size-3.5" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
