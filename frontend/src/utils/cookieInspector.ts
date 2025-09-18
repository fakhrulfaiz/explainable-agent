/**
 * Utility to inspect Supabase cookies
 */

export const inspectSupabaseCookies = () => {
  const cookies = document.cookie.split(';').reduce((acc, cookie) => {
    const [name, value] = cookie.trim().split('=');
    acc[name] = decodeURIComponent(value);
    return acc;
  }, {} as Record<string, string>);

  // Filter for Supabase-related cookies
  const supabaseCookies = Object.entries(cookies).filter(([name]) => 
    name.includes('supabase') || 
    name.includes('sb-') || 
    name.includes('auth-token')
  );

  console.log('All Cookies:', cookies);
  console.log('Supabase Cookies:', supabaseCookies);
  
  return { allCookies: cookies, supabaseCookies };
};

export const inspectLocalStorage = () => {
  const supabaseKeys = [];
  
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && (key.includes('supabase') || key.includes('sb-'))) {
      const value = localStorage.getItem(key);
      supabaseKeys.push({ key, value });
    }
  }
  
  console.log('Supabase Local Storage:', supabaseKeys);
  return supabaseKeys;
};

// Usage example
export const debugSupabaseStorage = () => {
  console.log('=== Supabase Storage Debug ===');
  inspectSupabaseCookies();
  inspectLocalStorage();
  console.log('========================');
};
