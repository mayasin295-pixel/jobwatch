"""הגדרות - כאן עורכים. את jobwatch.py עצמו אין צורך לשנות."""
import os

# הפרופיל שמועבר ל-Claude לצורך הדירוג (אין כאן טלפון או מייל)
PROFILE = os.environ.get("PROFILE_TEXT", "").strip() or """
אנליסטית מערכות ומנהלת פרויקטים. מחפשת דאטה אנליסט וניהול פרויקטים, בעיקר בחדשנות ברפואה; משרה חלקית או פרילנס בעדיפות; היברידי.
"""

APP_URL = "https://mayasin295-pixel.github.io/jobwatch/"   # כפתור "פתחי באפליקציה" בהתראה
MODEL = "claude-haiku-5-5"   # מודל זול ומהיר לדירוג
MIN_SCORE_AI = 5             # סף התראה כשיש מפתח AI (1-10). 5 = התאמה סבירה
MIN_SCORE_KW = 4             # סף כשאין AI
MAX_PER_RUN = 20             # מקסימום התראות בכל הרצה (השאר ימתינו להרצה הבאה)
MAX_AI_PER_RUN = 40          # הגבלת עלות

# ---- מילים שחייבות להופיע בכותרת המשרה (אחרת מדלגים עליה) ----
ROLE_TERMS = [
    "analyst", "אנליסט", "analytics", "אפיון", "project", "פרויקט", "crm", "salesforce",
    "dynamics", "consultant", "ייעוץ", "יועץ", "יועצת", "נתונים", "data", "דאטה", "מחקר",
    "research", "הטמעה", "implementation", "תהליכים", "process", "מערכות מידע",
]
EXCLUDE_TERMS = [
    "sales rep", "מכירות", "נציג", "מוקד", "sdr", "שליח", "נהג", "software engineer",
    "מפתח", "developer", "devops", "ביטחון", "אחות", "רופא",
]

# ---- סימנים לדירוג (חיפוש בכותרת, מיקום ותיאור) ----
PART_TERMS = ["part time", "part-time", "חלקית", "פרילנס", "freelance", "contract", "קבלן", "עצמאי", "שעתי"]
HEALTH_TERMS = ["בית חולים", "בית-חולים", "קופת חולים", "כללית", "מכבי", "מאוחדת", "לאומית", "שיבא", "איכילוב",
                "הדסה", "רפואי", "רפואה", "בריאות", "קליני", "clinical", "health", "medical", "hospital",
                "pharma", "biotech", "digital health", "healthtech", "medtech", "startup", "סטארט"]
LOCAL_TERMS = ["אלעד", "elad", "ראש העין", "rosh ha", "פתח תקו", "petah", "petach", "תל אביב", "tel aviv",
               "רמת גן", "ramat gan", "בני ברק", "bnei brak", "גבעתיים", "קריית אונו", "שוהם", "מודיעין",
               "תל השומר", "tel hashomer", "גוש דן"]
REMOTE_TERMS = ["remote", "מהבית", "מרחוק", "work from home", "hybrid", "היברידי"]

# ---- מקורות ----
# LinkedIn (חיפוש אורחים לא רשמי; עלול להיחסם). כל חיפוש: (מיקום, פילטר נוסף, רמז)
LINKEDIN_QUERIES = ["medical data analyst", "digital health project manager", "health tech data analyst",
                    "אנליסט מערכות", "מנהל פרויקטים", "data analyst", "Salesforce CRM"]
LINKEDIN_SEARCHES = [
    ("Israel", "", ""),                                            # כל המשרות בישראל
    ("Israel", "&f_JT=P%2CC", "part-time or contract (search filter)"),   # חלקית / חוזה
    ("Worldwide", "&f_WT=2&f_JT=P%2CC", "remote part-time or contract abroad"),  # מרחוק מחו"ל
]

# חיפוש לפי שם ארגון (רץ ללא פילטרים, ומסונן אחר כך לפי כותרת)
LINKEDIN_ORG_QUERIES = ["שיבא", "כללית", "אסף הרופא", "בילינסון", "מכבי שירותי בריאות",
                        "מאוחדת", "לאומית שירותי בריאות", "איכילוב", "אסותא"]

# עמודי חברה ב-drushim.co.il (נבדקו: נטענים עם משרות)
DRUSHIM_COMPANIES = {
    "שיבא": "https://www.drushim.co.il/דרושים-3466496-מרכז-רפואי/",
    "כללית": "https://www.drushim.co.il/%D7%93%D7%A8%D7%95%D7%A9%D7%99%D7%9D-3635748-%D7%9B%D7%9C%D7%9C%D7%99%D7%AA/",
}

# לוחות משרות של חברות. את ה-slug לוקחים מכתובת עמוד הקריירה, למשל
# boards.greenhouse.io/<slug> או jobs.lever.co/<slug>
GREENHOUSE = []   # למשל ["examplecompany"]
LEVER = []        # למשל ["examplecompany"]

# עמודי קריירה סטטיים (בתי חולים, קופות וכו'): שם -> כתובת
# הבוט מחלץ קישורים מהעמוד ומסנן לפי ROLE_TERMS. לא עובד על עמודים שנטענים ב-JavaScript.
WATCH_PAGES = {
    # "כללית": "https://....",
}
