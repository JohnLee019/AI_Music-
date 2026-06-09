import json
import os
import sys

# Set standard output to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    path = "data/raw/tourapi_places.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, "r", encoding="utf-8") as f:
        places = json.load(f)
        
    print(f"Total places: {len(places)}")
    types = {}
    regions = {}
    for p in places:
        t = p.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
        r = p.get("music_region", "unknown")
        regions[r] = regions.get(r, 0) + 1
        
    print("Types:")
    for t, count in types.items():
        print(f"  {t}: {count}")
        
    print("Regions:")
    for r, count in regions.items():
        print(f"  {r}: {count}")

if __name__ == "__main__":
    main()
