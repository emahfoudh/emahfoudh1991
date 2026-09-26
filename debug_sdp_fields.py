"""
One-off debug script: checks the API response's metadata (list_info,
response_status envelope) to see if a default filter/view is limiting
results to open tickets only. Prints NO ticket content - only counts
and metadata about the request/response itself.

Delete this file once the mapping is fixed - it's a diagnostic tool,
not part of the pipeline.
"""

import json

from dotenv import load_dotenv

load_dotenv()

from connectors.manageengine_sdp import ManageEngineSDPConnector

import requests

sdp = ManageEngineSDPConnector()
sdp.authenticate()

response = requests.get(
    f"{sdp.api_domain}/api/v3/requests",
    headers=sdp._headers(),
    params={
        "input_data": json.dumps(
            {
                "list_info": {
                    "row_count": 5,
                    "start_index": 1,
                    "get_total_count": True,
                }
            }
        )
    },
    timeout=30,
)
response.raise_for_status()
body = response.json()

print("Top-level response keys:", sorted(body.keys()))
print()
if "list_info" in body:
    print("list_info (echoed back by the API):")
    print(json.dumps(body["list_info"], indent=2))
print()
if "response_status" in body:
    print("response_status:", json.dumps(body["response_status"], indent=2))

print()
print(f"Number of tickets in this page: {len(body.get('requests', []))}")

# Print just the status of each ticket in this small page, to see the
# actual variety of status values without any other ticket content.
statuses_seen = [t.get("status", {}).get("name") for t in body.get("requests", [])]
print("Status names in this page:", statuses_seen)
