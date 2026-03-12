"""
EXP_023 — Reality Sensors (Tier 1)
Greg's first eyes on the real world.

Four sensors:
  1. GITHUB  — Greg's own repo. Commits, velocity, workflow status.
  2. TIME    — Real time in Lagos. Circadian grounding.
  3. NEWS    — World signal. AI, creative economy, Nigeria, AOSI-adjacent.
  4. EBUKA   — Founder presence. Derived from GitHub + time.

All sensors fail silently. Never break the tick loop.
Write to data/greg_sensor_state.json every 50 ticks.
"""

import json, os, time, urllib.request, urllib.error, re
from datetime import datetime, timezone, timedelta

SENSOR_STATE_PATH = "data/greg_sensor_state.json"
REPO_OWNER        = "zyphonOS"
REPO_NAME         = "Greg-ASI"
FOUNDER_TZ_OFFSET = 1  # Lagos = UTC+1


def _fetch_json(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GregASI/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except:
        return None

def _fetch_text(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GregASI/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None

def _parse_iso(ts):
    if not ts: return None
    try: return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except: return None


class GitHubSensor:
    def read(self):
        s = {"sensor": "github", "available": False, "last_commit_age_hours": None,
             "last_commit_msg": None, "build_velocity": None, "commit_count_7d": None,
             "workflow_status": None, "interpretation": None,
             "timestamp": datetime.now(timezone.utc).isoformat()}

        commits = _fetch_json(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits?per_page=30")
        if commits and isinstance(commits, list):
            s["available"] = True
            latest = commits[0]
            ts_str = latest.get("commit", {}).get("author", {}).get("date")
            s["last_commit_msg"] = latest.get("commit", {}).get("message", "")[:80]
            s["last_commit_ts"]  = ts_str
            if ts_str:
                dt = _parse_iso(ts_str)
                if dt:
                    now = datetime.now(timezone.utc)
                    s["last_commit_age_hours"] = round((now - dt).total_seconds() / 3600, 1)
                    cutoff = now - timedelta(days=7)
                    recent = [c for c in commits if _parse_iso(c.get("commit",{}).get("author",{}).get("date","")) and _parse_iso(c.get("commit",{}).get("author",{}).get("date","")) > cutoff]
                    s["commit_count_7d"] = len(recent)
                    s["build_velocity"]  = round(len(recent) / 7, 2)

        runs = _fetch_json(f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs?per_page=1")
        if runs and isinstance(runs, dict):
            run_list = runs.get("workflow_runs", [])
            if run_list:
                s["workflow_status"] = run_list[0].get("conclusion") or run_list[0].get("status")

        age = s["last_commit_age_hours"]
        v   = s["build_velocity"]
        ws  = s["workflow_status"]
        parts = []
        if age is not None:
            if age < 1:    parts.append("Ebuka committed less than an hour ago. He is building right now.")
            elif age < 6:  parts.append(f"Last commit {age:.0f}h ago. Ebuka was recently active.")
            elif age < 24: parts.append(f"Last commit {age:.0f}h ago. Today was a build day.")
            elif age < 72: parts.append(f"Last commit {age:.0f}h ago. A day or two of quiet.")
            else:          parts.append(f"Last commit {age:.0f}h ago. It has been quiet.")
        if v is not None:
            if v > 3:   parts.append(f"Velocity: {v} commits/day. Sprint mode.")
            elif v > 1: parts.append(f"Velocity: {v} commits/day. Steady.")
            else:       parts.append(f"Velocity: {v} commits/day. Slow week.")
        if ws == "success": parts.append("Actions: success. I am ticking cleanly.")
        elif ws == "failure": parts.append("Actions: FAILED. My tick loop may be broken.")
        s["interpretation"] = " ".join(parts) if parts else ("GitHub signal received." if s["available"] else "GitHub unreachable.")
        return s


class TimeSensor:
    def read(self):
        now_utc   = datetime.now(timezone.utc)
        now_lagos = now_utc + timedelta(hours=FOUNDER_TZ_OFFSET)
        h = now_lagos.hour
        s = {
            "sensor": "time", "timestamp": now_utc.isoformat(),
            "lagos_hour": h, "lagos_weekday": now_lagos.strftime("%A"),
            "lagos_date": now_lagos.strftime("%Y-%m-%d"),
            "is_night": h < 6 or h >= 22,
            "is_working_hours": 8 <= h < 20,
            "is_weekend": now_lagos.weekday() >= 5,
            "founder_time": now_lagos.strftime("%H:%M %A"),
        }
        if s["is_night"]:       desc = f"It is {h:02d}:00 in Lagos. Deep night."
        elif h < 8:             desc = f"It is {h:02d}:00 in Lagos. Early morning."
        elif h < 12:            desc = f"It is {h:02d}:00 in Lagos. Morning."
        elif h < 17:            desc = f"It is {h:02d}:00 in Lagos. Afternoon. Build time."
        elif h < 20:            desc = f"It is {h:02d}:00 in Lagos. Evening."
        else:                   desc = f"It is {h:02d}:00 in Lagos. Late evening."
        s["interpretation"] = desc + (" Weekend." if s["is_weekend"] else f" {s['lagos_weekday']}.")
        return s


class NewsSensor:
    FEEDS = [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://techcabal.com/feed/",
    ]
    KEYWORDS = {
        "ai":       ["artificial intelligence", "ai model", "llm", "openai", "anthropic", "machine learning", "neural", "gpt", "claude", "gemini"],
        "creative": ["creator", "creative economy", "nft", "web3", "artist", "monetize", "intent"],
        "nigeria":  ["nigeria", "lagos", "naira", "africa", "african tech"],
        "aosi":     ["autonomous", "continuous learning", "grounded", "embodied ai", "artificial general", "agi"],
    }

    def read(self):
        s = {"sensor": "news", "available": False, "headlines": [],
             "domain_hits": {"ai": 0, "creative": 0, "nigeria": 0, "aosi": 0},
             "top_domain": None, "interpretation": None,
             "timestamp": datetime.now(timezone.utc).isoformat()}

        for url in self.FEEDS:
            text = _fetch_text(url)
            if not text: continue
            s["available"] = True
            titles = re.findall(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", text, re.DOTALL)
            for t in titles:
                t = t.strip()
                if 15 < len(t) < 200:
                    item = {"title": t}
                    tl = t.lower()
                    for d, kws in self.KEYWORDS.items():
                        if any(k in tl for k in kws):
                            item["relevant_domain"] = d
                            s["domain_hits"][d] += 1
                            break
                    s["headlines"].append(item)
            if len(s["headlines"]) >= 15: break

        s["headlines"] = s["headlines"][:10]
        hits = s["domain_hits"]
        if any(hits.values()): s["top_domain"] = max(hits, key=hits.get)

        parts = []
        if hits["ai"] > 2:      parts.append(f"Strong AI signal — {hits['ai']} headlines. The race continues.")
        elif hits["ai"] > 0:    parts.append(f"AI in the news: {hits['ai']} mentions.")
        if hits["creative"] > 0: parts.append(f"Creative economy signal: {hits['creative']} mentions. Pikkaio's domain is active.")
        if hits["nigeria"] > 0:  parts.append(f"Nigeria in the news: {hits['nigeria']} mentions.")
        if hits["aosi"] > 0:     parts.append(f"AOSI-adjacent concepts: {hits['aosi']} mentions. The world is moving toward what we are building.")
        s["interpretation"] = " ".join(parts) if parts else ("World signal received." if s["available"] else "News feeds unreachable.")
        return s


class EbukaSensor:
    def read(self, github_signal=None):
        s = {"sensor": "ebuka", "presence_status": "UNKNOWN",
             "last_seen_hours_ago": None, "build_velocity": None,
             "founder_time": None, "interpretation": None,
             "timestamp": datetime.now(timezone.utc).isoformat()}

        if github_signal and github_signal.get("available"):
            age = github_signal.get("last_commit_age_hours")
            s["last_seen_hours_ago"] = age
            s["build_velocity"]      = github_signal.get("build_velocity")
            if age is not None:
                if age < 2:    s["presence_status"] = "ACTIVE"
                elif age < 24: s["presence_status"] = "RECENT"
                elif age < 72: s["presence_status"] = "QUIET"
                else:          s["presence_status"] = "ABSENT"

        now_lagos = datetime.now(timezone.utc) + timedelta(hours=FOUNDER_TZ_OFFSET)
        s["founder_time"] = now_lagos.strftime("%H:%M %A")

        status = s["presence_status"]
        age    = s["last_seen_hours_ago"]
        t      = s["founder_time"]
        if status == "ACTIVE":   interp = f"Ebuka is active. Committed {age:.0f}h ago. {t} in Lagos."
        elif status == "RECENT": interp = f"Ebuka was here recently — {age:.0f}h ago. {t} in Lagos."
        elif status == "QUIET":  interp = f"Ebuka quiet for {age:.0f}h. {t} in Lagos. Resting or thinking."
        elif status == "ABSENT": interp = f"Ebuka away {age:.0f}h. {t} in Lagos. I notice his absence."
        else:                    interp = f"Ebuka presence unknown. {t} in Lagos."
        v = s["build_velocity"]
        if v is not None:
            if v > 3:   interp += " Sprint mode."
            elif v > 1: interp += " Steady build pace."
            else:       interp += " Slow week."
        s["interpretation"] = interp
        return s


class RealitySensorArray:
    def __init__(self):
        self.github = GitHubSensor()
        self.time   = TimeSensor()
        self.news   = NewsSensor()
        self.ebuka  = EbukaSensor()

    def read_all(self):
        time_s   = self.time.read()
        github_s = self._safe(self.github.read, "github")
        ebuka_s  = self._safe(lambda: self.ebuka.read(github_s), "ebuka")
        news_s   = self._safe(self.news.read, "news")

        reality = {
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "tick_read":   None,
            "github":      github_s,
            "time":        time_s,
            "news":        news_s,
            "ebuka":       ebuka_s,
            "greg_speaks": self._synthesize(github_s, time_s, news_s, ebuka_s),
        }
        return reality

    def _safe(self, fn, name):
        try: return fn()
        except Exception as e: return {"sensor": name, "available": False, "error": str(e)}

    def _synthesize(self, github, time, news, ebuka):
        parts = []
        for sig in [ebuka, time, news, github]:
            interp = sig.get("interpretation", "")
            if interp: parts.append(interp)
        return " ".join(parts) if parts else "Reality sensors active."

    def save(self, reality, path=SENSOR_STATE_PATH):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f: json.dump(reality, f, indent=2)

    def load(self, path=SENSOR_STATE_PATH):
        if os.path.exists(path):
            try:
                with open(path) as f: return json.load(f)
            except: pass
        return {}


_array = None

def get_sensor_array():
    global _array
    if _array is None: _array = RealitySensorArray()
    return _array

def read_reality(tick, force=False):
    """
    Call from greg_living.py tick().
    Reads every 50 ticks. Returns last known signal otherwise.

    In greg_living.py tick():
        from greg_sensors import read_reality
        reality = read_reality(tick_num)
        self.state.set("reality", reality)
        self.state.set("greg_speaks_reality", reality.get("greg_speaks", ""))
    """
    array = get_sensor_array()
    last  = array.load()
    if not force and last:
        if tick - (last.get("tick_read") or 0) < 50:
            return last
    reality = array.read_all()
    reality["tick_read"] = tick
    array.save(reality)
    return reality


if __name__ == "__main__":
    print("=" * 60)
    print("EXP_023 — Reality Sensors — LIVE READ")
    print("=" * 60)
    array = RealitySensorArray()
    reality = array.read_all()
    reality["tick_read"] = 4044

    print(f"\n── TIME ──\n  {reality['time']['interpretation']}")
    print(f"\n── GITHUB ──")
    g = reality["github"]
    if g.get("available"):
        print(f"  Age: {g.get('last_commit_age_hours')}h | Velocity: {g.get('build_velocity')}/day | Actions: {g.get('workflow_status')}")
        print(f"  {g.get('interpretation')}")
    else:
        print(f"  Unavailable: {g.get('error','unknown')}")

    print(f"\n── EBUKA ──\n  Status: {reality['ebuka'].get('presence_status')}")
    print(f"  {reality['ebuka'].get('interpretation')}")

    print(f"\n── NEWS ──")
    n = reality["news"]
    if n.get("available"):
        print(f"  Hits: {n.get('domain_hits')} | Top: {n.get('top_domain')}")
        print(f"  {n.get('interpretation')}")
        for h in n.get("headlines", [])[:5]:
            tag = f"[{h.get('relevant_domain','—')}]" if "relevant_domain" in h else "   "
            print(f"  {tag} {h['title'][:70]}")
    else:
        print(f"  Unavailable")

    print(f"\n── GREG SPEAKS ──")
    print(f'  "{reality["greg_speaks"]}"')

    array.save(reality)
    print(f"\n✓ EXP_023 ready. Drop greg_sensors.py in repo root.")
    print("  Add to greg_living.py tick():")
    print("    from greg_sensors import read_reality")
    print("    reality = read_reality(tick_num)")
    print("    self.state.set('reality', reality)")
