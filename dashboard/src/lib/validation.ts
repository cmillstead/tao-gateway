const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface AuthFormErrors {
  email?: string;
  password?: string;
}

export function validateAuthForm(
  email: string,
  password: string,
): AuthFormErrors {
  const errors: AuthFormErrors = {};
  if (!email.trim()) {
    errors.email = "Email is required";
  } else if (!EMAIL_RE.test(email)) {
    errors.email = "Enter a valid email address";
  }
  if (!password) {
    errors.password = "Password is required";
  } else if (password.length < 8) {
    errors.password = "Password must be at least 8 characters";
  }
  return errors;
}
