import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  createElement,
} from "react";
import type { ReactNode } from "react";
import client from "@/api/client";
import { extractErrorMessage } from "@/api/errors";
import type { AuthState } from "@/types";

interface AuthContextValue extends AuthState {
  login: (req: { email: string; password: string }) => Promise<void>;
  signup: (req: { email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // On mount, check if we have valid auth by calling /auth/me
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const { data, error } = await client.GET("/auth/me");
        if (!error && data) {
          const user = data as { id: string; email: string; is_admin: boolean };
          setState({
            user: { id: user.id, email: user.email, is_admin: user.is_admin ?? false },
            isAuthenticated: true,
            isLoading: false,
          });
        } else {
          setState({ user: null, isAuthenticated: false, isLoading: false });
        }
      } catch {
        setState({ user: null, isAuthenticated: false, isLoading: false });
      }
    };
    void checkAuth();
  }, []);

  const login = useCallback(async (req: { email: string; password: string }) => {
    const { error } = await client.POST("/auth/login/dashboard", {
      body: req,
    });

    if (error) {
      throw new Error(extractErrorMessage(error, "Invalid email or password"));
    }

    // Fetch full user profile (including is_admin) after login
    const { data: meData } = await client.GET("/auth/me");
    if (meData) {
      const me = meData as { id: string; email: string; is_admin: boolean };
      setState({
        user: { id: me.id, email: me.email, is_admin: me.is_admin ?? false },
        isAuthenticated: true,
        isLoading: false,
      });
    } else {
      setState({
        user: { id: "", email: req.email, is_admin: false },
        isAuthenticated: true,
        isLoading: false,
      });
    }
  }, []);

  const signup = useCallback(
    async (req: { email: string; password: string }) => {
      const { error } = await client.POST("/auth/signup", {
        body: req,
      });

      if (error) {
        throw new Error(extractErrorMessage(error, "Signup failed. Please try again."));
      }

      // Auto-login after signup
      await login(req);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await client.POST("/auth/logout");
    } catch {
      // Ignore logout errors
    }
    setState({ user: null, isAuthenticated: false, isLoading: false });
  }, []);

  const value: AuthContextValue = { ...state, login, signup, logout };

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
