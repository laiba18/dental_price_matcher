import { useEffect, useState } from "react";
import { checkHealth } from "../api/client";

type BackendStatus = "checking" | "online" | "offline";

export function useBackendStatus() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function ping() {
      try {
        const data = await checkHealth();
        if (!active) return;
        setStatus("online");
        setVersion(data.version);
      } catch {
        if (!active) return;
        setStatus("offline");
        setVersion(null);
      }
    }

    ping();
    const interval = window.setInterval(ping, 15000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return { status, version };
}
