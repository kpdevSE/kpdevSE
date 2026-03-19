import os
import re
import requests
import sys
from datetime import datetime, timezone

USERNAME = "kpdevSE"
token = os.environ.get("GITHUB_TOKEN")

# Validate token
if not token:
    print("Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# Fetch recent events (includes private if token has repo scope)
url = f"https://api.github.com/users/{USERNAME}/events?per_page=100"

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    events = response.json()
except requests.exceptions.HTTPError as e:
    print(f"HTTP error fetching GitHub events: {e}", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.ConnectionError:
    print("Error: Could not connect to GitHub API. Check your internet connection.", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"Error fetching events from GitHub API: {e}", file=sys.stderr)
    sys.exit(1)

# Check rate limit
remaining = int(response.headers.get("X-RateLimit-Remaining", 60))
print(f"GitHub API rate limit remaining: {remaining}")
if remaining < 5:
    print("Warning: GitHub API rate limit almost exceeded.", file=sys.stderr)

# Build commit lines
lines = []

for event in events:
    if event.get("type") != "PushEvent":
        continue

    repo = event["repo"]["name"]
    commits = event["payload"].get("commits", [])

    for commit in commits[:2]:  # max 2 commits per push event
        msg = commit["message"].splitlines()[0]  # first line only
        # Truncate long messages
        msg = msg[:60] + "..." if len(msg) > 60 else msg
        # Escape any characters that could break markdown/regex
        msg = msg.replace("|", "\\|").replace("`", "'")
        lines.append(f"- 📦 `{repo}` → {msg}")

    if len(lines) >= 5:  # show last 5 commits total
        break

if not lines:
    lines = ["- No recent public commits found."]

# Add last updated timestamp (timezone-safe)
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lines.append(f"\n⏰ _Last updated: {timestamp}_")

new_content = "\n".join(lines)

# Read README
readme_path = "README.md"

if not os.path.exists(readme_path):
    print(f"Error: {readme_path} not found in current directory.", file=sys.stderr)
    sys.exit(1)

try:
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
except IOError as e:
    print(f"Error reading {readme_path}: {e}", file=sys.stderr)
    sys.exit(1)

# Replace content between placeholder comments
pattern = r"<!--RECENT_ACTIVITY:start-->.*?<!--RECENT_ACTIVITY:end-->"

if not re.search(pattern, readme, flags=re.DOTALL):
    print(
        "Warning: Placeholder comments not found in README.\n"
        "Make sure your README contains:\n"
        "  <!--RECENT_ACTIVITY:start-->\n"
        "  <!--RECENT_ACTIVITY:end-->",
        file=sys.stderr
    )
    sys.exit(1)

updated = re.sub(
    pattern,
    f"<!--RECENT_ACTIVITY:start-->\n{new_content}\n<!--RECENT_ACTIVITY:end-->",
    readme,
    flags=re.DOTALL
)

try:
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"Done! README updated with {len(lines) - 1} recent commits for {USERNAME}.")
except IOError as e:
    print(f"Error writing to {readme_path}: {e}", file=sys.stderr)
    sys.exit(1)