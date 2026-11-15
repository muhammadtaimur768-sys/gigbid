# clausewise

Small, production-tested service extracted from client work (legal). It exists because paralegals copied renewal dates and liability caps out of contracts by hand.

## Features

- Ner-based core to pull entities and intents out of free text
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Used in production by one client; PRs welcome.
