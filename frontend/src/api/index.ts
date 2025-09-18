// Main API exports
export { apiClient } from './client';

// Export Supabase client for authentication
export { createSupabaseClient, supabaseClient } from './supabase';

export * from './types';
export * from './endpoints';
export * from './services';

// Default export for convenience
export { default as api } from './client';
