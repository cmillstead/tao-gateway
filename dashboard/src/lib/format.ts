/**
 * Format an ISO timestamp as a human-readable relative time string.
 * Returns "Never" for null/undefined values.
 */
export function formatRelativeTime(isoTime: string | null | undefined): string {
  if (!isoTime) return "Never";
  const diff = Math.max(0, Date.now() - new Date(isoTime).getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
