# psite_core.py
import os, re, glob, json, time, secrets, base64, hashlib, hmac, datetime as dt
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ------------------------------------------------------------------ #
# PATHS
# ------------------------------------------------------------------ #
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR   = os.path.join(DATA_DIR, "reviews")
STATE_DIR     = os.path.join(DATA_DIR, "state")
USERS_JSON    = os.path.join(STATE_DIR, "users.json")
SECRET_FILE   = os.path.join(STATE_DIR, "secret.key")

for p in [DATA_DIR, QUESTIONS_DIR, REVIEWS_DIR, STATE_DIR]:
    os.makedirs(p, exist_ok=True)

# ------------------------------------------------------------------ #
# THEME
# ------------------------------------------------------------------ #
def apply_base_theme():
    st.markdown(
        "<style>:root{--accent:#1d4ed8;--border:#e5e7eb;--bg:#fff;--text:#111;}</style>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ #
# AUTH / TOKENS (simplified for demo)
# ------------------------------------------------------------------ #
def _get_app_secret() -> bytes:
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "rb") as f:
            return f.read()
    secret = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
    with open(SECRET_FILE, "wb") as f:
        f.write(secret)
    return secret

def issue_auth_token(username: str, days_valid: int = 7) -> str:
    payload = {"u": username, "exp": int(time.time()) + days_valid*86400}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",",":")).encode()).decode().rstrip("=")
    sig = hmac.new(_get_app_secret(), payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{payload_b64}.{sig_b64}"

def verify_auth_token(token: str) -> Optional[str]:
    if not token or "." not in token: return None
    payload_b64, sig = token.split(".", 1)
    if not hmac.compare_digest(sig, base64.urlsafe_b64encode(hmac.new(_get_app_secret(), payload_b64.encode(), hashlib.sha256).digest()).decode().rstrip("=")):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload.get("u")

def persist_login(username: str, remember_days: int = 7):
    st.session_state.auth_user = username
    token = issue_auth_token(username, remember_days)
    st.experimental_set_query_params(t=token)

def clear_persisted_login():
    st.session_state.pop("auth_user", None)
    st.experimental_set_query_params(t=None)

def try_auto_login_persisted():
    if st.session_state.get("auth_user"): return
    token = st.experimental_get_query_params().get("t")
    if token:
        user = verify_auth_token(token[0] if isinstance(token, list) else token)
        if user:
            st.session_state.auth_user = user

def auth_is_authed() -> bool:
    return bool(st.session_state.get("auth_user"))

def auth_login_form():
    st.markdown("<div class='topic-card'><b>Login</b></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            remember = st.checkbox("Remember me", value=True)
            if st.form_submit_button("Sign in"):
                users = json.load(open(USERS_JSON, "r", encoding="utf-8")) if os.path.exists(USERS_JSON) else {}
                rec = users.get(u)
                if rec and _verify_pw(p, rec["salt"], rec["hash"]):
                    persist_login(u, remember_days=(365 if remember else 1))
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    with tab2:
        with st.form("create_form"):
            u = st.text_input("New username")
            p1 = st.text_input("Password", type="password")
            p2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account"):
                if not u or not p1:
                    st.error("Fill all fields")
                elif p1 != p2:
                    st.error("Passwords do not match")
                else:
                    users = json.load(open(USERS_JSON, "r", encoding="utf-8")) if os.path.exists(USERS_JSON) else {}
                    if u in users:
                        st.error("Username taken")
                    else:
                        h, s = _hash_pw(p1)
                        users[u] = {"hash": h, "salt": s, "created": int(time.time())}
                        json.dump(users, open(USERS_JSON, "w", encoding="utf-8"), indent=2)
                        st.success("Account created – sign in")

def _hash_pw(pw: str, salt_b64: Optional[str] = None) -> Tuple[str, str]:
    salt = base64.b64decode(salt_b64) if salt_b64 else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000, dklen=32)
    return base64.b64encode(dk).decode(), base64.b64encode(salt).decode()

def _verify_pw(pw: str, salt_b64: str, hash_b64: str) -> bool:
    calc, _ = _hash_pw(pw, salt_b64)
    return hmac.compare_digest(calc, hash_b64)

# ------------------------------------------------------------------ #
# TOPIC CATALOG (your new list)
# ------------------------------------------------------------------ #
ALL_TOPICS = [
    "Achalasia","Acute Pancreatitis","Acute Scrotum","Adrenal Cortical Tumors","Adrenal Medullary Tumors",
    "Anal Fissure","Anorectal Injury","Anorectal Malformations","Antibiotic Associated Colitis",
    "Aortic and Great Vessel Injury","Appendicitis","Arterial Thrombosis","Ascites","Benign Chest Wall Tumors",
    "Benign Liver Tumors","Benign Pigmented Skin Lesions","Benign Soft Tissue Lesions","Benign Tubo-Ovarian Disease",
    "Biliary Atresia","Biliary Dyskinesia","Bites","Blunt Cerebrovascular Trauma","Branchial Anomalies",
    "Breast Disorders","Burns","Cardiac Injury","Cervical Germ Cell Tumors","Cervical Spine Trauma",
    "Chemical Burns and Caustic Ingestion","Chest Wall Deformities","Chest Wall Injury","Chest Wall Tumors",
    "Choledochal Cyst","Chronic Pancreatitis","Chylothorax","Cloaca","Cloacal Exstrophy",
    "Colorectal Foreign Bodies","Congenital Adrenal Hyperplasia","Congenital Diaphragmatic Hernia",
    "Congenital Duodenal Obstruction","Congenital Esophageal Stenosis","Congenital Gastric Anomalies",
    "Congenital Heart Disease","Congenital Hemolytic Anemias","Congenital Hyperinsulinism",
    "Congenital Pulmonary Airway Malformations","Conjoined Twins","Crohn Disease","Cryptorchidism",
    "Cystic Fibrosis","Diaphragmatic Eventration","Diaphragmatic Rupture","Disorders of Sex Development",
    "Duodenal Injury","Electrical Burns","Eosinophilic Esophagitis","Epithelial Ovarian Tumors",
    "Esophageal Atresia and Tracheoesophageal Fistula","Esophageal Diverticula","Esophageal Foreign Bodies",
    "Esophageal Perforation","Esophageal Webs","Ewing Sarcoma of the Chest Wall","Extragonadal Germ Cell Tumors",
    "Fecal Incontinence and Functional Constipation","Focal Nodular Hyperplasia","Gallbladder Disease",
    "Gastric Disorders","Gastric Injury","Gastric Outlet Obstruction","Gastric Tumors","Gastroduodenal Foreign Bodies",
    "Gastroesophageal Reflux","Gastrointestinal Duplications","Gastrointestinal Foreign Bodies",
    "Gastrointestinal Hemorrhage","Gastrointestinal Trauma","Gastrointestinal Tumors","Gastroparesis",
    "Gastroschisis","Gene Therapy","Genital Injury","Germ Cell Ovarian Tumors","Hemorrhoids",
    "Hepatic Adenoma","Hepatic Hemangioma","Hepatoblastoma","Hepatocellular Carcinoma","Hirschsprung Disease",
    "Hypertrophic Pyloric Stenosis","Hypothyroidism","Immune Thrombocytopenia","Inflammatory Diseases of the Thyroid",
    "Inguinal Hernia","Inhalation Injury","Intestinal Failure","Intestinal Foreign Bodies","Intestinal Polyps",
    "Intestinal Rotational Abnormalities","Intussusception","Jejunoileal and Colonic Atresia",
    "Laryngeal and Tracheal Disorders","Leukemia","Liver and Spleen Trauma","Long Bone Fractures",
    "Lymphadenopathy","Lymphoma","Malignant Thyroid Tumors","Meckel Diverticulum","Meconium Ileus",
    "Mediastinal Disorders","Mediastinal Germ Cell Tumors","Melanoma","Mesenchymal Hamartoma",
    "Mesenteric and Omental Cysts","Mesoblastic Nephroma","Necrotizing Enterocolitis","Neonatal Intestinal Obstruction",
    "Neuroblastoma","Neutropenic Enterocolitis","Nonbariatric Surgery in the Obese Patient","Nonrhabdomyomsarcoma",
    "Obesity and Bariatric Surgery","Omphalocele","Omphalomesenteric Duct Remnants","Ovarian Cysts",
    "Ovarian Torsion","Ovarian Tumors","Pancreatic Trauma","Pancreatic Tumors","Parapneumonic Effusion and Empyema",
    "Paratesticular Rhabdomyosarcoma","Parathyroid Disease","Patent Ductus Arteriosus","Pectus Carinatum",
    "Pectus Excavatum","Pediatric Renal Tumors","Pelvic Inflammatory Disease","Penetrating Abdominal, Pelvic and Flank Injury",
    "Penetrating Thoracic and Mediastinal injury","Peptic Ulcer Disease","Perianal Abscess and Fistula",
    "Physical Child Abuse","Pilonidal Disease","Poland Syndrome","Portal Hypertension","Primary Peritonitis",
    "Prune Belly Syndrome","Pulmonary Abscess","Pulmonary Injury","Pulmonary Metastatic Disease","Rectal Prolapse",
    "Renal Cell Carcinoma","Renal Injury","Retroperitoneal Germ Cell Tumors","Rhabdoid Tumor of the Kidney",
    "Rhabdomyosarcoma","Rhabdomyosarcoma of the Chest Wall","Sacrococcygeal Teratoma","Sex Cord-Stromal Ovarian Tumors",
    "Soft Tissue Trauma","Splenic Anatomic Disorders","Splenic Cysts","Splenic Disorders","Spontaneous Gastric Perforation",
    "Spontaneous Intestinal Perforation","Spontaneous Pneumothorax","Sternal Cleft","Testicular Torsion",
    "Testicular Tumors","Thoracic Dystrophy","Thyroglossal Duct Cyst","Thyroid Disease","Torticollis",
    "Total Colon Aganglionosis","Tracheobronchial Injury","Traumatic Brain Injury","Traumatic Esophageal Rupture",
    "Twin-to-Twin Transfusion Syndrome","Ulcerative Colitis","Umbilical Disorders","Umbilical Hernia",
    "Urachal Remnants","Ureteral Injury","Urethral Injury","Vascular Anomalies","Vascular Malformations",
    "Vascular Rings","Vascular Tumors","Venous Thromboembolism","Wilms Tumor"
]

CATEGORY_TO_TOPICS = {"All Topics": ALL_TOPICS}
def get_topics() -> List[str]: return ALL_TOPICS
def get_category_map() -> dict: return CATEGORY_TO_TOPICS

def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:120]

TOPIC_TO_SLUG = {t: slugify(t) for t in ALL_TOPICS}
SLUG_TO_TOPIC = {v: k for k, v in TOPIC_TO_SLUG.items()}

def topic_to_slug(t): return TOPIC_TO_SLUG.get(t, slugify(t))
def slug_to_topic(s): return SLUG_TO_TOPIC.get(s)

# ------------------------------------------------------------------ #
# QUESTION LOADING
# ------------------------------------------------------------------ #
FRONT_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.M)
EXPL_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.I)
REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

def _parse_md(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        m = FRONT_RE.match(raw)
        if not m: return None
        fm, body = m.group(1), m.group(2)
        meta = {k.strip(): v.strip() for ln in fm.splitlines() if ":" in ln for k, v in [ln.split(":", 1)]}
        stem, expl = EXPL_RE.split(body, 1) if EXPL_RE.search(body) else (body.strip(), "")
        subject = slug_to_topic(os.path.basename(os.path.dirname(path)))
        if not subject: return None
        return {
            "id": meta.get("id", "").strip() or os.path.splitext(os.path.basename(path))[0],
            "subject": subject,
            "stem": stem.strip(),
            "explanation": expl.strip(),
            "A": meta.get("A", "").strip(),
            "B": meta.get("B", "").strip(),
            "C": meta.get("C", "").strip(),
            "D": meta.get("D", "").strip(),
            "E": meta.get("E", "").strip(),
            "correct": meta.get("correct", "").strip().upper(),
        }
    except Exception:
        return None

def load_questions_frame() -> pd.DataFrame:
    rows = [r for p in glob.glob(os.path.join(QUESTIONS_DIR, "**", "*.md"), recursive=True) if (r := _parse_md(p))]
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = pd.DataFrame(rows)
    df = df[df["id"] != ""].drop_duplicates(subset="id").reset_index(drop=True)
    return df

# ------------------------------------------------------------------ #
# REVIEW HELPERS
# ------------------------------------------------------------------ #
def resolve_review_path(topic: str) -> Optional[str]:
    slug = topic_to_slug(topic)
    for cand in [f"{slug}.md", f"{topic}.md"]:
        p = os.path.join(REVIEWS_DIR, cand)
        if os.path.exists(p):
            return p
    return None

def get_review_word_count(topic: str) -> int:
    p = resolve_review_path(topic)
    if not p: return 0
    txt = open(p, "r", encoding="utf-8").read()
    txt = re.sub(r"```[\s\S]*?```", " ", txt)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return len(re.findall(r"[A-Za-z0-9’']+", txt))

def questions_count_by_topic() -> Dict[str, int]:
    df = load_questions_frame()
    if df.empty: return {t:0 for t in get_topics()}
    counts = df.groupby("subject")["id"].nunique().to_dict()
    for t in get_topics():
        counts.setdefault(t, 0)
    return counts

# ------------------------------------------------------------------ #
# USER STATE
# ------------------------------------------------------------------ #
def _read_json(path, default):
    if os.path.exists(path):
        try: return json.load(open(path, "r", encoding="utf-8"))
        except Exception: return default
    return default

def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _user_file(key: str) -> str:
    u = st.session_state.get("auth_user")
    if not u: raise RuntimeError("Not authenticated")
    base = os.path.join(STATE_DIR, "users", re.sub(r"[^A-Za-z0-9_.-]+", "_", u))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{key}.json")

def load_progress() -> Dict[str, dict]:
    data = _read_json(_user_file("progress"), {})
    for t in get_topics():
        data.setdefault(t, {"total":0,"correct":0,"last_seen":None})
    return data

def save_progress(d): _write_json(_user_file("progress"), d)

def load_history() -> List[Dict]:
    return _read_json(_user_file("history"), [])

def save_history(arr: List[Dict]):
    _write_json(_user_file("history"), arr)

def record_attempt(topic: str, qid: str, correct: bool):
    hist = load_history()
    hist.append({"ts": int(time.time()), "topic": topic, "id": qid, "correct": bool(correct)})
    save_history(hist)
    prog = load_progress()
    rec = prog.get(topic, {"total":0,"correct":0,"last_seen":None})
    rec["total"] += 1
    if correct: rec["correct"] += 1
    rec["last_seen"] = int(time.time())
    save_progress(prog)

def overall_accuracy() -> float:
    prog = load_progress()
    tot = sum(v.get("total",0) for v in prog.values())
    cor = sum(v.get("correct",0) for v in prog.values())
    return (cor / tot) if tot else 0.0

# ------------------------------------------------------------------ #
# SPACED REPETITION (SM-2 lite)
# ------------------------------------------------------------------ #
def _now_day_ts() -> int:
    today = dt.date.today()
    return int(time.mktime(dt.datetime(today.year,today.month,today.day).timetuple()))

def load_sr() -> Dict[str, Dict]:
    return _read_json(_user_file("sr"), {})

def save_sr(srobj: Dict[str, Dict]):
    _write_json(_user_file("sr"), srobj)

def sr_due_ids(limit:int=20, subjects: Optional[List[str]]=None) -> List[str]:
    df = load_questions_frame()
    if df.empty: return []
    sr = load_sr(); today = _now_day_ts(); ids=[]
    for _, r in df.iterrows():
        qid = r["id"]; d = sr.get(qid); due_ts = d["due_ts"] if d else today
        if due_ts <= today: ids.append(qid)
    if not ids:
        upcoming = sorted(((q, sr.get(q, {"due_ts":today})["due_ts"]) for q in df["id"].tolist()), key=lambda x:x[1])
        ids = [q for q,_ in upcoming[:limit]]
    return ids[:limit]

def sr_update(qid:str, was_correct:bool):
    sr = load_sr()
    if qid not in sr:
        sr[qid] = {"reps":0,"interval":0.0,"ease":2.5,"due_ts":_now_day_ts(),"last_result":None}
    rec = sr[qid]
    quality = 4 if was_correct else 2
    ease = rec.get("ease",2.5); reps = rec.get("reps",0); interval = rec.get("interval",0.0)
    if was_correct:
        if reps==0: interval=1
        elif reps==1: interval=6
        else: interval=round(interval*ease)
        reps += 1
        ease = max(1.3, ease + 0.1 - (5-quality)*(0.08 + (5-quality)*0.02))
    else:
        reps = 0; interval = 1; ease = max(1.3, ease - 0.2)
    due_date = dt.date.today() + dt.timedelta(days=int(interval))
    due_ts = int(time.mktime(dt.datetime(due_date.year,due_date.month,due_date.day).timetuple()))
    rec.update({"reps":reps,"interval":float(interval),"ease":float(ease),"due_ts":due_ts,"last_result":int(was_correct)})
    sr[qid]=rec
    save_sr(sr)

# ------------------------------------------------------------------ #
# SESSION DEFAULTS
# ------------------------------------------------------------------ #
def ensure_session_keys():
    defaults = {
        "auth_user": None,
        "view": "dashboard",
        "active_topic": None,
        "quiz_mode": "normal",
        "quiz_pool": None,
        "quiz_idx": 0,
        "quiz_answers": {},
        "quiz_revealed": set(),
        "quiz_finished": False,
        "rail_open": True,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
