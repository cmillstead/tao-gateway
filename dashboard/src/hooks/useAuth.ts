import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  createElement,
} from "react";
import type { ReactNode } from "react";
import type { User, AuthState, LoginRequest, SignupRequest } from "@/types";

interface AuthContextValue extends AuthState {
  login: (req: LoginRequest) => Promise<void>;
  signup: (req: SignupRequest) => Promise<void>;
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
        const res = await fetch("/auth/me", { credentials: "include" });
        if (res.ok) {
          const data = (await res.json()) as { id: string; email: string };
          setState({
            user: { id: data.id, email: data.email },
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

  const login = useCallback(async (req: LoginRequest) => {
    const res = await fetch("/auth/login/dashboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(req),
    });

    if (!res.ok) {
      const body: { error?: { message?: string }; detail?: string } | null =
        await res.json().catch(() => null);
      const message =
        body?.error?.message ?? body?.detail ?? "Invalid email or password";
      throw new Error(message);
    }

    const user: User = { id: "", email: req.email };
    setState({ user, isAuthenticated: true, isLoading: false });
  }, []);

  const signup = useCallback(
    async (req: SignupRequest) => {
      const res = await fetch("/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(req),
      });

      if (!res.ok) {
        const body: { error?: { message?: string }; detail?: string } | null =
          await res.json().catch(() => null);
        const message =
          body?.error?.message ?? body?.detail ?? "Signup failed. Please try again.";
        throw new Error(message);
      }

      // Auto-login after signup
      await login(req);
    },
    [login],
  );

  const logout = useCallback(async () => {
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
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
