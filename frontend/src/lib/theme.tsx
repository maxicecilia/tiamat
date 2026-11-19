import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'

/** Light/dark mode; only used by the boring skin (the others are always dark). */
export type Theme = 'light' | 'dark' | 'system'
/** Visual skin. */
export type Skin = 'boring' | 'phosphor' | 'gibson' | 'tiamat'

export const SKINS: { value: Skin; label: string; tagline: string; swatch: string[] }[] = [
  { value: 'boring', label: 'Boring', tagline: '', swatch: ['#171717', '#e5e5e5'] },
  { value: 'phosphor', label: 'Phosphor', tagline: 'root@tiamat:~$', swatch: ['#050a07', '#39e58c'] },
  { value: 'gibson', label: 'Gibson', tagline: '// hack the planet', swatch: ['#100c24', '#ff3ea5', '#22d3ee'] },
  { value: 'tiamat', label: 'Tiamat', tagline: 'power demands respect', swatch: ['#f0545a', '#e4e4ea', '#3a3a45'] },
]

// Earlier draft names, so a saved choice keeps working.
const LEGACY_SKINS: Record<string, Skin> = { classic: 'boring', hoard: 'tiamat', heads: 'tiamat' }

const THEME_KEY = 'tiamat-theme'
const SKIN_KEY = 'tiamat-skin'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

function apply(theme: Theme, skin: Skin) {
  const dark = skin !== 'boring' || theme === 'dark' || (theme === 'system' && media().matches)
  const root = document.documentElement
  root.classList.toggle('dark', dark)
  root.style.colorScheme = dark ? 'dark' : 'light'
  root.dataset.skin = skin
}

type ThemeState = { theme: Theme; setTheme: (t: Theme) => void; skin: Skin; setSkin: (s: Skin) => void }
const ThemeContext = createContext<ThemeState | null>(null)

function savedTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY)
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'dark'
}

function savedSkin(): Skin {
  const saved = localStorage.getItem(SKIN_KEY) ?? ''
  if (SKINS.some((s) => s.value === saved)) return saved as Skin
  return LEGACY_SKINS[saved] ?? 'boring'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(savedTheme)
  const [skin, setSkinState] = useState<Skin>(savedSkin)

  useEffect(() => {
    apply(theme, skin)
    if (theme !== 'system' || skin !== 'boring') return
    const m = media()
    const onChange = () => apply('system', skin)
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [theme, skin])

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem(THEME_KEY, t)
    setThemeState(t)
  }, [])
  const setSkin = useCallback((s: Skin) => {
    localStorage.setItem(SKIN_KEY, s)
    setSkinState(s)
  }, [])

  return <ThemeContext value={{ theme, setTheme, skin, setSkin }}>{children}</ThemeContext>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
