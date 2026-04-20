"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  AUTH_REQUIRED_EVENT,
  changePassword as changePasswordRequest,
  getAuthState,
  login as loginRequest,
  logout as logoutRequest,
  type AuthState,
  type AuthUser,
  type ChangePasswordRequest,
  type LoginRequest,
} from "@/lib/api";

type AuthBootstrapStatus = "loading" | "ready" | "error";

interface AuthContextValue {
  authState: AuthState | null;
  authStatus: AuthBootstrapStatus;
  authError: string | null;
  authEnabled: boolean;
  isAuthenticated: boolean;
  user: AuthUser | null;
  refreshSession: (options?: { silent?: boolean }) => Promise<AuthState>;
  login: (payload: LoginRequest) => Promise<AuthState>;
  logout: () => Promise<AuthState>;
  changePassword: (payload: ChangePasswordRequest) => Promise<AuthState>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function formatAuthError(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to reach auth service";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthBootstrapStatus>("loading");
  const [authError, setAuthError] = useState<string | null>(null);

  const refreshSession = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setAuthStatus("loading");
      }
      setAuthError(null);

      try {
        const nextState = await getAuthState();
        setAuthState(nextState);
        setAuthStatus("ready");
        return nextState;
      } catch (error) {
        setAuthState(null);
        setAuthError(formatAuthError(error));
        setAuthStatus("error");
        throw error;
      }
    },
    []
  );

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    const handleAuthRequired = () => {
      void refreshSession({ silent: true });
    };

    window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired);
    return () => {
      window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired);
    };
  }, [refreshSession]);

  const login = useCallback(async (payload: LoginRequest) => {
    const nextState = await loginRequest(payload);
    setAuthState(nextState);
    setAuthError(null);
    setAuthStatus("ready");
    return nextState;
  }, []);

  const logout = useCallback(async () => {
    const nextState = await logoutRequest();
    setAuthState(nextState);
    setAuthError(null);
    setAuthStatus("ready");
    return nextState;
  }, []);

  const changePassword = useCallback(
    async (payload: ChangePasswordRequest) => {
      const nextState = await changePasswordRequest(payload);
      setAuthState(nextState);
      setAuthError(null);
      setAuthStatus("ready");
      return nextState;
    },
    []
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      authState,
      authStatus,
      authError,
      authEnabled: authState?.enabled ?? false,
      isAuthenticated:
        authState?.enabled === false ? true : Boolean(authState?.authenticated),
      user: authState?.user ?? null,
      refreshSession,
      login,
      logout,
      changePassword,
    }),
    [authError, authState, authStatus, changePassword, login, logout, refreshSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
