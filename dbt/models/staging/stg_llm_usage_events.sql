SELECT
    event_id,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', timestamp_utc) AS event_timestamp,
    DATE(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', timestamp_utc))    AS event_date,
    EXTRACT(HOUR FROM PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', timestamp_utc)) AS event_hour,
    provider,
    model,
    CONCAT(provider, '/', model) AS provider_model,
    team,
    feature,
    NULLIF(experiment_id, '') AS experiment_id,
    environment,
    status,
    NULLIF(error_code, '')    AS error_code,
    NULLIF(finish_reason, '') AS finish_reason,
    prompt_tokens,
    completion_tokens,
    cached_tokens,
    GREATEST(prompt_tokens - cached_tokens, 0) AS billed_prompt_tokens,
    prompt_cost_usd,
    completion_cost_usd,
    total_cost_usd,
    latency_ms,
    time_to_first_token_ms,
    (status = 'error')    AS is_error,
    (cached_tokens > 0)   AS has_cache_hit
FROM {{ source('llm_finops_raw', 'llm_usage_events') }}
WHERE event_id IS NOT NULL
  AND timestamp_utc IS NOT NULL
