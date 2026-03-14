-- Multi-window rate limiter: per-key × per-subnet × three time windows.
-- Atomic: Redis executes the entire script as one operation.
--
-- KEYS[1] = rate:{key_id}:{subnet_id}:m   (minute counter)
-- KEYS[2] = rate:{key_id}:{subnet_id}:d   (day counter)
-- KEYS[3] = rate:{key_id}:{subnet_id}:M   (month counter)
--
-- ARGV[1] = minute_limit
-- ARGV[2] = day_limit
-- ARGV[3] = month_limit
-- ARGV[4] = minute_window   (seconds, typically 60)
-- ARGV[5] = day_window      (seconds, typically 86400)
-- ARGV[6] = month_window    (seconds, typically 2592000)
--
-- Returns array:
--   [1] allowed   (1 = yes, 0 = no)
--   [2] minute_count
--   [3] minute_ttl   (seconds until window resets, -1 if no key)
--   [4] day_count
--   [5] day_ttl
--   [6] month_count
--   [7] month_ttl

local minute_key   = KEYS[1]
local day_key      = KEYS[2]
local month_key    = KEYS[3]

local minute_limit  = tonumber(ARGV[1])
local day_limit     = tonumber(ARGV[2])
local month_limit   = tonumber(ARGV[3])
local minute_window = tonumber(ARGV[4])
local day_window    = tonumber(ARGV[5])
local month_window  = tonumber(ARGV[6])

-- Read current counts WITHOUT incrementing (returns "false"/nil if key missing)
local minute_count = tonumber(redis.call('GET', minute_key) or 0)
local day_count    = tonumber(redis.call('GET', day_key) or 0)
local month_count  = tonumber(redis.call('GET', month_key) or 0)

-- Check if any window would be exceeded BEFORE incrementing
if minute_count >= minute_limit or day_count >= day_limit or month_count >= month_limit then
    -- Denied: return current counts and TTLs without incrementing
    local minute_ttl = redis.call('TTL', minute_key)
    local day_ttl    = redis.call('TTL', day_key)
    local month_ttl  = redis.call('TTL', month_key)
    return {0, minute_count, minute_ttl, day_count, day_ttl, month_count, month_ttl}
end

-- All windows allow: increment all three counters
minute_count = redis.call('INCR', minute_key)
day_count    = redis.call('INCR', day_key)
month_count  = redis.call('INCR', month_key)

-- Set TTL only on first increment (counter == 1 means key was just created)
if minute_count == 1 then
    redis.call('EXPIRE', minute_key, minute_window)
end
if day_count == 1 then
    redis.call('EXPIRE', day_key, day_window)
end
if month_count == 1 then
    redis.call('EXPIRE', month_key, month_window)
end

-- Get TTLs for reset time calculation
local minute_ttl = redis.call('TTL', minute_key)
local day_ttl    = redis.call('TTL', day_key)
local month_ttl  = redis.call('TTL', month_key)

return {1, minute_count, minute_ttl, day_count, day_ttl, month_count, month_ttl}
