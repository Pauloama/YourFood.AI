import { createContext, useContext, useState, type ReactNode } from 'react';
import { deliveryApi, getStoredSession, saveSession } from '../services/api';
import type { AuthTokenResponse, UserRole, UserSummary } from '../types/models';

interface AuthContextValue {
  user: UserSummary | null;
  login: (email: string, password: string) => Promise<void>;
  register: (fullName: string, email: string, password: string, role: UserRole) => Promise<void>;
  oauthLogin: (provider: string, email: string, fullName: string, role: UserRole) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthTokenResponse | null>(() => getStoredSession());

  const applySession = (next: AuthTokenResponse) => {
    saveSession(next);
    setSession(next);
  };

  const login = async (email: string, password: string) => {
    const res = await deliveryApi.login(email, password);
    applySession(res);
  };

  const register = async (fullName: string, email: string, password: string, role: UserRole) => {
    const res = await deliveryApi.register(fullName, email, password, role);
    applySession(res);
  };

  const oauthLogin = async (provider: string, email: string, fullName: string, role: UserRole) => {
    const res = await deliveryApi.oauthExternalLogin(provider, email, fullName, role);
    applySession(res);
  };

  const logout = () => {
    saveSession(null);
    setSession(null);
  };

  return (
    <AuthContext.Provider value={{ user: session?.user ?? null, login, register, oauthLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
