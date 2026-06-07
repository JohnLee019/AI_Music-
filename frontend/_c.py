import sys, httpx, json
sys.stdout.reconfigure(encoding="utf-8")
# get a place id
places = httpx.get("http://127.0.0.1:8000/api/places", timeout=10).json()
pid = places[0]["id"]
r = httpx.post("http://127.0.0.1:8000/api/generate", json={"place_id": pid}, timeout=120)
d = r.json()
print("status:", r.status_code, "| keys:", list(d.keys()))
print("has license field:", "license" in d)
if "license" in d:
    print(json.dumps(d["license"], ensure_ascii=False, indent=2))
