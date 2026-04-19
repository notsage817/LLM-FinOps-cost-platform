# generate_llm_events.py

import os, json, uuid, random, math
from datetime import datetime, timezone, timedelta
from confluent_kafka import Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC     = os.getenv("KAFKA_TOPIC", "llm.usage.events")

_conf = {"bootstrap.servers": BOOTSTRAP}
if os.getenv("KAFKA_USERNAME"):
    _conf.update({
        "security.protocol": "SASL_SSL",
        "sasl.mechanism":    "SCRAM-SHA-256",
        "sasl.username":     os.getenv("KAFKA_USERNAME"),
        "sasl.password":     os.getenv("KAFKA_PASSWORD"),
    })

def _on_delivery(err, msg):
    if err:
        print(f"Send failed [{msg.topic()}]: {err}")

try:
    producer = Producer(_conf)
except Exception as e:
    raise SystemExit(f"Failed to create producer for {BOOTSTRAP}: {e}")

# ── Pricing table (mirrors your dbt seed) ──────────────────────────────────
PRICING = {
    ("openai",    "gpt-4o"):             (0.005,   0.015),
    ("openai",    "gpt-4o-mini"):        (0.00015, 0.0006),
    ("anthropic", "claude-haiku-4-5"):   (0.00025, 0.00125),
    ("anthropic", "claude-sonnet-4-6"):  (0.003,   0.015),
    ("google",    "gemini-1.5-flash"):   (0.000075,0.0003),
    ("google",    "gemini-1.5-pro"):     (0.00125, 0.005),
}

# ── Team definitions ────────────────────────────────────────────────────────
# Each team has: call volume, preferred models, prompt size, feature names
TEAMS = {
    "search-relevance": {
        "daily_calls":    (400, 600),
        "models":         [("openai","gpt-4o-mini",0.8), ("openai","gpt-4o",0.2)],
        "prompt_tokens":  (300, 900),
        "completion_tokens": (80, 200),
        "features":       ["query-expansion", "intent-classification", "spell-correction"],
        "experiments":    ["baseline", "exp-semantic-v1", "exp-semantic-v2"],
        "exp_weights":    [0.4, 0.3, 0.3],
        "error_rate":     0.02,
        "cache_rate":     0.35,   # high cache — similar queries repeat
    },
    "recommendations": {
        "daily_calls":    (600, 900),
        "models":         [("openai","gpt-4o",0.5), ("anthropic","claude-sonnet-4-6",0.5)],
        "prompt_tokens":  (800, 2000),
        "completion_tokens": (150, 400),
        "features":       ["product-description", "personalized-email", "upsell-copy"],
        "experiments":    ["baseline", "exp-tone-formal", "exp-tone-casual"],
        "exp_weights":    [0.5, 0.25, 0.25],
        "error_rate":     0.01,
        "cache_rate":     0.05,   # low cache — personalized content, rarely repeats
    },
    "customer-support": {
        "daily_calls":    (200, 350),
        "models":         [("anthropic","claude-haiku-4-5",0.7), ("openai","gpt-4o-mini",0.3)],
        "prompt_tokens":  (500, 1500),
        "completion_tokens": (200, 600),
        "features":       ["ticket-classification", "response-draft", "sentiment-analysis"],
        "experiments":    ["baseline", "exp-concise-replies"],
        "exp_weights":    [0.6, 0.4],
        "error_rate":     0.03,
        "cache_rate":     0.15,
    },
    "data-science": {
        "daily_calls":    (80, 150),
        "models":         [("google","gemini-1.5-pro",0.4), ("openai","gpt-4o",0.6)],
        "prompt_tokens":  (2000, 8000),   # large prompts — data analysis
        "completion_tokens": (400, 1200),
        "features":       ["data-summarization", "schema-inference", "sql-generation"],
        "experiments":    ["baseline"],
        "exp_weights":    [1.0],
        "error_rate":     0.05,   # exploratory usage — more errors
        "cache_rate":     0.02,
    },
}

# ── Realistic hourly traffic pattern ───────────────────────────────────────
# Business hours peak, quiet at night — mirrors real usage
def hourly_weight(hour):
    # Gaussian centered at 14:00 UTC (9am EST), flat overnight
    weight = math.exp(-0.5 * ((hour - 14) / 4) ** 2)
    return max(0.05, weight)   # minimum 5% traffic overnight

HOUR_WEIGHTS = [hourly_weight(h) for h in range(24)]

def pick_hour():
    return random.choices(range(24), weights=HOUR_WEIGHTS)[0]

# ── Single event generator ─────────────────────────────────────────────────
def generate_event(team_name: str, timestamp: datetime) -> dict:
    team = TEAMS[team_name]

    provider, model, _ = random.choices(
        [(p, m, w) for p, m, w in team["models"]],
        weights=[w for _, _, w in team["models"]]
    )[0]

    prompt_tokens     = int(random.uniform(*team["prompt_tokens"]))
    completion_tokens = int(random.uniform(*team["completion_tokens"]))
    cached_tokens     = min(int(prompt_tokens * random.uniform(0, team["cache_rate"] * 2)), prompt_tokens)

    billed_prompt = prompt_tokens - cached_tokens
    p_cost, c_cost = PRICING[(provider, model)]
    prompt_cost     = round((billed_prompt     / 1000) * p_cost, 8)
    completion_cost = round((completion_tokens / 1000) * c_cost, 8)

    is_error = random.random() < team["error_rate"]

    # Rate-limit errors are rejected at handshake; full-token latency only on success
    if is_error:
        latency_ms = random.randint(10, 50)
        time_to_first_token_ms = 0
    else:
        base_latency = 300 + (prompt_tokens + completion_tokens) * 0.4
        latency_ms   = int(random.gauss(base_latency, base_latency * 0.2))
        time_to_first_token_ms = int(latency_ms * random.uniform(0.15, 0.30))

    experiment = random.choices(team["experiments"], weights=team["exp_weights"])[0]

    return {
        "event_id":               str(uuid.uuid4()),
        "timestamp_utc":          timestamp.isoformat(),
        "provider":               provider,
        "model":                  model,
        "prompt_tokens":          prompt_tokens,
        "completion_tokens":      0 if is_error else completion_tokens,
        "cached_tokens":          cached_tokens,
        "prompt_cost_usd":        0.0 if is_error else prompt_cost,
        "completion_cost_usd":    0.0 if is_error else completion_cost,
        "total_cost_usd":         0.0 if is_error else round(prompt_cost + completion_cost, 8),
        "latency_ms":             latency_ms,
        "time_to_first_token_ms": time_to_first_token_ms,
        "team":                   team_name,
        "feature":                random.choice(team["features"]),
        "experiment_id":          experiment,
        "environment":            "production",
        "status":                 "error" if is_error else "success",
        "error_code":             "rate_limit_exceeded" if is_error else None,
        "finish_reason":          None if is_error else "stop",
    }

# ── Bulk historical generation ─────────────────────────────────────────────
def generate_history(days: int = 30):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0

    for day_offset in range(days):
        current_day = start + timedelta(days=day_offset)

        # Weekends have ~40% of weekday traffic
        is_weekend = current_day.weekday() >= 5
        day_multiplier = 0.4 if is_weekend else 1.0

        daily_events = []
        for team_name, team in TEAMS.items():
            daily_calls = int(random.randint(*team["daily_calls"]) * day_multiplier)
            for _ in range(daily_calls):
                hour   = pick_hour()
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                ts     = current_day.replace(hour=hour, minute=minute, second=second)
                daily_events.append(generate_event(team_name, ts))

        # Produce in chronological order so downstream watermarks are correct
        daily_events.sort(key=lambda x: x["timestamp_utc"])
        for event in daily_events:
            producer.produce(TOPIC, value=json.dumps(event).encode(), on_delivery=_on_delivery)
        producer.poll(0)
        total += len(daily_events)

        if (day_offset + 1) % 10 == 0:
            producer.flush()
            print(f"  Day {day_offset + 1}/{days} done — {total:,} events so far")

    producer.flush()
    print(f"\nDone. {total:,} events published across {days} days.")

if __name__ == "__main__":
    print("Generating 30 days of synthetic LLM usage events...")
    generate_history(days=30)
