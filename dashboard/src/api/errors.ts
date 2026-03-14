/**
 * Extract a human-readable error message from an openapi-fetch error response.
 *
 * The gateway wraps all errors (including validation errors) in:
 *   { error: { type, message, code, errors? } }
 *
 * This helper handles that envelope and provides a fallback for unexpected shapes.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error != null && typeof error === "object") {
    const envelope = error as {
      error?: { message?: string };
      detail?: string;
    };
    if (envelope.error?.message) return envelope.error.message;
    if (envelope.detail) return envelope.detail;
  }
  return fallback;
}
