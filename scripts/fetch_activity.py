"""Refreshes data/contributions.json and data/stats.json from the GitHub API.

Run by .github/workflows/refresh.yml with the workflow's GITHUB_TOKEN:
    GITHUB_TOKEN=... python scripts/fetch_activity.py joshsssn
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
weeks{contributionDays{date contributionCount}}}}}}"""


def call(url, payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None,
                                 headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main(login):
    data = call("https://api.github.com/graphql", {"query": QUERY, "variables": {"login": login}})
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    path = ROOT / "data/contributions.json"
    contrib = json.loads(path.read_text()) if path.exists() else {}
    for w in weeks:
        for day in w["contributionDays"]:
            if day["contributionCount"]:
                contrib[day["date"]] = day["contributionCount"]
            else:
                contrib.pop(day["date"], None)
    path.write_text(json.dumps(dict(sorted(contrib.items())), indent=0) + "\n")

    user = call(f"https://api.github.com/users/{login}")
    stats = {"public_repos": user["public_repos"], "as_of": dt.date.today().isoformat()}
    (ROOT / "data/stats.json").write_text(json.dumps(stats) + "\n")
    print(f"{len(contrib)} active days, {stats['public_repos']} public repos")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "joshsssn")
