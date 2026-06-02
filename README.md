## How to Run

```
uv run --with-requirements requirements.txt python main.py \
  --authority-ids 2529 35108 \
  --tender-statuses 5 \
  --tender-types 2 \
  --tender-date-start 2025-01-01 \
  --tender-date-end 2025-12-31 \
  --concurrency 10 \
  --page-size 10 \
  -o tenders.json
```

tender-date-end defaults to empty others are as shown above.

## Help to print arguement

```
uv run --with-requirements requirements.txt python main.py --help
```