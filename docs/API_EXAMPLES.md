# API examples

Base URL: `http://localhost:8000/api/v1` (direct) or `/api/v1` through nginx.

```bash
API=http://localhost:8000/api/v1
```

## Health and catalog

```bash
curl -s $API/health
curl -s $API/ready | python -m json.tool
curl -s $API/catalog | python -m json.tool
```

## Create a system from the catalog

```bash
SYSTEM_ID=$(curl -s -X POST $API/systems \
  -H 'Content-Type: application/json' \
  -d '{"source":{"type":"catalog","catalog_id":"ball_beam"}}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["system_id"])')
```

## Manual simulation

```bash
curl -s $API/systems/$SYSTEM_ID/schema?controller_type=PID | python -m json.tool

curl -s -X POST $API/systems/$SYSTEM_ID/simulate \
  -H 'Content-Type: application/json' \
  -d '{
    "controller_type":"PID",
    "params":{"Kp":15.0,"Ki":0.5,"Kd":2.0},
    "overrides":{"dt":0.01,"max_time":1.0}
  }' | python -m json.tool
```

Reopen persisted runs:

```bash
curl -s "$API/systems/$SYSTEM_ID/simulations?limit=10&offset=0"
curl -s "$API/simulations/<run_id>?include_artifacts=true"
```

## Synchronous GA optimization

```bash
curl -s -X POST $API/systems/$SYSTEM_ID/optimize \
  -H 'Content-Type: application/json' \
  -d '{"ga_config":{"population_size":5,"generations":2,"seed":42,"max_wall_clock":30}}' \
  | python -m json.tool
```

## Asynchronous GA optimization

```bash
curl -s -X POST $API/systems/$SYSTEM_ID/optimize \
  -H 'Content-Type: application/json' \
  -d '{
    "async":true,
    "ga_config":{"population_size":5,"generations":2,"seed":42,"max_wall_clock":30}
  }' | python -m json.tool
```

Poll:

```bash
curl -s $API/jobs/<job_id> | python -m json.tool
```

Stream progress with SSE (`-N` disables buffering):

```bash
curl -N $API/jobs/<job_id>/events
```

Reconnect replay using the last SSE event id:

```bash
curl -N -H 'Last-Event-ID: 1793646200353-1' $API/jobs/<job_id>/events
```

Cancel (idempotent while active):

```bash
curl -s -X POST $API/jobs/<job_id>/cancel | python -m json.tool
```

## Errors

All errors use the same envelope:

```json
{"error":{"code":"validation_error","message":"Request payload failed schema validation.","context":{}}}
```

Common codes: `system_not_found`, `run_not_found`, `job_not_found`,
`capability_not_supported`, `optimization_in_progress`, `system_in_use`, `job_not_cancellable`,
`job_queue_full`, `payload_too_large`, `engine_error`, `service_not_ready`.
