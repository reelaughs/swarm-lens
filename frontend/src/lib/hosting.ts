export const isHostedDemo = import.meta.env.VITE_SWARMLENS_MODE === "hosted";

interface RouteLocation {
  pathname: string;
  hash: string;
}

export function routePathFromLocation(
  location: RouteLocation,
  hosted = isHostedDemo,
): string {
  if (!hosted) return location.pathname;
  return location.hash.startsWith("#/") ? location.hash.slice(1) : "/";
}

export function browserRouteHref(
  path: string,
  hosted = isHostedDemo,
  baseUrl = import.meta.env.BASE_URL,
): string {
  if (!hosted) return path;
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return `${normalizedBase}#${path}`;
}
