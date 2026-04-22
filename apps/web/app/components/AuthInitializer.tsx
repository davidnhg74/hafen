'use client';

import { useEffect } from 'react';
import { fetchCurrentUser } from '@/app/lib/api';
import { useAuthStore } from '@/app/store/authStore';

export default function AuthInitializer() {
  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const user = await fetchCurrentUser();
          if (user) {
            useAuthStore.getState().setUser(user);
          }
        } catch (error) {
          // Token is invalid, clear it
          localStorage.removeItem('access_token');
        }
      }
    };

    initializeAuth();
  }, []);

  return null;
}
