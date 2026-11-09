#!/usr/bin/env python3
"""Rebuild the public club page from the planner's private sync copy.

The planner (a Claude artifact) mirrors its saved data on every save:
  pub/meta            -> currentId, settings, schedule, shelf, and [{id, updatedAt}] for every meeting
  pubmeetings/<id>    -> one public meeting record (host notes already removed)

Usage (run from the repo root):
  python3 tools/sync.py need  META.json             # print meeting ids whose record must be fetched
  python3 tools/sync.py apply META.json MEETINGS_DIR  # merge, rebuild index.html; prints CHANGED or UNCHANGED

MEETINGS_DIR holds one <id>.json per fetched meeting (the record's data object).
"""
import datetime, json, os, re, sys

DATA = "data/club.json"
PAGE = "index.html"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def current():
    if os.path.exists(DATA):
        return load_json(DATA)
    return {"meetings": [], "club": {"currentId": "", "now": ""}, "settings": {}, "schedule": [], "shelf": {"upNext": [], "books": {}}, "public": True}


def need(meta):
    have = {m["id"]: m.get("updatedAt") for m in current().get("meetings", [])}
    return [m["id"] for m in meta.get("meetings", []) if have.get(m["id"]) != m.get("updatedAt")]


def comparable(d):
    d = dict(d)
    d.pop("exportedAt", None)
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def apply(meta, mdir):
    cur = current()
    have = {m["id"]: m for m in cur.get("meetings", [])}
    meetings = []
    for ref in meta.get("meetings", []):
        mid = ref["id"]
        path = os.path.join(mdir, mid + ".json")
        if os.path.exists(path):
            rec = load_json(path)
            if rec.get("id") != mid:
                sys.exit(f"ERROR: {path} has id {rec.get('id')!r}, expected {mid!r}")
            if rec.get("updatedAt") != ref.get("updatedAt"):
                sys.exit(f"ERROR: {path} updatedAt {rec.get('updatedAt')} does not match meta {ref.get('updatedAt')}")
            rec.pop("notes", None)
            meetings.append(rec)
        elif mid in have and have[mid].get("updatedAt") == ref.get("updatedAt"):
            meetings.append(have[mid])
        else:
            sys.exit(f"ERROR: meeting {mid} changed but {path} is missing. Fetch pubmeetings/{mid} first.")
    new = {
        "meetings": meetings,
        "club": {"currentId": meta.get("currentId", ""), "now": ""},
        "settings": meta.get("settings", {}),
        "schedule": meta.get("schedule", []),
        "shelf": meta.get("shelf", {"upNext": [], "books": {}}),
        "public": True,
    }
    if comparable(new) == comparable(cur) and os.path.exists(PAGE):
        print("UNCHANGED")
        return
    new["exportedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
        f.write("\n")
    html = open(PAGE, encoding="utf-8").read()
    blob = json.dumps(new, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html, n = re.subn(r'(<script type="application/json" id="club-data">).*?(</script>)', lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
    if n != 1:
        sys.exit("ERROR: club-data block not found in index.html")
    name = (new["settings"].get("clubName", "").strip() or "Book Club")
    name = re.sub(r'[<>&"]', "", name)
    html = re.sub(r"<title>[^<]*</title>", "<title>" + name + "</title>", html, count=1)
    html = re.sub(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="' + name + '">', html, count=1)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print("CHANGED", len(meetings), "meetings")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "need":
        print("\n".join(need(load_json(sys.argv[2]))))
    elif len(sys.argv) >= 4 and sys.argv[1] == "apply":
        apply(load_json(sys.argv[2]), sys.argv[3])
    else:
        sys.exit(__doc__)
