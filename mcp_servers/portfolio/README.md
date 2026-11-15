# gigbid-portfolio-mcp

A read-only MCP server that turns a freelancer portfolio (case studies, repos, past proposals, client
reviews, CV) into evidence an agent can cite. Built on the official MCP Python SDK (FastMCP).

## Tools

| Tool | What it does |
|---|---|
| `search_evidence(requirement, k=5, filters=None, persona=None)` | Best evidence for one job requirement. Each item has `item_id`, `type`, `source`, `date`, `outcome`, `score`, `text`. Filters: `type`, `outcome`, `skills`, `client_industry`, `project`. |
| `get_case_study(id)` | Full text and metadata of one item. |
| `list_skills()` | Skills found in the portfolio with the number of items that back each one. |

All tools are annotated `readOnlyHint=true, destructiveHint=false, idempotentHint=true` and return
structured output with a declared output schema.

**Resources:** `portfolio://case/{id}`, `portfolio://proposal/{id}`, `portfolio://repo/{id}`, `portfolio://items`.

**Prompts:** *Answer a screening question from my portfolio*, *Find proof for each job requirement*,
*Draft a proposal opening from my best evidence*, *Check my skills against a job post*.

## Run with uvx

```bash
uvx --from "git+https://github.com/muhammadtaimur768-sys/gigbid#subdirectory=mcp_servers/portfolio" \
    gigbid-portfolio-mcp --data-dir /path/to/portfolios --persona me
```

stdio is the default. `--http --port 8201` serves Streamable HTTP; HTTP requests need
`Authorization: Bearer $MCP_PORTFOLIO_TOKEN`.

## Add it to any MCP host (Cursor, VS Code, or another MCP-capable client)

```json
{
  "mcpServers": {
    "gigbid-portfolio": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/muhammadtaimur768-sys/gigbid#subdirectory=mcp_servers/portfolio",
               "gigbid-portfolio-mcp"],
      "env": { "PORTFOLIO_DATA_DIR": "/path/to/portfolios", "PORTFOLIO_PERSONA": "me" }
    }
  }
}
```

## Portfolio folder layout

```
<PORTFOLIO_DATA_DIR>/<persona>/
  profile.json                {name, title, skills[], ...}
  cv.md
  case_studies/<id>.md        frontmatter: id, title, project, skills[], date, client_industry, outcome
  repos/<id>/README.md        plus code files (.py .ts .sql ...), which are searched too
  reviews.json                [{id, client, rating, text, project, date}]
  proposals.jsonl             {id, job_title, skills[], text, outcome: won|replied|ignored, date}
```

## Search backends

`PORTFOLIO_BACKEND=auto` (default) uses the GigBid hybrid retriever (`rag.retriever`) when the package
runs inside the GigBid repo, and otherwise a built-in TF-IDF keyword search with no extra dependencies.
Force one with `rag` or `keyword`.

| Env | Default | Meaning |
|---|---|---|
| `PORTFOLIO_DATA_DIR` | nearest `data/personas` folder | folder holding persona folders |
| `PORTFOLIO_PERSONA` | `aiml` | default persona |
| `PORTFOLIO_BACKEND` | `auto` | `auto`, `rag` or `keyword` |
| `MCP_PORTFOLIO_TOKEN` | development token | bearer token for `--http` |
