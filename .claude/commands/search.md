Search the legal knowledge base and return matching laws.

Run the following command and display the results:

```bash
uv run python -m src.query.search $ARGUMENTS
```

You can pass flags like `--country es`, `--rank ley`, `--n 10`.
Example: `/search housing rights --country es --n 10`

Display results clearly showing: law identifier, title, jurisdiction, relevance score, and a text excerpt.
