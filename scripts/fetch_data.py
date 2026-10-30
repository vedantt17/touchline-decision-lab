"""Fetch pinned public inputs into the ignored research cache, never the web root."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "source_manifest.json"
UA = "TouchlineDecisionLab/0.1 noncommercial-research"


def read_url(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            return urllib.request.urlopen(request, timeout=90)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def latest(repo):
    result = subprocess.run(["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.split()[0]


def get_file(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with read_url(url) as response:
            content = response.read()
        if content.startswith(b"version https://git-lfs"):
            raise ValueError("Git LFS pointer is not source data")
        dest.write_bytes(content)
    payload = dest.read_bytes()
    return {"path": str(dest.relative_to(ROOT)).replace("\\", "/"), "url": url,
            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}


def prefix(url, dest, *, jsonl=False, max_lines=5000):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with read_url(url) as response, dest.open("wb") as target:
            for i, line in enumerate(response):
                if jsonl:
                    row = json.loads(line)
                    timestamp = row.get("timestamp")
                    if row.get("period") == 1 and timestamp:
                        h, m, s = timestamp.split(":")
                        if int(h) * 3600 + int(m) * 60 + float(s) > 300:
                            break
                elif i >= max_lines:
                    break
                target.write(line)
    item = get_file(url, dest)
    item["subset"] = "period-1 prefix, at most five minutes" if jsonl else f"first {max_lines} lines"
    return item


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    old = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    commits = old.get("commits")
    if not commits or any(len(ref) != 40 for ref in commits.values()):
        commits = {name: latest(repo) for name, repo in [
        ("statsbomb", "hudl/open-data"), ("skillcorner", "SkillCorner/opendata"),
        ("metrica", "metrica-sports/sample-data"),
        ("pitchcontrol", "Friends-of-Tracking-Data-FoTD/LaurieOnTracking"),
        ]}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps({"commits": commits, "files": []}, indent=2), encoding="utf-8")
    sb = f"https://raw.githubusercontent.com/hudl/open-data/{commits['statsbomb']}"
    files = []
    for path in ["data/competitions.json", "data/matches/43/106.json"]:
        files.append(get_file(f"{sb}/{path}", RAW / "statsbomb" / path.removeprefix("data/")))
    matches = json.loads((RAW / "statsbomb/matches/43/106.json").read_text(encoding="utf-8"))
    jobs = [(f"{sb}/data/{kind}/{m['match_id']}.json", RAW / "statsbomb" / kind / f"{m['match_id']}.json")
            for m in matches for kind in ["events", "lineups"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for i, result in enumerate(pool.map(lambda args: get_file(*args), jobs)):
            files.append(result)
            if i % 16 == 0:
                print(f"StatsBomb source files {i + 1}/{len(jobs)}", flush=True)
    sc = f"https://raw.githubusercontent.com/SkillCorner/opendata/{commits['skillcorner']}"
    for remote, local in [("1899585_match.json", "skillcorner_match.json"), ("1899585_phases_of_play.csv", "skillcorner_phases.csv")]:
        files.append(get_file(f"{sc}/data/matches/1899585/{remote}", RAW / local))
    sc_track = f"https://media.githubusercontent.com/media/SkillCorner/opendata/{commits['skillcorner']}/data/matches/1899585/1899585_tracking_extrapolated.jsonl"
    files.append(prefix(sc_track, RAW / "skillcorner_tracking.jsonl", jsonl=True))
    mt = f"https://raw.githubusercontent.com/metrica-sports/sample-data/{commits['metrica']}/data/Sample_Game_3"
    files.append(get_file(f"{mt}/Sample_Game_3_metadata.xml", RAW / "metrica_metadata.xml"))
    files.append(prefix(f"{mt}/Sample_Game_3_tracking.txt", RAW / "metrica_tracking.txt", max_lines=5000))
    pc = f"https://raw.githubusercontent.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking/{commits['pitchcontrol']}"
    files.append(get_file(f"{pc}/Metrica_PitchControl.py", ROOT / "vendor/Metrica_PitchControl.py"))
    files.append(get_file(f"{pc}/LICENSE", ROOT / "vendor/LAURIE_LICENSE"))
    files.append(get_file(f"{sc}/LICENSE", ROOT / "vendor/SKILLCORNER_LICENSE"))
    files.append(get_file(f"{sb}/LICENSE.pdf", ROOT / "docs/STATSBOMB_DATA_LICENSE.pdf"))
    # The official repository's branding asset is required when publishing analysis.
    logo = "img/SB%20-%20Icon%20Lockup%20-%20Colour%20positive.png"
    files.append(get_file(f"{sb}/{logo}", ROOT / "public/data/statsbomb-logo.png"))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"commits": commits, "files": sorted(files, key=lambda x: x["path"])}, indent=2), encoding="utf-8")
    print(f"Fetched {len(files)} source/notice files; StatsBomb matches={len(matches)}", flush=True)


if __name__ == "__main__":
    main()
