import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, type User, type UserProfile } from '../api/client';

interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: { email: string; password: string; display_name: string; role: string; phone_number?: string }) => Promise<User>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadCurrentUser = async (): Promise<User> => {
    const me = await api.getMe();
    setUser(me);
    try {
      const prof = await api.getProfile();
      setProfile(prof);
    } catch {
      // Profile may not exist or fail non-critically
    }
    return me;
  };

  useEffect(() => {
    let mounted = true;
    const handleAuthExpired = () => {
      setUser(null);
      setProfile(null);
    };
    window.addEventListener('agri-auth-expired', handleAuthExpired);

    const init = async () => {
      try {
        const me = await api.getMe();
        if (!mounted) return;
        setUser(me);
        try {
          const prof = await api.getProfile();
          if (mounted) setProfile(prof);
        } catch {
          // ignore
        }
      } catch {
        if (mounted) {
          setUser(null);
          setProfile(null);
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    };

    void init();

    return () => {
      mounted = false;
      window.removeEventListener('agri-auth-expired', handleAuthExpired);
    };
  }, []);

  const login = async (email: string, password: string): Promise<User> => {
    await api.login({ email, password });
    return await loadCurrentUser();
  };

  const register = async (payload: { email: string; password: string; display_name: string; role: string; phone_number?: string }): Promise<User> => {
    await api.register(payload);
    await api.login({ email: payload.email, password: payload.password });
    return await loadCurrentUser();
  };

  const logout = () => {
    api.clearTokens();
    setUser(null);
    setProfile(null);
  };

  const refreshProfile = async () => {
    if (!user) return;
    try {
      const prof = await api.getProfile();
      setProfile(prof);
    } catch (err) {
      console.error('Error refreshing profile:', err);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
