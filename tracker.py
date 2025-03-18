import requests
from datetime import datetime, timezone
import json

# Sky Mavis API endpoint
API_URL = "https://marketplace-graphql.skymavis.com/graphql"

HEADERS = {
    "accept": "*/*",
    "authorization": "######",  # Replace with your actual token
    "cache-control": "no-cache",
    "content-type": "application/json",
}

query = """
query GetLaunchpadSales($saleState: SaleState!, $size: Int!, $from: Int!) {
    mavisSales(saleState: $saleState, from: $from, size: $size) {
        sales {
            ... on LaunchpadData {
                nftContract
                launchpadSupply
                minted
                launchpadStages {
                    stageIndex
                    stageType
                    startTime
                    endTime
                    mintPrice
                    currency
                    launchpadStageMetadata
                    isAllowListAdded
                }
                creatorInfo {
                    creatorName
                    verified
                }
            }
        }
    }
}
"""

PAYLOAD = {
    "operationName": "GetLaunchpadSales",
    "variables": {
        "saleState": "LiveAndUpcoming",
        "from": 0,
        "size": 30,
    },
    "query": query
}


def fetch_nft_sales():
    try:
        response = requests.post(API_URL, headers=HEADERS, json=PAYLOAD)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("mavisSales", {}).get("sales", [])
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return []


def process_nft_launch_data():
    print("Fetching NFT Launchpad Sales Data...\n")

    # Fetch the sales data
    sales = fetch_nft_sales()

    # Print the full API response for debugging
    print("\n🔍 Full API Response (Formatted):")
    print(json.dumps(sales, indent=4))

    # Process the sales data
    if sales:
        for sale in sales:
            nft_contract = sale.get("nftContract")
            stages = sale.get("launchpadStages", [])
            creator_info = sale.get("creatorInfo", {})
            creator = creator_info.get("creatorName", "Unknown")

            if nft_contract:
                # Iterate through each launchpad stage
                print("\tLaunchpad Sale Details")
                print("=====================================")
                for stage in stages:
                    print("=====================================")
                    stage_index = stage.get("stageIndex")
                    stage_type = stage.get("stageType")
                    start_time = stage.get("startTime")
                    end_time = stage.get("endTime")
                    mint_price = stage.get("mintPrice")
                    currency = stage.get("currency")
                    stage_metadata = stage.get("launchpadStageMetadata", {})
                    stage_name = stage_metadata.get("stage_name", "Unknown")
                    is_allowlist_added = stage.get("isAllowListAdded", False)

                    # Convert start_time and end_time from Unix timestamp to a readable format
                    start_time = datetime.fromtimestamp(int(start_time), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if start_time else "Not Available"
                    end_time = datetime.fromtimestamp(int(end_time), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if end_time else "Not Available"
                    
                    # Mint Price Conversion (Assuming it's in wei, converting to RON)
                    mint_price_eth = float(mint_price) / 10**18 if mint_price else 0

                    # Output the details for each stage
                    print(f"\nStage Index: {stage_index}")
                    print(f"  Stage Type: {stage_type}")
                    print(f"  Stage Name: {stage_name}")
                    print(f"  Start Time: {start_time}")
                    print(f"  End Time: {end_time}")
                    print(f"  Mint Price: {mint_price_eth} RON")
                    print(f"  Currency: {currency}")
                    print(f"  Allowlist Added: {is_allowlist_added}")
                    print(f"  Creator: {creator}")
            print("=====================================")
    else:
        print("No sales data found.")


def start_tracker():
    process_nft_launch_data()


if __name__ == "__main__":
    start_tracker()
