#!/usr/bin/env python3
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def main():
    readme_path = Path(__file__).parent.parent / "README.md"
    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}", file=sys.stderr)
        sys.exit(1)

    is_push = "--push" in sys.argv

    # 1. Get latest commit timestamp
    try:
        commit_ts_res = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            check=True
        )
        latest_commit_ts = int(commit_ts_res.stdout.strip())
    except Exception as e:
        print(f"Error reading latest commit time: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Get target timestamp to write to README
    if is_push:
        target_ts = latest_commit_ts
    else:
        target_ts = int(datetime.now(timezone.utc).timestamp())
        
    target_time_str = datetime.fromtimestamp(target_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Calculate cumulative development hours from git log
    try:
        result = subprocess.run(
            ["git", "log", "--format=%ct"],
            capture_output=True,
            text=True,
            check=True
        )
        timestamps = sorted([int(ts) for ts in result.stdout.strip().split("\n")])
    except Exception as e:
        print(f"Error reading git log: {e}", file=sys.stderr)
        sys.exit(1)

    if timestamps:
        sessions = []
        current_session = [timestamps[0]]
        # Gaps of more than 2 hours (7200 seconds) start a new session
        for ts in timestamps[1:]:
            if ts - current_session[-1] > 7200:
                sessions.append(current_session)
                current_session = [ts]
            else:
                current_session.append(ts)
        sessions.append(current_session)

        total_seconds = 0
        for session in sessions:
            duration = session[-1] - session[0]
            # Add 30 minutes (1800 seconds) overhead per session
            total_seconds += duration + 1800
        total_hours = total_seconds / 3600
    else:
        total_hours = 0.0

    content = readme_path.read_text(encoding="utf-8")
    
    # Extract current README timestamp to check threshold
    time_pattern = r"\*Last Developer Session: ([^\*]+)\*"
    match = re.search(time_pattern, content)
    if not match:
        print("Error: Could not find 'Last Developer Session' section in README.md", file=sys.stderr)
        sys.exit(1)
        
    readme_time_str = match.group(1)
    try:
        readme_ts = int(datetime.strptime(readme_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        readme_ts = 0

    # If it is a push check, only update if the difference is more than 60 seconds
    if is_push and abs(latest_commit_ts - readme_ts) <= 60:
        print("README.md timestamp is already up to date (within threshold).")
        sys.exit(0)

    # Perform updates
    time_replacement = f"*Last Developer Session: {target_time_str}*"
    content = re.sub(time_pattern, time_replacement, content)
    
    hours_pattern = r"\*Total Cumulative Development Time: [^\*]+\*"
    hours_replacement = f"*Total Cumulative Development Time: ~{total_hours:.1f} hours*"
    content = re.sub(hours_pattern, hours_replacement, content)
    
    readme_path.write_text(content, encoding="utf-8")
    print(f"Updated README.md Last Developer Session to: {target_time_str}")
    print(f"Updated README.md Total Cumulative Development Time to: ~{total_hours:.1f} hours")
    
    if is_push:
        # Exit with 1 on push to force commit of the updated timestamp
        sys.exit(1)

if __name__ == "__main__":
    main()
