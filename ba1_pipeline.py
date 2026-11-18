#!/usr/bin/env python3
"""
BA-1 pipeline: Етап 1 (звірка реєстру з SEC API) + Етап 2 (витягування Item 1A).

Встановлення (один раз):
    python3 -m venv .venv && .venv/bin/pip install requests beautifulsoup4 lxml openpyxl

Запуск (у папці з трьома xlsx «Таблиця 1» від EPE):
    .venv/bin/python ba1_pipeline.py stage1  --email you@domain
    .venv/bin/python ba1_pipeline.py extract --email you@domain --only KO:2025 CAG:2021   # пробний запуск
    .venv/bin/python ba1_pipeline.py extract --email you@domain                          # усі 40

Пошту можна також передати через змінну SEC_EMAIL. Відповіді SEC кешуються в out/cache/,
тому повторні запуски не ходять у мережу (і пошта для них не потрібна).

Результати:
    out/Table1_reconciled.xlsx  — Register, Discrepancies, Special cases, Item1A_log, Legend
    out/item1a/{TICKER}_FY{YYYY}_item1a.txt
    out/review_sample.csv
    out/state.json              — проміжний стан між етапами
"""
import argparse, csv, datetime as dt, glob, hashlib, json, os, re, sys, time
from collections import Counter
from pathlib import Path

OUT = Path("out")
CACHE = OUT / "cache"
TXT = OUT / "item1a"
STATE = OUT / "state.json"
STATE1 = OUT / "state_stage1.json"     # знімок після Етапу 1: extract завжди стартує з нього
XLSX = OUT / "Table1_reconciled.xlsx"
YEARS = range(2021, 2026)
ACC_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
FIELDS = ["Fiscal Year End", "Filing Date", "Accession No.", "Link"]   # звіряються з API
FORMS = {"10-K", "10-K/A", "10-K405", "10-KT", "10-KT/A", "NT 10-K", "NT 10-K/A"}
BIG4 = [("KPMG", "KPMG"), ("PRICEWATERHOUSECOOPERS", "PwC"), ("ERNST & YOUNG", "EY"), ("DELOITTE", "Deloitte")]
FYE_RULE = {
    "KO": "31 грудня", "MDLZ": "31 грудня", "HSY": "31 грудня",
    "CAG": "остання неділя травня", "GIS": "остання неділя травня",
    "CPB": "неділя, найближча до 31 липня", "KHC": "остання субота грудня",
    "TSN": "субота, найближча до 30 вересня",
}


# ================================================================ helpers
def nearest_weekday(target, wd):
    fwd = (wd - target.weekday()) % 7
    return target + dt.timedelta(fwd) if fwd <= 3 else target - dt.timedelta(7 - fwd)


def last_weekday(last, wd):
    return last - dt.timedelta((last.weekday() - wd) % 7)


def expected_fye(tk, y):
    """Очікувана дата кінця FY за правилом компанії (Mon=0 … Sun=6)."""
    if tk in ("KO", "MDLZ", "HSY"):
        return dt.date(y, 12, 31)
    if tk in ("CAG", "GIS"):
        return last_weekday(dt.date(y, 5, 31), 6)
    if tk == "KHC":
        return last_weekday(dt.date(y, 12, 31), 5)
    if tk == "CPB":
        return nearest_weekday(dt.date(y, 7, 31), 6)
    if tk == "TSN":
        return nearest_weekday(dt.date(y, 9, 30), 5)
    return None


def norm_date(v):
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v)
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m[0] if m else ""


def split_note(v):
    """Розділяє значення клітинки та дописану примітку: '25.12.2021 (перевірити)' -> ('25.12.2021', 'перевірити')."""
    if v is None:
        return "", ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v, ""
    s = str(v).strip()
    if s.lower().startswith("не знайдено"):
        return "", s
    notes = re.findall(r"\(([^)]*)\)", s)
    return re.sub(r"\s*\([^)]*\)", "", s).strip(), "; ".join(notes)


def is_direct_link(u):
    return (u.startswith("https://www.sec.gov/Archives/edgar/data/")
            and not re.search(r"-index\.html?$", u))


def edgar_link(cik, acc, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"


def big4(name):
    u = (name or "").upper()
    return next((short for key, short in BIG4 if key in u), "")


def firm_key(name):
    return big4(name) or re.sub(r"[^a-z]", "", (name or "").lower().replace("llp", ""))


# ================================================================ SEC client
class SEC:
    def __init__(self, email):
        self.email = email
        self.s = None
        self.last = 0.0
        self.net = 0
        CACHE.mkdir(parents=True, exist_ok=True)

    def _session(self):
        if self.s is None:
            if not self.email or "@" not in self.email:
                sys.exit("Потрібен мережевий запит до SEC, а пошти немає: додайте --email you@domain "
                         "або змінну SEC_EMAIL.")
            import requests
            self.s = requests.Session()
            self.s.headers.update({"User-Agent": f"FoodRiskResearch {self.email}",
                                   "Accept-Encoding": "gzip, deflate"})
        return self.s

    def fetch(self, url, method="GET"):
        """Повертає (HTTP-статус, байти). Остаточні відповіді (200/404/410) кешуються на диск."""
        h = hashlib.sha1(f"{method} {url}".encode()).hexdigest()
        body_f, meta_f = CACHE / h, CACHE / f"{h}.json"
        if meta_f.exists():
            m = json.loads(meta_f.read_text())
            body = body_f.read_bytes() if (method == "GET" and m["status"] == 200) else b""
            return m["status"], body
        import requests
        s = self._session()
        status, content = None, b""
        for attempt in range(6):
            wait = 0.15 - (time.time() - self.last)     # ≈ 6–7 запитів/с (ліміт SEC — 10/с)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.net += 1
            try:
                r = s.request(method, url, timeout=60, allow_redirects=True)
            except requests.RequestException as e:
                print(f"   ! мережа: {e}; повтор", file=sys.stderr)
                time.sleep(2 * 2 ** attempt)
                continue
            status, content = r.status_code, r.content
            if status in (403, 429, 503) or status >= 500:
                print(f"   ! {status} для {url}; пауза {2 * 2 ** attempt} с", file=sys.stderr)
                time.sleep(2 * 2 ** attempt)
                continue
            break
        if status in (200, 404, 410):
            if status == 200 and method == "GET":
                body_f.write_bytes(content)
            meta_f.write_text(json.dumps({"url": url, "method": method, "status": status,
                                          "fetched": dt.datetime.now().isoformat(timespec="seconds")}))
        return status, content if method == "GET" else b""

    def json(self, url):
        st, b = self.fetch(url)
        if st != 200:
            raise RuntimeError(f"{url}: HTTP {st}")
        return json.loads(b)


# ================================================================ ЕТАП 1
def read_epe(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and str(r[0] or "").strip() == "Company")
    hdr = [str(c).strip() if c is not None else "" for c in rows[h]]
    m = re.search(r"EPE[ _\-]?(\d)", Path(path).name)
    epe = f"EPE-{m[1]}" if m else Path(path).stem
    out = []
    for r in rows[h + 1:]:
        if not r or not r[0]:
            continue
        d = dict(zip(hdr, r))
        notes = []
        rec = {"Company": str(d["Company"]).strip(), "Ticker": str(d["Ticker"]).strip(),
               "CIK": re.sub(r"\D", "", str(d["CIK"])).zfill(10),
               "Exchange": d.get("Exchange") or "",
               "Fiscal Year": int(re.search(r"\d{4}", str(d["Fiscal Year"]))[0]),
               "Form": str(d.get("Form") or "10-K").strip(), "EPE": epe, "Source": Path(path).name}
        for k in ("Fiscal Year End", "Filing Date"):
            v, n = split_note(d.get(k))
            rec[k] = norm_date(v)
            if n:
                notes.append(f"{k}: {n}")
        v, n = split_note(d.get("Accession No."))
        am = ACC_RE.search(str(v))
        rec["Accession No."] = am[0] if am else ""
        if n:
            notes.append(f"Accession: {n}")
        v, n = split_note(d.get("Link"))
        v = v.split()[0] if v else ""
        rec["Link"] = v if is_direct_link(v) else ""
        if v and not is_direct_link(v):
            rec["Link (EPE, непряме)"] = v
            notes.append(f"Link EPE не є прямим посиланням на документ EDGAR: {v}")
        if n and not (n.lower().startswith("не знайдено") and not v):
            notes.append(f"Link: {n}")
        v, n = split_note(d.get("Auditor"))
        rec["Auditor"] = v
        if n:
            notes.append(f"Auditor: {n}")
        rec["Big Four"] = str(d.get("Big Four") or "").strip()
        rec["Item 1A Status"] = str(d.get("Item 1A Status") or "Not started").strip()
        rec["Comment"] = str(d.get("Comment") or "").strip()
        rec["EPE notes"] = "; ".join(notes)
        out.append(rec)
    return out


def company_filings(sec, cik):
    j = sec.json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    blocks = [("recent", j["filings"]["recent"])]
    for f in j["filings"].get("files", []):
        blocks.append((f["name"], sec.json(f"https://data.sec.gov/submissions/{f['name']}")))
    seen, rows = set(), []
    for src, b in blocks:
        for i, form in enumerate(b["form"]):
            if form in FORMS and b["accessionNumber"][i] not in seen:
                seen.add(b["accessionNumber"][i])
                rows.append({"form": form, "accessionNumber": b["accessionNumber"][i],
                             "filingDate": b["filingDate"][i], "reportDate": b["reportDate"][i],
                             "primaryDocument": b["primaryDocument"][i], "src": src})
    return j, rows


def cmd_stage1(a):
    sec = SEC(a.email)
    inputs = a.inputs or sorted(p for p in glob.glob("*.xlsx") if not p.startswith("~$"))
    rows = []
    for p in inputs:
        rows += read_epe(p)
    dropped = [r for r in rows if r["Fiscal Year"] not in YEARS]
    rows = sorted((r for r in rows if r["Fiscal Year"] in YEARS), key=lambda r: (r["Ticker"], r["Fiscal Year"]))
    print(f"Зведено {len(rows)} рядків із {len(inputs)} файлів; виключено поза FY2021–FY2025: "
          + (", ".join(f"{r['Ticker']} FY{r['Fiscal Year']}" for r in dropped) or "—"))
    by_t = {}
    for r in rows:
        by_t.setdefault(r["Ticker"], []).append(r["Fiscal Year"])
    problems = []
    for t, ys in by_t.items():
        c = Counter(ys)
        miss = sorted(set(YEARS) - set(ys))
        dup = [y for y, n in c.items() if n > 1]
        if miss:
            problems.append(f"{t}: бракує FY {miss}")
        if dup:
            problems.append(f"{t}: дублікати FY {dup}")
    if len(rows) != 40 or problems:
        sys.exit("Реєстр не має 40 унікальних рядків — зупиняюсь.\n  " + "\n  ".join(problems or [f"рядків: {len(rows)}"]))

    disc, special = [], []
    # ручні виправлення BA-1 (corrections.csv): застосовуються лише якщо в клітинці EPE саме Old,
    # слід лишається в Comment і в Discrepancies (поле «… (виправлено BA-1)»)
    corr = Path("corrections.csv")
    if corr.exists():
        idx = {(r["Ticker"], r["Fiscal Year"]): r for r in rows}
        for c in csv.DictReader(open(corr, encoding="utf-8")):
            r = idx.get((c["Ticker"], int(c["Fiscal Year"])))
            if not r or c["Field"] not in r:
                print(f"  ! виправлення не застосовано (немає рядка/поля): {c}")
                continue
            if r[c["Field"]] != c["Old"]:
                print(f"  ! {c['Ticker']} FY{c['Fiscal Year']} {c['Field']}: очікувалось «{c['Old']}», "
                      f"у таблиці «{r[c['Field']]}» — не змінюю")
                continue
            r[c["Field"]] = c["New"]
            note = f"{c['Field']} виправлено BA-1: було «{c['Old']}» ({r['EPE']}), стало «{c['New']}» — {c['Reason']}"
            r["Comment"] = "; ".join(x for x in [r["Comment"], note] if x)
            disc.append([r["Ticker"], r["Fiscal Year"], f"{c['Field']} (виправлено BA-1)", c["Old"], c["New"], c["Reason"]])
    filings = {}
    for cik in sorted({r["CIK"] for r in rows}):
        tk = next(r["Ticker"] for r in rows if r["CIK"] == cik)
        meta, fl = company_filings(sec, cik)
        filings[cik] = fl
        print(f"  {tk}: {meta['name']} — {len(fl)} подань 10-K/10-K/A/NT у {1 + len(meta['filings'].get('files', []))} файлах API")
        fye = meta.get("fiscalYearEnd") or ""
        special.append([tk, cik, "fiscalYearEnd (API)", fye,
                        f"MMDD з профілю компанії в EDGAR (для 52/53-тижневих років — орієнтир, "
                        f"фактичні дати див. API Fiscal Year End); правило: {FYE_RULE.get(tk, '?')}"])
        special.append([tk, cik, "Назва в API", meta["name"], ""])
        for fn in meta.get("formerNames", []):
            frm, to = (fn.get("from") or "")[:10], (fn.get("to") or "")[:10]
            in_period = to >= "2021-01-01"
            special.append([tk, cik, "Зміна назви (formerNames)" + (" — у період дослідження" if in_period else ""),
                            f"{fn['name']} → {meta['name']}", f"стара назва діяла {frm} – {to}"])
        for f in fl:
            in_scope = (f["reportDate"][:4] in {str(y) for y in YEARS}) or \
                       (not f["reportDate"] and "2021-01-01" <= f["filingDate"] <= "2026-12-31")
            if f["form"] != "10-K" and in_scope:
                special.append([tk, cik, f["form"], f["accessionNumber"],
                                f"подано {f['filingDate']}, звітний період {f['reportDate'] or '—'}; "
                                f"{edgar_link(cik, f['accessionNumber'], f['primaryDocument'])}"])

    for r in rows:
        fy, tk = r["Fiscal Year"], r["Ticker"]
        exp = expected_fye(tk, fy)
        cands = sorted((f for f in filings[r["CIK"]] if f["form"] == "10-K" and f["reportDate"][:4] == str(fy)),
                       key=lambda f: f["filingDate"])
        r["Auto-filled"] = ""
        if not cands:
            r["API status"] = "НЕМАЄ 10-K в API"
            r["Link HTTP"] = "—"
            r["Comment"] = "; ".join(x for x in [r["Comment"], f"10-K з reportDate у {fy} в API SEC не знайдено"] if x)
            disc.append([tk, fy, "10-K", "", "", "у submissions API немає 10-K з reportDate у цьому році"])
            continue
        if len(cands) > 1:
            special.append([tk, r["CIK"], "Кілька 10-K за FY",
                            ", ".join(c["accessionNumber"] for c in cands), "взято найраніший (оригінал)"])
        f = cands[0]
        api = {"Fiscal Year End": f["reportDate"], "Filing Date": f["filingDate"],
               "Accession No.": f["accessionNumber"],
               "Link": edgar_link(r["CIK"], f["accessionNumber"], f["primaryDocument"])}
        r["API Form"] = f["form"]
        r["API source"] = f["src"]
        filled, bad = [], []
        for k in FIELDS:
            r[f"API {k}"] = api[k]
            if not r[k]:
                r[k] = api[k]
                filled.append(k)
            elif r[k] != api[k]:
                bad.append(k)
                disc.append([tk, fy, k, r[k], api[k], "ручне значення не збігається з API (не перезаписано)"])
        r["Auto-filled"] = ", ".join(filled)
        r["FYE rule"] = exp.isoformat() if exp else ""
        r["FYE rule OK"] = "так" if exp and exp.isoformat() == f["reportDate"] else "НІ"
        if r["FYE rule OK"] != "так":
            special.append([tk, r["CIK"], "FYE не за правилом", f"FY{fy}: API {f['reportDate']}",
                            f"за правилом «{FYE_RULE.get(tk)}» очікувалось {r['FYE rule']}"])
        if r["Form"] != "10-K":
            disc.append([tk, fy, "Form", r["Form"], f["form"], "форма в реєстрі EPE відрізняється"])
            bad.append("Form")
        r["API status"] = ("розбіжність: " + ", ".join(bad)) if bad else \
                          ("заповнено з API: " + ", ".join(filled)) if filled else "збіг"
        if filled:
            r["Comment"] = "; ".join(x for x in [r["Comment"], "Заповнено автоматично з SEC API: " + ", ".join(filled)] if x)

        # перевірка посилань (HEAD; якщо сервер не підтримує HEAD — GET)
        def check(u):
            st, _ = sec.fetch(u, "HEAD")
            if st not in (200, 404, 410):
                st, _ = sec.fetch(u)
            return st
        r["Link HTTP"] = str(check(r["Link"]))
        if r["Link"] != api["Link"]:
            r["Link HTTP"] += f" (API-посилання: {check(api['Link'])})"
        if not r["Link HTTP"].startswith("200"):
            r["Comment"] = "; ".join(x for x in [r["Comment"], f"посилання не відкривається: HTTP {r['Link HTTP']}"] if x)

    STATE.parent.mkdir(parents=True, exist_ok=True)
    for f in (STATE1, STATE):
        f.write_text(json.dumps({"rows": rows, "disc": disc, "special": special}, ensure_ascii=False, indent=1))
    write_xlsx(rows, disc, special, None)
    n_match = sum(r["API status"] == "збіг" for r in rows)
    n_fill = sum(r["API status"].startswith("заповнено") for r in rows)
    print(f"\nЗвірено 40 рядків: повний збіг {n_match}, збіг + заповнено з API {n_fill}, "
          f"з розбіжностями {sum(r['API status'].startswith('розбіжність') for r in rows)}, "
          f"без 10-K {sum(r['API status'].startswith('НЕМАЄ') for r in rows)}.")
    print("Заповнено з API:")
    for r in rows:
        if r["Auto-filled"]:
            print(f"  {r['Ticker']} FY{r['Fiscal Year']}: {r['Auto-filled']}")
    print("Розбіжності:" if disc else "Розбіжностей немає.")
    for d in disc:
        print(f"  {d[0]} FY{d[1]} {d[2]}: EPE «{d[3]}» vs API «{d[4]}»")
    print("Посилання не 200:", [f"{r['Ticker']} FY{r['Fiscal Year']}: {r['Link HTTP']}" for r in rows
                                if not r["Link HTTP"].startswith("200")] or "—")
    print("Special cases:")
    for s in special:
        print("  " + " | ".join(str(x) for x in s))
    print(f"Мережевих запитів: {sec.net}.  → {XLSX}")


# ================================================================ ЕТАП 2
BLOCK = ["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section",
         "ul", "ol", "center", "pre", "hr", "blockquote", "dt", "dd", "font_block"]
SEP = r"[\s.:\-–—]*"
START = re.compile(rf"(?im)^item\s*1a{SEP}risk\s+factors\.?[ \t]*$")
START_LOOSE = re.compile(rf"(?im)^item\s*1a{SEP}risk\s+factors\b")
END = re.compile(rf"(?im)^item\s*(?:1b{SEP}unresolved\s+staff|1c{SEP}cybersecurity|2{SEP}(?:description\s+of\s+)?propert)")
JUNK_LINE = re.compile(r"(?im)^(?:\d{1,3}|[ivx]{1,5}|page\s*\d{1,3}|table\s+of\s+contents|index|back\s+to\s+contents)$\n?")
# колонтитул: короткий рядок із «Form 10-K», що закінчується номером сторінки («The Hershey Company | 2023 Form 10-K | Page 15»)
FOOTER = re.compile(r"(?im)^(?=.{0,100}$)[^\n]*\bform\s+10-k\b[^\n]*?(?:\bpage\s*)?\d{1,3}$\n?")
AUD = re.compile(r"/s/\s*([A-Z][A-Za-z&.,'’\s\-]{1,60}?\bLLP)\b")   # \s: слова підпису можуть бути в окремих блоках


def html_to_text(raw):
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(raw, "lxml")
    for t in soup.find_all(["script", "style", "head", "ix:header"]):
        t.decompose()
    for t in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        if not t.decomposed:
            t.decompose()
    # верстка «з PDF» (GIS): пробіл = порожній inline-block div, рядок = div з position:absolute
    for t in soup.find_all(style=re.compile(r"display\s*:\s*inline-block", re.I)):
        if not t.get_text(strip=True):
            t.replace_with(" ")
    prev_top, prev_font = None, None
    for t in soup.find_all(style=re.compile(r"position\s*:\s*absolute", re.I)):
        sty = t.get("style", "")
        m = re.search(r"top\s*:\s*(-?[\d.]+)px", sty)
        top = float(m[1]) if m else None
        font = tuple(re.findall(r"font-(?:weight|style)\s*:\s*([\w-]+)", sty))   # зміна жирного/курсиву = заголовок
        same_line = prev_top is not None and top is not None and abs(top - prev_top) < 1
        same_par = same_line or (prev_top is not None and top is not None and 0 < top - prev_top <= 20
                                 and font == prev_font)
        t.insert_before(" " if same_par else "\n\n")
        t.unwrap()
        prev_top, prev_font = top, font
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for t in soup.find_all(["td", "th"]):
        t.append(" ")
    for t in soup.find_all(BLOCK):
        t.insert_before("\n")
        t.append("\n")
    txt = soup.get_text("")
    txt = re.sub(r"[\xa0\u2002\u2003\u2009\u202f]", " ", txt).replace("\u200b", "").replace("\ufeff", "")
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r" +([,.;:)])", r"\1", txt)                      # «Progresso ,» → «Progresso,»
    txt = "\n".join(line.strip() for line in txt.split("\n"))
    txt = re.sub(r"(?m)^([•●▪◦·])\n+", r"\1 ", txt)          # маркер списку в окремій комірці → до тексту
    return re.sub(r"\n{3,}", "\n\n", txt)


def find_item1a(text):
    """-> (body, info). Серед усіх заголовків Item 1A (окремий рядок) бере той, від якого до
    найближчого Item 1B/1C/2 найдовший відрізок: рядок змісту дає короткий відрізок, а перехресні
    посилання («see Item 1A…») не є окремим рядком і в пошук не потрапляють."""
    info = {"start": False, "end": False, "loose": False, "end_heading": ""}
    starts = list(START.finditer(text))
    if not starts:
        starts = [m for m in START_LOOSE.finditer(text)]
        info["loose"] = bool(starts)
    if not starts:
        return "", info
    info["start"] = True
    ends = list(END.finditer(text))
    best, best_end = None, None
    for s in starts:
        nxt = next((e for e in ends if e.start() > s.end()), None)
        if nxt and (best is None or nxt.start() - s.start() > best_end.start() - best.start()):
            best, best_end = s, nxt
    if not best:
        return "", info
    info["end"] = True
    info["end_heading"] = best_end.group(0).replace("\n", " ")
    body = FOOTER.sub("", JUNK_LINE.sub("", text[best.start():best_end.start()]))
    body = re.sub(r"([a-z,;])\n+([a-z])", r"\1 \2", body)     # абзац, розірваний межею сторінки
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body, info


def nwords(t):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", t))


def find_auditor(text):
    hits = [re.sub(r"\s+", " ", m[1]).strip(" ,") for m in AUD.finditer(text)]
    hits = [h for h in hits if len(h) > 5]
    if not hits:
        return "", ""
    c = Counter(hits)
    top = c.most_common(1)[0][0]
    return top, ("; також: " + ", ".join(k for k in c if k != top)) if len(c) > 1 else ""


def extract_one(sec, r):
    """Завантажує документ, вирізає Item 1A. Повертає dict з результатами (не змінює r)."""
    link = r.get("API Link") or r.get("Link") or ""
    res = {"link": link, "http": "", "words": 0, "file": "", "body": "", "flags": [], "fail": "",
           "auditor": "", "auditor_note": "", "end_heading": ""}
    if not is_direct_link(link):
        res["fail"] = "немає прямого посилання на документ 10-K"
        return res
    st, raw = sec.fetch(link)
    res["http"] = st
    if st != 200:
        res["fail"] = f"документ не завантажився (HTTP {st})"
        return res
    text = html_to_text(raw)
    res["auditor"], res["auditor_note"] = find_auditor(text)
    body, info = find_item1a(text)
    res["end_heading"] = info["end_heading"]
    if not info["start"]:
        res["flags"].append("немає заголовка початку Item 1A")
        res["fail"] = "заголовок «Item 1A. Risk Factors» не знайдено"
        return res
    if not info["end"]:
        res["flags"].append("немає заголовка кінця (Item 1B/1C/2)")
        res["fail"] = "після Item 1A не знайдено заголовка Item 1B / 1C / 2"
        return res
    if info["loose"]:
        res["flags"].append("заголовок початку знайдено нестрогим пошуком")
    res["body"] = body
    res["words"] = nwords(body)
    tail = body.rstrip()[-1:] if body else ""
    if tail and tail not in '.!?"”)’':
        res["flags"].append(f"закінчується посеред речення («…{body.rstrip()[-40:]}»)")
    if res["words"] < 2000:
        res["flags"].append(f"менше 2000 слів ({res['words']})")
    return res


def cmd_extract(a):
    if not STATE1.exists():
        sys.exit("Спершу запустіть stage1.")
    st = json.loads(STATE1.read_text())
    rows, disc, special = st["rows"], st["disc"], st["special"]
    sec = SEC(a.email)
    TXT.mkdir(parents=True, exist_ok=True)
    only = {(s.split(":")[0].upper(), int(s.split(":")[1])) for s in (a.only or [])}
    targets = [r for r in rows if not only or (r["Ticker"], r["Fiscal Year"]) in only]

    if only:   # пробний режим: тільки показати результат, state/xlsx не чіпати
        for r in targets:
            res = extract_one(sec, r)
            name = f"{r['Ticker']}_FY{r['Fiscal Year']}_item1a.txt"
            if res["body"]:
                (TXT / name).write_text(res["body"], encoding="utf-8")
            print(f"\n================ {r['Ticker']} FY{r['Fiscal Year']}  ({res['link']})")
            print(f"слів: {res['words']}; кінець на: «{res['end_heading']}»; аудитор: {res['auditor'] or '—'}"
                  f"; позначки: {'; '.join(res['flags']) or 'немає'}{'; ПОМИЛКА: ' + res['fail'] if res['fail'] else ''}")
            if res["body"]:
                print("---- перші 300 символів ----")
                print(res["body"][:300])
                print("---- останні 300 символів ----")
                print(res["body"][-300:])
        return

    log, prev = [], {}
    disc = [d for d in disc if d[2] not in ("Auditor", "Big Four")]
    for r in sorted(rows, key=lambda r: (r["Ticker"], r["Fiscal Year"])):
        tk, fy = r["Ticker"], r["Fiscal Year"]
        name = f"{tk}_FY{fy}_item1a.txt"
        res = extract_one(sec, r)
        flags = list(res["flags"])
        p = prev.get(tk)
        change = ""
        if res["words"] and p:
            ch = (res["words"] - p) / p
            change = f"{ch:+.0%}"
            if abs(ch) > 0.40:
                flags.append(f"зміна довжини {ch:+.0%} проти FY{fy - 1} ({p} → {res['words']})")
        prev[tk] = res["words"] or None
        old_status = r["Item 1A Status"]
        if res["body"] and not res["fail"]:
            (TXT / name).write_text(res["body"], encoding="utf-8")
            r["File"] = f"item1a/{name}"
            if old_status != "Reviewed":
                r["Item 1A Status"] = "Extracted"
        else:
            r["File"] = ""
            flags.append(res["fail"])
            r["Comment"] = "; ".join(x for x in [r["Comment"], f"потрібне ручне копіювання: {res['fail']}"] if x)
            if (TXT / name).exists():
                (TXT / name).unlink()
        # аудитор
        r["Auditor (10-K)"] = res["auditor"]
        r["Big Four (10-K)"] = ("Так (" + big4(res["auditor"]) + ")") if big4(res["auditor"]) else ("Ні" if res["auditor"] else "")
        if not res["auditor"] and res["http"] == 200:
            flags.append("підпис аудитора «/s/ … LLP» не знайдено")
        elif res["auditor"]:
            if not r["Auditor"]:
                r["Auditor"] = res["auditor"]
                r["Auto-filled"] = ", ".join(x for x in [r["Auto-filled"], "Auditor (з 10-K)"] if x)
            elif firm_key(r["Auditor"]) != firm_key(res["auditor"]):
                disc.append([tk, fy, "Auditor", r["Auditor"], res["auditor"], "аудитор у підписі 10-K інший"])
            epe_b4 = r["Big Four"].lower().startswith(("так", "yes", "y"))
            if epe_b4 != bool(big4(res["auditor"])):
                disc.append([tk, fy, "Big Four", r["Big Four"], r["Big Four (10-K)"], "позначка Big Four не відповідає підпису"])
        if res["auditor_note"]:
            flags.append("кілька підписів аудиторів" + res["auditor_note"])
        r["Words"] = res["words"]
        r["Flags"] = "; ".join(flags)
        log.append({"Ticker": tk, "FY": fy, "Link used": res["link"], "HTTP": res["http"],
                    "End heading": res["end_heading"], "Words": res["words"], "Change vs prev FY": change,
                    "Auditor (10-K)": res["auditor"], "Status before": old_status,
                    "Status after": r["Item 1A Status"], "Flags": r["Flags"] or "OK", "File": r["File"] or "—"})
        print(f"{tk:5} FY{fy}: {res['words']:>6} слів  {change:>6}  {r['Flags'] or 'OK'}")

    STATE.write_text(json.dumps({"rows": rows, "disc": disc, "special": special}, ensure_ascii=False, indent=1))
    write_xlsx(rows, disc, special, log)

    # вибірка для ручної звірки: по 1 звіту на компанію — спершу з позначками, далі найновіші
    sample = []
    for tk in sorted({r["Ticker"] for r in rows}):
        rs = sorted((r for r in rows if r["Ticker"] == tk), key=lambda r: (bool(r.get("Flags")), r["Fiscal Year"]), reverse=True)
        r = rs[0]
        sample.append({"Ticker": tk, "Fiscal Year": r["Fiscal Year"], "Company": r["Company"], "EPE": r["EPE"],
                       "Reason": "є позначки" if r.get("Flags") else "найновіший звіт (позначок немає)",
                       "Flags": r.get("Flags", ""), "Words": r.get("Words", ""), "File": r.get("File", ""),
                       "Link": r["Link"]})
    with open(OUT / "review_sample.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(sample[0]))
        w.writeheader()
        w.writerows(sample)

    n_files = sum(1 for r in rows if r.get("File"))
    print(f"\nФайлів Item 1A: {n_files}/40 у {TXT}/;  позначених звітів: {sum(1 for r in rows if r.get('Flags'))}")
    print("Розбіжності (усього):")
    for d in disc:
        print(f"  {d[0]} FY{d[1]} {d[2]}: EPE «{d[3]}» vs «{d[4]}» — {d[5]}")
    print(f"Мережевих запитів: {sec.net}.  → {XLSX}, {OUT / 'review_sample.csv'}")


# ================================================================ xlsx
REG_COLS = ["Company", "Ticker", "CIK", "Exchange", "EPE", "Fiscal Year",
            "Fiscal Year End", "API Fiscal Year End", "FYE rule", "FYE rule OK",
            "Filing Date", "API Filing Date", "Form", "API Form",
            "Accession No.", "API Accession No.", "Link", "API Link", "Link HTTP",
            "Auditor", "Auditor (10-K)", "Big Four", "Big Four (10-K)",
            "Item 1A Status", "Words", "Flags", "File",
            "API status", "Auto-filled", "Comment", "EPE notes", "Source"]


def write_xlsx(rows, disc, special, log):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    yellow = PatternFill("solid", fgColor="FFF2CC")
    red = PatternFill("solid", fgColor="F8CBAD")
    blue = PatternFill("solid", fgColor="DDEBF7")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Register"
    ws.append(REG_COLS)
    ci = {c: i for i, c in enumerate(REG_COLS)}
    for r in sorted(rows, key=lambda r: (r["Ticker"], r["Fiscal Year"])):
        ws.append([r.get(c, "") for c in REG_COLS])
        cells = ws[ws.max_row]
        hard = r["API status"].startswith("НЕМАЄ") or (log is not None and not r.get("File")) \
            or not str(r.get("Link HTTP", "")).startswith("200")
        soft = r["API status"].startswith("розбіжність") or r.get("Flags") or r.get("FYE rule OK") == "НІ"
        if hard or soft:
            for c in cells:
                c.fill = red if hard else yellow
        for k in [x.strip() for x in r.get("Auto-filled", "").split(",") if x.strip()]:
            k = "Auditor" if k.startswith("Auditor") else k
            if k in ci:
                cells[ci[k]].fill = blue
    sheets = [("Discrepancies", ["Ticker", "FY", "Поле", "EPE (вручну)", "API / 10-K", "Примітка"], disc),
              ("Special cases", ["Ticker", "CIK", "Тип", "Значення", "Деталі"], special)]
    if log:
        sheets.append(("Item1A_log", list(log[0]), [list(x.values()) for x in log]))
    for name, hdr, data in sheets:
        s = wb.create_sheet(name)
        s.append(hdr)
        for x in data:
            s.append(x)
    lg = wb.create_sheet("Legend")
    for row in [["Позначка", "Значення"],
                ["Червоний рядок", "немає 10-K / посилання не 200 / Item 1A не витягнуто — потрібне ручне втручання"],
                ["Жовтий рядок", "розбіжність з API, FYE не за правилом або позначки Item 1A (Flags)"],
                ["Блакитна клітинка", "значення заповнено автоматично з SEC API (див. колонку Auto-filled)"],
                ["API …", "значення з data.sec.gov/submissions (filings.recent + filings.files)"],
                ["FYE rule", "дата кінця FY, розрахована за правилом компанії"],
                ["Words", "кількість слів у вирізаному Item 1A (без рядків-номерів сторінок і «Table of Contents»)"]]:
        lg.append(row)
    for s in wb.worksheets:
        for c in s[1]:
            c.font = Font(bold=True)
        s.freeze_panes = "A2"
        for col in s.columns:
            w = max(len(str(c.value or "")) for c in col)
            s.column_dimensions[col[0].column_letter].width = min(55, max(9, w + 2))
            for c in col[1:]:
                c.alignment = Alignment(vertical="top", wrap_text=w > 55)
    ws.auto_filter.ref = ws.dimensions
    XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    s1 = sp.add_parser("stage1")
    s1.add_argument("--inputs", nargs="*")
    s2 = sp.add_parser("extract")
    s2.add_argument("--only", nargs="*", help="TICKER:FY … — пробний запуск без оновлення реєстру")
    for s in (s1, s2):
        s.add_argument("--email", default=os.environ.get("SEC_EMAIL"))
    a = p.parse_args()
    {"stage1": cmd_stage1, "extract": cmd_extract}[a.cmd](a)
