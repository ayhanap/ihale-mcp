import asyncio
import json
from ihale_client import EKAPClient


async def callAPI():
    ekap_client = EKAPClient()
    page_size = 10
    concurrency = 10
    search_sem = asyncio.Semaphore(concurrency)

    async def fetch_page(skip: int):
        async with search_sem:
            return await ekap_client.search_tenders(
                authority_ids=[2529, 35108],
                tender_statuses=[5],
                tender_types=[2],
                tender_date_start="2025-01-01",
                skip=skip,
                limit=page_size,
            )

    def log_page(skip: int, result):
        page_number = skip // page_size + 1
        returned_count = result.get("returned_count", 0)
        print(f"Page {page_number}: returned_count={returned_count}")
        if returned_count == 0:
            print(f"WARNING: Page {page_number} returned 0 results. Full response:")
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    # First page tells us the total so we can fan out the rest.
    first = await fetch_page(0)
    log_page(0, first)
    total_count = first.get("total_count", 0)
    print(f"total_count={total_count}")
    all_tenders = list(first.get("tenders", []))

    if total_count > page_size:
        skips = list(range(page_size, total_count, page_size))
        # Process pages in ordered batches so earlier pages are requested first.
        for i in range(0, len(skips), concurrency):
            batch = skips[i:i + concurrency]
            results = await asyncio.gather(*(fetch_page(s) for s in batch))
            for skip, page_result in zip(batch, results):
                log_page(skip, page_result)
                all_tenders.extend(page_result.get("tenders", []))

    print(f"Total tenders fetched: {len(all_tenders)}")

    detail_sem = asyncio.Semaphore(concurrency)
    total = len(all_tenders)

    async def fetch_one(idx: int, tender_id: str):
        async with detail_sem:
            print(f"Fetching details {idx}/{total} (id={tender_id})")
            return await ekap_client.get_tender_details_raw(tender_id=tender_id)

    tasks = [
        fetch_one(idx, tender["id"])
        for idx, tender in enumerate(all_tenders, start=1)
        if tender.get("id")
    ]
    detailed_tenders = await asyncio.gather(*tasks)

    print(f"Total details fetched: {len(detailed_tenders)}")
    output_path = "detailed_tenders.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(detailed_tenders, f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote JSON to {output_path}")


def main():
    print("Hello from ihale-mcp!")
    asyncio.run(callAPI())


if __name__ == "__main__":
    main()