import { useEffect, useState } from "react";
import apiClient from "../components/utils/axios";
import { useAuth } from "../components/auth/AuthContext";

// Which optional modules (points, storefront, calendar) are on for the current org.
// Until the answer arrives, or if the request fails, every module counts as on.
const useOrgModules = () => {
  const { currentOrg } = useAuth();
  const [states, setStates] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!currentOrg?.id) {
      setStates({});
      return undefined;
    }
    let cancelled = false;
    apiClient
      .get<{ modules?: { name: string; enabled?: boolean }[] }>(`/api/organizations/${currentOrg.id}/modules`)
      .then((response) => {
        if (cancelled) return;
        const next: Record<string, boolean> = {};
        (response.data?.modules || []).forEach((m) => {
          next[m.name] = m.enabled !== false;
        });
        setStates(next);
      })
      .catch(() => {
        if (!cancelled) setStates({});
      });
    return () => {
      cancelled = true;
    };
  }, [currentOrg?.id]);

  const isEnabled = (name?: string) => !name || states[name] !== false;
  return { isEnabled };
};

export default useOrgModules;
