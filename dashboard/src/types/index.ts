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
