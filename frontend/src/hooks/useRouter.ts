import { useCallback, useEffect, useState } from "react";

function getPathname(): string {
  return window.location.pathname;
}

/**
 * Minimal client-side router: tracks window.location.pathname and exposes a
 * navigate() that pushes history entries, so views get real, shareable,
 * back/forward-aware URLs without pulling in a routing library.
 */
export function useRouter() {
  const [pathname, setPathname] = useState<string>(getPathname);

  useEffect(() => {
    const onPopState = () => setPathname(getPathname());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((path: string) => {
    if (path === window.location.pathname) return;
    window.history.pushState({}, "", path);
    setPathname(path);
  }, []);

  return { pathname, navigate };
}
