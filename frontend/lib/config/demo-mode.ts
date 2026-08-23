export const awsDemoMode = process.env.NEXT_PUBLIC_AWS_DEMO_MODE === 'true';

export function isDemoDisabledPath(pathname: string) {
  return (
    pathname === '/register' ||
    pathname === '/monitors' ||
    pathname.startsWith('/monitors/') ||
    pathname === '/alerts' ||
    pathname.startsWith('/alerts/')
  );
}
