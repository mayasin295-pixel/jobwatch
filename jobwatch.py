#!/usr/bin/env python3
"""בוט משרות: סורק מקורות, מדרג מול הפרופיל, שולח התראות ל-ntfy.
שימוש:  python jobwatch.py            הרצה רגילה
        python jobwatch.py --test     שליחת התראת בדיקה
        python jobwatch.py --dry      הדפסה בלבד, בלי שליחה ובלי שמירת מצב
"""
import hashlib
import html as ihtml
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

import config as C

STATE_FILE = Path(__file__).with_name("state.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "he,en;q=0.8",
}


def log(*a):
    print(*a, flush=True)


def get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"  ! {url[:90]} -> {e}")
        return None


def job(title, url, company="", location="", desc="", hints=(), source=""):
    return {"id": hashlib.sha1(url.encode()).hexdigest()[:16], "title": " ".join(title.split()), "url": url,
            "company": company, "location": location, "desc": desc,
            "hints": [h for h in hints if h], "source": source}


# ------------------------------ מקורות ------------------------------
def src_linkedin():
    out, fails = [], 0
    combos = [(q, ss) for q in C.LINKEDIN_QUERIES for ss in C.LINKEDIN_SEARCHES]
    combos += [(q, C.LINKEDIN_SEARCHES[0]) for q in C.LINKEDIN_ORG_QUERIES]
    for q, (loc, extra, hint) in combos:
        if True:
            url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                   f"?keywords={quote(q)}&location={quote(loc)}&f_TPR=r86400{extra}&start=0")
            r = get(url)
            time.sleep(2)
            if not r:
                fails += 1
                if fails >= 3:
                    log("  LinkedIn חוסם או לא זמין, מדלג על שאר החיפושים")
                    return out
                continue
            for li in BeautifulSoup(r.text, "html.parser").select("li"):
                a = li.select_one("a.base-card__full-link")
                t = li.select_one(".base-search-card__title")
                if not (a and t):
                    continue
                c = li.select_one(".base-search-card__subtitle")
                l = li.select_one(".job-search-card__location")
                out.append(job(t.get_text(), a["href"].split("?")[0], c.get_text(strip=True) if c else "",
                               l.get_text(strip=True) if l else "", hints=[hint], source="linkedin"))
    return out


def src_greenhouse():
    out = []
    for tok in C.GREENHOUSE:
        r = get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=true")
        if not r:
            continue
        for j in r.json().get("jobs", []):
            d = BeautifulSoup(ihtml.unescape(j.get("content", "")), "html.parser").get_text(" ")[:1500]
            out.append(job(j["title"], j["absolute_url"], tok, (j.get("location") or {}).get("name", ""), d,
                           source="greenhouse"))
    return out


def src_lever():
    out = []
    for slug in C.LEVER:
        r = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if not r:
            continue
        for j in r.json():
            cat = j.get("categories") or {}
            out.append(job(j["text"], j["hostedUrl"], slug, cat.get("location", ""),
                           (j.get("descriptionPlain") or "")[:1500], hints=[cat.get("commitment", "")],
                           source="lever"))
    return out


def src_pages():
    out = []
    for name, url in C.WATCH_PAGES.items():
        r = get(url)
        if not r:
            continue
        for a in BeautifulSoup(r.text, "html.parser").select("a[href]"):
            txt = a.get_text(" ", strip=True)
            if 8 <= len(txt) <= 120:
                out.append(job(txt, urljoin(url, a["href"]), name, source="page"))
    return out


def src_drushim():
    """עמודי חברה ב-drushim.co.il: כותרת המשרה (h2/h3) לפני הקישור /job/"""
    out = []
    for name, url in C.DRUSHIM_COMPANIES.items():
        r = get(url)
        if not r:
            continue
        seen = set()
        for a in BeautifulSoup(r.text, "html.parser").select('a[href*="/job/"]'):
            href = urljoin(url, a["href"])
            h = a.find_previous(["h2", "h3"])
            if href in seen or not h:
                continue
            seen.add(href)
            box = a.find_parent(["article", "li", "div"])
            out.append(job(h.get_text(" ", strip=True), href, name,
                           desc=box.get_text(" ", strip=True)[:1500] if box else "", source="drushim"))
    return out


SOURCES = [("linkedin", src_linkedin), ("drushim", src_drushim), ("greenhouse", src_greenhouse), ("lever", src_lever), ("pages", src_pages)]


# ------------------------------ סינון ודירוג ------------------------------
HEB = re.compile(r"[\u0590-\u05FF]")
IL = ["israel", "ישראל", "tel aviv", "jerusalem", "haifa", "herzliya", "petah", "petach", "ramat gan", "rehovot",
      "netanya", "kfar saba", "ra'anana", "raanana", "beer sheva", "be'er sheva", "rishon", "holon", "bnei brak",
      "modi'in", "airport city", "hod hasharon", "yokneam", "rosh ha", "ashdod", "ashkelon", "givatayim",
      "kiryat", "nazareth", "caesarea", "or yehuda", "yavne", "ness ziona", "tel hashomer"]


def israel_ok(loc, desc=""):
    """True אם המשרה בישראל (או שהמיקום לא ידוע)."""
    if not getattr(C, "ISRAEL_ONLY", False):
        return True
    loc = (loc or "").strip()
    if not loc:
        return True
    t = (loc + " " + (desc or "")[:300]).lower()
    return bool(HEB.search(loc)) or any(w in t for w in IL)



def relevant(j):
    t = j["title"].lower()
    return any(w in t for w in C.ROLE_TERMS) and not any(w in t for w in C.EXCLUDE_TERMS)


def has(j, terms):
    b = " ".join([j["title"], j["company"], j["location"], j["desc"], " ".join(j["hints"])]).lower()
    return any(t.lower() in b for t in terms)


def kw_score(j):
    part, health = has(j, C.PART_TERMS), has(j, C.HEALTH_TERMS)
    local, remote = has(j, C.LOCAL_TERMS), has(j, C.REMOTE_TERMS)
    s = 3 + 2 * health + 2 * part + local + remote
    fit = ["הכותרת תואמת תחום (אנליזה, פרויקטים, CRM או דאטה)"]
    gap = []
    if health: fit.append("בתחום הבריאות או החדשנות הרפואית")
    else: gap.append("לא ברור שהתפקיד בתחום הבריאות")
    if part: fit.append("מצוין שהמשרה חלקית או פרילנס")
    else: gap.append("לא מצוין שהמשרה חלקית")
    if local: fit.append("המיקום באזור המרכז")
    if remote: fit.append("אפשרות להיברידי או עבודה מהבית")
    if not (local or remote): gap.append("המיקום או ההיברידיות לא ברורים")
    if len(j["desc"]) < 50: gap.append("אין תיאור מלא, הדירוג לפי הכותרת")
    return {"score": min(s, 10), "reason": "", "fit": ", ".join(fit), "gap": ", ".join(gap), "part": part, "ai": False}


def ai_score(j):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    prompt = (f"{C.PROFILE}\n\nמשרה:\nכותרת: {j['title']}\nחברה: {j['company']}\nמיקום: {j['location']}\n"
              f"רמזים: {', '.join(j['hints'])}\nתיאור: {j['desc'][:1500]}\n\n"
              "דרגי 1-10 עד כמה כדאי לה לגשת למשרה הזו. שקלי: התאמה לניסיון, חברה טובה ומוניטין של אנשים ותרבות, "
              "עניין וייחודיות של התפקיד, תפקיד שטח (עבודה מול משתמשים/לקוחות בשטח, הטמעה, ליווי), "
              "וגם בונוס גדול לחדשנות ברפואה (סטארט־אפ או הייטק בריאות, דאטה אנליסט או ניהול פרויקטים), ובונוס על חלקית/פרילנס, בריאות/רפואה, היברידי/מרחוק וקרבה לאלעד. "
              "תפקיד שגרתי ומשעמם = נמוך גם אם מתאים. התאמה סבירה = 5. ציני רק מה שאפשר להסיק מהפרטים שניתנו, ואם חסר תיאור כתבי זאת. "
              "החזירי JSON בלבד, בלי טקסט נוסף: "
              '{"score": מספר, "fit": "מה מתאים לה, עד 25 מילים בעברית", "gap": "מה פחות מתאים או לא ברור, עד 25 מילים בעברית", "part": true/false (חלקית או פרילנס)}')
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=60,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": C.MODEL, "max_tokens": 400,
                                "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        d = json.loads(re.search(r"\{.*\}", r.json()["content"][0]["text"], re.S).group(0))
        return {"score": int(d["score"]), "reason": "", "fit": str(d.get("fit", "")), "gap": str(d.get("gap", "")), "part": bool(d.get("part")) or has(j, C.PART_TERMS),
                "ai": True}
    except Exception as e:
        log(f"  ! דירוג AI נכשל ({e}), משתמש בדירוג מילות מפתח")
        return None


# ------------------------------ בדיקת משרה פתוחה ------------------------------
CLOSED = re.compile(r"no longer accepting|position (has been )?filled|(job|position|posting) (is )?(no longer|closed|expired|not available)|"
                    r"this job (is )?closed|המשרה (נסגרה|אינה זמינה|לא זמינה|פגה|אינה פעילה)|לא מקבלים מועמדים|המשרה הוסרה", re.I)


def is_open(url):
    """False רק כשברור שהמשרה סגורה. אם אי אפשר לדעת, נחשבת פתוחה."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception:
        return True
    if r.status_code in (404, 410):
        return False
    return r.status_code >= 400 or not CLOSED.search(r.text[:300000])


# ------------------------------ התראות ------------------------------
def notify(j, res):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    star = "🌟 " if res["part"] else ""
    body = " · ".join(x for x in [j["company"], j["location"]] if x)
    if res.get("reason"):
        body += "\n" + res["reason"]
    if res.get("fit"):
        body += "\n✓ " + res["fit"]
    if res.get("gap"):
        body += "\n✗ " + res["gap"]
    payload = {"topic": topic, "title": f"{star}{res['score']}/10 · {j['title']}"[:200], "message": body or j["title"],
               "click": j["url"], "priority": 4 if res["part"] else 3,
               "tags": ["briefcase"] + (["star"] if res["part"] else [])}
    if getattr(C, "APP_URL", ""):
        payload["actions"] = [{"action": "view", "label": "פתחי באפליקציה", "url": C.APP_URL}]
    r = requests.post(os.environ.get("NTFY_SERVER", "https://ntfy.sh"), json=payload, timeout=20)
    r.raise_for_status()


def load_state():
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:
        return {"jobs": {}}


def main():
    args = sys.argv[1:]
    if "--test" in args:
        notify(job("בדיקה: ההתראות עובדות!", "https://ntfy.sh"), {"score": 10, "reason": "אם את רואה את זה, הכול מוכן", "part": True})
        log("נשלחה התראת בדיקה")
        return
    dry = "--dry" in args
    if not dry and not os.environ.get("NTFY_TOPIC", "").strip():
        sys.exit("חסר NTFY_TOPIC (הגדרת Secret)")

    state, now = load_state(), time.time()
    state["jobs"] = {k: v for k, v in state["jobs"].items() if now - v.get("ts", now) < 120 * 86400}

    # משרות שמורות מחוץ לישראל מוסתרות
    for v in state["jobs"].values():
        if not israel_ok(v.get("l", "")):
            v["closed"] = v["sent"] = True

    # איסוף
    found, keys = [], set()
    for name, fn in SOURCES:
        try:
            got = fn()
        except Exception as e:
            log(f"[{name}] קרס: {e}")
            continue
        log(f"[{name}] {len(got)} משרות")
        for j in got:
            k = (j["title"].lower(), j["company"].lower())
            if k not in keys:
                keys.add(k)
                found.append(j)

    found = [j for j in found if israel_ok(j["location"], j["desc"])]

    # דירוג חדשות
    new = [j for j in found if j["id"] not in state["jobs"] and relevant(j)]
    log(f"חדשות ורלוונטיות לפי כותרת: {len(new)}")
    ai_calls, byid = 0, {j["id"]: j for j in found}
    for j in new:
        res = None
        if ai_calls < C.MAX_AI_PER_RUN:
            res = ai_score(j)
            ai_calls += 1 if os.environ.get("ANTHROPIC_API_KEY", "").strip() else 0
        elif os.environ.get("ANTHROPIC_API_KEY", "").strip():
            continue  # ימתין להרצה הבאה
        res = res or kw_score(j)
        state["jobs"][j["id"]] = {"t": j["title"], "c": j["company"], "u": j["url"], "l": j["location"],
                                  "score": res["score"], "r": res["reason"], "f": res.get("fit", ""), "g": res.get("gap", ""), "part": res["part"],
                                  "ai": res["ai"], "sent": False, "ts": now}

    # שליחה: קודם חלקית/פרילנס, אחר כך לפי ציון
    pending = [(i, v) for i, v in state["jobs"].items()
               if not v["sent"] and v["score"] >= (C.MIN_SCORE_AI if v["ai"] else C.MIN_SCORE_KW)]
    pending.sort(key=lambda x: (x[1]["part"], x[1]["score"]), reverse=True)
    sent = 0
    for i, v in pending[:C.MAX_PER_RUN]:
        j = job(v["t"], v["u"], v["c"], v["l"])
        res = {"score": v["score"], "reason": v["r"], "fit": v.get("f", ""), "gap": v.get("g", ""), "part": v["part"]}
        if dry:
            log(f"  [{v['score']}{'*' if v['part'] else ''}] {v['t']} | {v['c']} | {v['l']} | {v['u']}")
            continue
        if not is_open(v["u"]):
            v["sent"], v["closed"] = True, True
            log(f"  משרה סגורה, מדלג: {v['t']}")
            continue
        try:
            notify(j, res)
            v["sent"] = True
            sent += 1
        except Exception as e:
            log(f"  ! שליחה נכשלה: {e}")
    log(f"נשלחו {sent} התראות, ממתינות {max(len(pending) - sent, 0)}")
    if not dry:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), "utf-8")


if __name__ == "__main__":
    main()
