import asyncio
import json
from ihale_client import EKAPClient


async def callAPI():
    ekap_client = EKAPClient()
    page_size = 10
    skip = 0
    page = 1
    all_tenders = []

    while True:
        result = await ekap_client.search_tenders(
            authority_ids=[2529, 35108],
            tender_statuses=[5],
            tender_types=[2],
            skip=skip,
            limit=page_size,
        )

        returned_count = result.get("returned_count", 0)
        total_count = result.get("total_count", 0)
        tenders = result.get("tenders", [])
        all_tenders.extend(tenders)

        print(f"Page {page}: skip={skip}, returned_count={returned_count}, total_count={total_count}")

        if returned_count < page_size:
            break

        skip += page_size
        page += 1

    print(f"Total tenders fetched: {len(all_tenders)}")

    detailed_tenders = []
    for idx, tender in enumerate(all_tenders, start=1):
        tender_id = tender.get("id")
        if not tender_id:
            continue
        print(f"Fetching details {idx}/{len(all_tenders)} (id={tender_id})")
        details = await ekap_client.get_tender_details_raw(tender_id=tender_id)
        detailed_tenders.append(details)

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