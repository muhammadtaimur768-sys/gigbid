# nightly-sync

Small, production-tested service extracted from client work (insurance). It exists because reports used week-old CSV exports.

## Features

- Etl-based core to move data from the CRM into the warehouse nightly
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Maintained.
