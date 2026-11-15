# dedupe-crm

Small, production-tested service extracted from client work (wholesale). It exists because a third of the CRM records were duplicates.

## Features

- Data wrangling-based core to fix duplicates and broken dates
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Used in production by one client; PRs welcome.
