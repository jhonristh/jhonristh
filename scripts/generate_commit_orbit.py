"""
Generates assets/commit-orbit.svg — a custom-styled contribution heatmap
("Commit Orbit Map") using real data from the GitHub GraphQL API.

Why this exists (Phase 1 decision "b"):
GitHub README SVGs are static files — they cannot fetch live data at render
time. To get a fully custom-styled heatmap (not a fixed third-party badge),
this script must run on a schedule via GitHub Actions and commit the
regenerated SVG back to the repo, the same pattern the contribution-snake
action uses.

Requires:
  - env var GH_TOKEN (a token with `read:user` scope; the default
    GITHUB_TOKEN in Actions works for public contribution data)
  - env var GH_USERNAME (your GitHub username)

Usage:
  GH_TOKEN=... GH_USERNAME=... python scripts/generate_commit_orbit.py
"""

import os
import json
import datetime
import urllib.request

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

# Energy-cell color ramp — matches the Phase 1 palette (green = energy).
LEVELS = ["#10151c", "#1c3326", "#2f5c3f", "#4d9e6a", "#7fe6a0"]


def fetch_calendar(username: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def level_for(count: int, max_count: int) -> int:
    if count == 0 or max_count == 0:
        return 0
    ratio = count / max_count
    if ratio > 0.75:
        return 4
    if ratio > 0.5:
        return 3
    if ratio > 0.25:
        return 2
    return 1


def compute_streaks(days: list) -> tuple[int, int]:
    longest = current = 0
    running = 0
    today = datetime.date.today()
    for d in days:
        if d["contributionCount"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    # current streak: walk backwards from today
    running = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            running += 1
        else:
            break
    current = running
    return current, longest


def render_svg(calendar: dict) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    all_days = [d for w in weeks for d in w["contributionDays"]]
    max_count = max((d["contributionCount"] for d in all_days), default=0)
    current_streak, longest_streak = compute_streaks(all_days)

    cell = 11
    gap = 3
    x0, y0 = 20, 30

    cells_svg = []
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            lvl = level_for(day["contributionCount"], max_count)
            x = x0 + wi * (cell + gap)
            y = y0 + di * (cell + gap)
            delay = (wi * 7 + di) * 0.01
            cells_svg.append(
                f'<rect class="cell" x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{LEVELS[lvl]}" style="animation-delay:{delay:.2f}s"/>'
            )

    width = x0 * 2 + len(weeks) * (cell + gap)
    height = 220

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg {{ fill: #05070a; }}
    .label {{ font-family: 'Courier New', monospace; font-size: 12px; fill: #9fb3ad; }}
    .stat {{ font-family: 'Courier New', monospace; font-size: 16px; fill: #7fe6a0; font-weight: bold; }}
    .cell {{ animation: glow 3s ease-in-out infinite; }}
    @keyframes glow {{
      0%, 100% {{ opacity: 0.75; }}
      50% {{ opacity: 1; }}
    }}
  </style>
  <rect class="bg" width="{width}" height="{height}" rx="10"/>
  <text x="20" y="18" class="label" letter-spacing="3">COMMIT ORBIT MAP</text>
  {''.join(cells_svg)}
  <text x="20" y="195" class="label">TOTAL CONTRIBUTIONS</text>
  <text x="20" y="215" class="stat">{total}</text>
  <text x="230" y="195" class="label">CURRENT STREAK</text>
  <text x="230" y="215" class="stat">{current_streak}d</text>
  <text x="400" y="195" class="label">LONGEST STREAK</text>
  <text x="400" y="215" class="stat">{longest_streak}d</text>
</svg>"""


def main():
    username = os.environ["GH_USERNAME"]
    token = os.environ["GH_TOKEN"]
    calendar = fetch_calendar(username, token)
    svg = render_svg(calendar)
    out_path = os.path.join(os.path.dirname(__file__), "..", "assets", "commit-orbit.svg")
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
