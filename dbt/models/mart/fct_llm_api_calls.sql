{{
    config(
        unique_key = 'event_id',
        incremental_strategy = 'merge'
    )
}}

SELECT
    event_id,
    event_timestamp,
    event_date,
    event_hour,
    provider,
    model,
    provider_model,
    team,
    feature,
    experiment_id,
    environment,
    status,
    error_code,
    finish_reason,
    prompt_tokens,
    completion_tokens,
    cached_tokens,
    billed_prompt_tokens,
    prompt_cost_usd,
    completion_cost_usd,
    total_cost_usd,
    latency_ms,
    time_to_first_token_ms,
    is_error,
    has_cache_hit
FROM {{ ref('stg_llm_usage_events') }}
{% if is_incremental() %}
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)
{% endif %}
