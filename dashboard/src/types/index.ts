export interface User {
  id: string;
  email: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface ApiError {
  error: {
    type: string;
    message: string;
    code: number;
  };
}

export interface SignupRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupResponse {
  id: string;
  email: string;
  message: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

// API Key types

export interface ApiKey {
  id: string;
  prefix: string;
  name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ApiKeyCreateRequest {
  environment: "live" | "test";
  name?: string | null;
}

export interface ApiKeyCreateResponse {
  id: string;
  key: string;
  prefix: string;
  name: string;
  created_at: string;
}

export interface ApiKeyListResponse {
  items: ApiKey[];
  total: number;
}

export interface ApiKeyRotateResponse {
  new_key: ApiKeyCreateResponse;
  revoked_key_id: string;
}

// Dashboard overview types

export interface SubnetRateLimits {
  minute: number;
  day: number;
  month: number;
}

export interface SubnetOverview {
  name: string;
  netuid: number;
  status: "healthy" | "degraded" | "unavailable";
  rate_limits: SubnetRateLimits;
}

export interface OverviewData {
  email: string;
  tier: string;
  created_at: string;
  api_key_count: number;
  first_api_key_prefix: string | null;
  subnets: SubnetOverview[];
}
