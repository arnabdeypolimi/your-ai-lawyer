Build or update the vector search index for the legal knowledge base.

Run the following command:

```bash
uv run python -m src.indexer.embed $ARGUMENTS
```

Default usage: `/index` indexes Spain (es) compiled notes and raw law chunks.
Pass `--country fr` for another country, or `--compiled-only` / `--raw-only` to index a subset.

Report how many documents were indexed in the `compiled` and `raw_chunks` collections.
