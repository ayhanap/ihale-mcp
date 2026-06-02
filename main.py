import argparse
import asyncio
import json
from ihale_client import EKAPClient


async def callAPI(args):
    ekap_client = EKAPClient()
    page_size = args.page_size
    concurrency = args.concurrency
    search_sem = asyncio.Semaphore(concurrency)

    async def fetch_page(skip: int):
        async with search_sem:
            return await ekap_client.search_tenders(
                authority_ids=args.authority_ids or None,
                tender_statuses=args.tender_statuses or None,
                tender_types=args.tender_types or None,
                tender_date_start=args.tender_date_start,
                tender_date_end=args.tender_date_end,
                announcement_date_start=args.announcement_date_start,
                announcement_date_end=args.announcement_date_end,
                search_text=args.search_text,
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

    if args.skip_details:
        detailed_tenders = all_tenders
    else:
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

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(detailed_tenders, f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote JSON to {args.output}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Search Turkish government tenders (EKAP v2) and dump details to JSON."
    )
    parser.add_argument("--authority-ids", type=int, nargs="*", default=[2529,35108],
                        help="Authority (idare) IDs to filter by, space-separated.")
    parser.add_argument("--tender-statuses", type=int, nargs="*", default=[5],
                        help="Tender status IDs to filter by.")
    parser.add_argument("--tender-types", type=int, nargs="*", default=[2],
                        help="Tender type IDs to filter by.")
    parser.add_argument("--tender-date-start", default='2025-01-01',
                        help="Tender date start (YYYY-MM-DD).")
    parser.add_argument("--tender-date-end", default=None,
                        help="Tender date end (YYYY-MM-DD).")
    parser.add_argument("--announcement-date-start", default=None,
                        help="Announcement date start (YYYY-MM-DD).")
    parser.add_argument("--announcement-date-end", default=None,
                        help="Announcement date end (YYYY-MM-DD).")
    parser.add_argument("--search-text", default="",
                        help="Free text search.")
    parser.add_argument("--page-size", type=int, default=10,
                        help="Results per page (default: 10).")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="Max concurrent requests (default: 10).")
    parser.add_argument("--skip-details", action="store_true",
                        help="Skip per-tender detail fetching; output search results only.")
    parser.add_argument("-o", "--output", default="detailed_tenders.json",
                        help="Output JSON file (default: detailed_tenders.json).")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(callAPI(parse_args()))
