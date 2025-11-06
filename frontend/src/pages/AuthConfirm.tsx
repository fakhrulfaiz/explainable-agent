import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { createSupabaseClient } from '@/api/supabase';
import { type EmailOtpType } from '@supabase/supabase-js';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function AuthConfirm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const confirmAuth = async () => {
      try {
        const supabase = createSupabaseClient();
        
        // Try to handle the session from URL hash
        const { data, error } = await supabase.auth.getSession();
        
        if (data?.session) {
          // Already has a session, redirect to home
          navigate('/');
          return;
        }

        // Check for OTP verification parameters
        const token_hash = searchParams.get('token_hash') || searchParams.get('token');
        const type = (searchParams.get('type') || searchParams.get('confirmation_type')) as EmailOtpType | null;
        
        // Debug logging
        console.log('URL Search Params:', Object.fromEntries(searchParams.entries()));
        console.log('Token hash:', token_hash);
        console.log('Type:', type);

        if (token_hash && type) {
          const { data, error: verifyError } = await supabase.auth.verifyOtp({
            type,
            token_hash,
          });

          if (verifyError) {
            throw verifyError;
          }

          // Session is automatically set by Supabase
          console.log('Auth successful:', data);
          
        
          navigate('/', { replace: true });
        } else {
          // If we reach here, check what parameters we have
          const allParams = Object.fromEntries(searchParams.entries());
          console.error('Missing auth parameters:', allParams);
          
          if (Object.keys(allParams).length === 0) {
            setError('No authentication parameters found. Please use the link from your email.');
          } else {
            setError(`Invalid authentication parameters. Found: ${JSON.stringify(allParams)}`);
          }
        }
      } catch (err: any) {
        console.error('Auth confirmation error:', err);
        setError(err?.message || 'Failed to confirm authentication');
      } finally {
        setLoading(false);
      }
    };

    confirmAuth();
  }, [searchParams, navigate]);

  if (loading) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-6 md:p-10">
        <div className="w-full max-w-sm">
          <Card>
            <CardHeader>
              <CardTitle className="text-2xl">Confirming...</CardTitle>
              <CardDescription>Please wait while we confirm your account</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Processing your authentication...
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-6 md:p-10">
        <div className="w-full max-w-sm">
          <Card>
            <CardHeader>
              <CardTitle className="text-2xl">Authentication Error</CardTitle>
              <CardDescription>There was a problem confirming your account</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-destructive">{error}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return null;
}
