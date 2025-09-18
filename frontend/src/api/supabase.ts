import { createBrowserClient } from '@supabase/ssr'

export function createSupabaseClient() {
  return createBrowserClient(
    import.meta.env.VITE_SUPABASE_URL!,
    import.meta.env.VITE_SUPABASE_PUBLISHABLE_OR_ANON_KEY!
  )
}

// Export singleton instance for consistency with your existing API pattern
export const supabaseClient = createSupabaseClient();
export default supabaseClient;
