"""Manually assign a Free or Pro plan while billing is disabled."""

import argparse
from datetime import datetime, timezone

from pymongo import MongoClient

from dataviz.config import Config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email", help="Account email address")
    parser.add_argument("plan", choices=("free", "pro"))
    arguments = parser.parse_args()

    email = arguments.email.strip().lower()
    client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=10000)
    try:
        database = client[Config.MONGO_DB_NAME]
        result = database.users.update_one(
            {"email": email},
            {
                "$set": {
                    "plan": arguments.plan,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count != 1:
            raise SystemExit(f"No account found for {email}.")
        print(f"Updated {email} to the {arguments.plan} plan.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
