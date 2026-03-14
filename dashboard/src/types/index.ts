import type { components } from "@/api/schema";

// Frontend-only types (not derived from API)
export interface User {
  id: string;
  email: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// Re-export API schema types used by components and hooks
export type ApiKey = components["schemas"]["ApiKeyListItem"];
export type ApiKeyCreateRequest = components["schemas"]["ApiKeyCreateRequest"];
export type SubnetOverview = components["schemas"]["SubnetOverview"];
export type SubnetRateLimits = components["schemas"]["SubnetRateLimits"];
