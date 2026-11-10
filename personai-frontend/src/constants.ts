/**
 * API configuration - centralized base URL
 * Uses relative path through Vite dev proxy by default, or VITE_API_BASE override
 */

const getApiBase = (): string => {
  // Use VITE_API_BASE if explicitly set
  if (import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }
  
  // Default: relative path through Vite dev proxy (dev) or same origin (prod)
  // This works in both dev (proxied) and prod (same origin)
  return '/api';
};

export const API_BASE = getApiBase();
