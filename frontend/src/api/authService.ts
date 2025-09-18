import { supabaseClient } from './supabase';
import { apiClient } from './client';

export class AuthService {
  /**
   * Get current user session
   */
  async getCurrentUser() {
    const { data: { user }, error } = await supabaseClient.auth.getUser();
    if (error) throw error;
    return user;
  }

  /**
   * Get current session with access token
   */
  async getCurrentSession() {
    const { data: { session }, error } = await supabaseClient.auth.getSession();
    if (error) throw error;
    return session;
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    try {
      const session = await this.getCurrentSession();
      return !!session?.access_token;
    } catch {
      return false;
    }
  }

  /**
   * Get access token for API calls
   */
  async getAccessToken(): Promise<string | null> {
    try {
      const session = await this.getCurrentSession();
      return session?.access_token || null;
    } catch {
      return null;
    }
  }

  /**
   * Sign out user
   */
  async signOut() {
    const { error } = await supabaseClient.auth.signOut();
    if (error) throw error;
  }

  /**
   * Listen to auth state changes
   */
  onAuthStateChange(callback: (event: string, session: any) => void) {
    return supabaseClient.auth.onAuthStateChange(callback);
  }
}

export const authService = new AuthService();
