import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { License } from "../api/types";

const FALLBACK: License = {
  premium: false,
  plan: "free",
  features: {},
  hint: "Set AFR_PREMIUM_ENABLED=true to enable premium features.",
};

const LicenseContext = createContext<License>(FALLBACK);

export function LicenseProvider({ children }: { children: ReactNode }) {
  const [license, setLicense] = useState<License>(FALLBACK);

  useEffect(() => {
    api
      .getLicense()
      .then(setLicense)
      .catch(() => setLicense(FALLBACK));
  }, []);

  return <LicenseContext.Provider value={license}>{children}</LicenseContext.Provider>;
}

export function useLicense(): License {
  return useContext(LicenseContext);
}

export function usePremium(): boolean {
  return useContext(LicenseContext).premium;
}
