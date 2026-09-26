"""
One-off debug script: fetches a handful of REAL, RECENT tickets and
prints ONLY field names/structure for status/category/priority/time
fields, plus the ticket id. Deliberately does NOT print subject,
description, or requester fields, since those contain real ticket
content and personal details that aren't needed to fix a field-name
mapping bug.

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
                    "sort_field": "created_time",
                    "sort_order": "desc",  # most recent tickets, more likely fully triaged
                    "fields_required": [
                        "priority",
                        "category",
                        "subcategory",
                        "status",
                        "created_time",
                        "due_by_time",
                        "resolved_time",
                        "completed_time",
                    ],
                }
            }
        )
    },
    timeout=30,
)
response.raise_for_status()
tickets = response.json().get("requests", [])

print(f"Fetched {len(tickets)} recent tickets.\n")

for t in tickets:
    print(f"--- ticket id: {t.get('id')} ---")
    print("Top-level field names present:", sorted(t.keys()))
    for field in ["status", "category", "subcategory", "priority", "created_time", "due_by_time", "completed_time", "resolved_time"]:
        if field in t:
            print(f"  {field}: {json.dumps(t[field])}")
        else:
            print(f"  {field}: <not present>")
    print()
