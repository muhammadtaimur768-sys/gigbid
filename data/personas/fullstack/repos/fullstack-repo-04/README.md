# shipyard

Small, production-tested service extracted from client work (fintech). It exists because deploys were done by SSH-ing into a server on Friday nights.

## Features

- Containers-based core to make local and production environments match
- Ci/cd-based core to ship every merged pull request automatically
- Config via environment variables
- Tests for the main paths

## Quickstart

```bash
make install
make run
```

## Status

Maintained.
