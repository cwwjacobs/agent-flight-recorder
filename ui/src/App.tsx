import { HashRouter, Link, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "./themes/ThemeContext";
import { ThemeToggle } from "./components/ThemeToggle";
import { LicenseProvider, useLicense } from "./license/LicenseContext";
import RunListPage from "./pages/RunListPage";
import RunDetailPage from "./pages/RunDetailPage";

function FeatureChip() {
  const license = useLicense();
  return (
    <span
      className={`plan-chip ${license.experimental_enabled ? "experimental" : ""}`}
      title={license.hint ?? "advanced/experimental features enabled"}
    >
      {license.experimental_enabled ? "◆ experimental" : "standard"}
    </span>
  );
}

function BrandMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden>
      <path d="M8 24 L16 6 L24 24" stroke="var(--accent)" strokeWidth="2.5" fill="none" />
      <circle cx="16" cy="19" r="2.6" fill="var(--highlight)" />
    </svg>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <LicenseProvider>
        <HashRouter>
          <div className="app">
            <header className="topbar">
              <Link to="/" className="brand">
                <span className="brand-mark">
                  <BrandMark />
                </span>
                <span className="brand-text">
                  <span className="brand-title">
                    Agent <em>Flight Recorder</em>
                  </span>
                  <span className="brand-sub">observability · replay · checkpoints</span>
                </span>
              </Link>
              <span className="rec-dot" title="recording" />
              <FeatureChip />
              <span className="topbar-spacer" />
              <ThemeToggle />
            </header>

            <Routes>
              <Route path="/" element={<RunListPage />} />
              <Route path="/runs/:runId" element={<RunDetailPage />} />
            </Routes>
          </div>
        </HashRouter>
      </LicenseProvider>
    </ThemeProvider>
  );
}
