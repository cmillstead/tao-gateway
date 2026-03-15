export interface SubnetMetrics {
  subnet_name: string;
  netuid: number;
  request_count: number;
  success_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
}

export interface MetricsResponse {
  time_range: string;
  subnets: SubnetMetrics[];
  total_requests: number;
  total_errors: number;
  overall_error_rate: number;
}

export interface SubnetMetagraphStatus {
  netuid: number;
  subnet_name: string;
  last_sync_time: string | null;
  staleness_seconds: number;
  is_stale: boolean;
  sync_status: "healthy" | "degraded" | "never_synced";
  last_sync_error: string | null;
  consecutive_failures: number;
  active_miners: number;
}

export interface MetagraphResponse {
  subnets: SubnetMetagraphStatus[];
}

export interface DeveloperSummary {
  org_id: string;
  email: string;
  signup_date: string;
  last_active: string | null;
  total_requests: number;
  requests_by_subnet: Record<string, number>;
}

export interface DeveloperMetrics {
  total_developers: number;
  new_signups_today: number;
  new_signups_this_week: number;
  weekly_active_developers: number;
  developers: DeveloperSummary[];
}

export interface MinerInfo {
  miner_uid: number;
  hotkey: string;
  netuid: number;
  subnet_name: string;
  incentive_score: number;
  gateway_quality_score: number;
  total_requests: number;
  successful_requests: number;
  avg_latency_ms: number;
  error_rate: number;
}

export interface MinerResponse {
  subnets: Record<string, MinerInfo[]>;
}
