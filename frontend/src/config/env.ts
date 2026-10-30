/** Typed, validated access to VITE_* environment variables. */

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL

if (!apiBaseUrl) {
  throw new Error(
    'VITE_API_BASE_URL is not set. Copy frontend/.env.example to frontend/.env and restart the dev server.',
  )
}

export const env = {
  apiBaseUrl: apiBaseUrl.replace(/\/+$/, ''),
  appName: import.meta.env.VITE_APP_NAME || 'Namma Suvidha',
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? '',
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? '',
} as const
