import { THEMES, useTheme } from "../themes/ThemeContext";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-switch" role="group" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.id}
          className={theme === t.id ? "active" : ""}
          onClick={() => setTheme(t.id)}
          aria-pressed={theme === t.id}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
