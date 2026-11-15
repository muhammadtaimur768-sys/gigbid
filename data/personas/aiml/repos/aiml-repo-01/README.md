# doc-sieve

Small, production-tested service extracted from client work (insurance). It exists because adjusters spent the first hour of every claim reading PDFs to decide who should handle it.

## Features

- Retrieval augmented generation-based core to ground answers in the client's own documents
- Py-based core to glue the data pipeline and model code together
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Used in production by one client; PRs welcome.
