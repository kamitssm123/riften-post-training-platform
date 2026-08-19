export type Route =
  | { name: "traces" }
  | { name: "tradeoff" }
  | { name: "exclusions" }
  | { name: "trace"; id: string }
  | { name: "session"; id: string };

export function parsePath(pathname: string): Route {
  const traceMatch = pathname.match(/^\/traces\/([^/]+)\/?$/);
  if (traceMatch) return { name: "trace", id: decodeURIComponent(traceMatch[1]) };

  const sessionMatch = pathname.match(/^\/sessions\/([^/]+)\/?$/);
  if (sessionMatch) return { name: "session", id: decodeURIComponent(sessionMatch[1]) };

  if (pathname === "/exclusions") return { name: "exclusions" };
  if (pathname === "/model-tradeoff") return { name: "tradeoff" };
  return { name: "traces" };
}

export function pathForRoute(route: Route): string {
  switch (route.name) {
    case "trace":
      return `/traces/${encodeURIComponent(route.id)}`;
    case "session":
      return `/sessions/${encodeURIComponent(route.id)}`;
    case "exclusions":
      return "/exclusions";
    case "tradeoff":
      return "/model-tradeoff";
    case "traces":
      return "/";
  }
}
