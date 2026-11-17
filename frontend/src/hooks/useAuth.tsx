import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User } from '../types';
import { auth } from '../api/client';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAdmin: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, fullName: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('tg_token'));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const savedUser = localStorage.getItem('tg_user');
    if (savedUser && token) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        logout();
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const res = await auth.login(email, password);
    localStorage.setItem('tg_token', res.access_token);
    const me = await auth.me();
    localStorage.setItem('tg_user', JSON.stringify(me));
    setToken(res.access_token);
    setUser(me);
  };

  const register = async (email: string, fullName: string, password: string) => {
    const res = await auth.register(email, fullName, password);
    localStorage.setItem('tg_token', res.access_token);
    const me = await auth.me();
    localStorage.setItem('tg_user', JSON.stringify(me));
    setToken(res.access_token);
    setUser(me);
  };

  const logout = () => {
    localStorage.removeItem('tg_token');
    localStorage.removeItem('tg_user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user, token,
      isAdmin: user?.role === 'admin',
      isLoading,
      login, register, logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
