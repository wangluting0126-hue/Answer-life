"""Call a running Answer Life server using Python's standard library."""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Message to send")
    parser.add_argument("--url", default="http://127.0.0.1:8020", help="Server base URL")
    parser.add_argument("--skill", help="Skill name for this message")
    parser.add_argument("--conversation-id", help="ID returned by an earlier request")
    args = parser.parse_args()

    payload = {"text": args.text, "skill": args.skill, "conversation_id": args.conversation_id}
    request = Request(
        args.url.rstrip("/") + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
