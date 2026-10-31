/** Typed, validated access to VITE_* environment variables. */

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export const env = {
  apiBaseUrl: apiBaseUrl.replace(/\/+$/, ''),
  appName: import.meta.env.VITE_APP_NAME || 'Namma Suvidha',
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? '',
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? '',
  mapboxToken: import.meta.env.VITE_MAPBOX_TOKEN ?? '',
} as const
