# model-hangar

Small, production-tested service extracted from client work (logistics). It exists because models were retrained by hand on a laptop and nobody knew which version was live.

## Features

- Mlflow-based core to track experiments and monitor drift after launch
- K8s-based core to run the inference fleet with autoscaling
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Used in production by one client; PRs welcome.
