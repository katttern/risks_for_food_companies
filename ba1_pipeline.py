"""
BA-1 pipeline: Етап 1 (звірка реєстру з SEC API) + Етап 2 (витягування Item 1A).

Встановлення:
    pip install requests beautifulsoup4 lxml openpyxl

Запуск (у папці, де лежать три файли Таблиці 1 від EPE):
    python ba1_pipeline.py register  --inputs Table1_EPE1*.xlsx Table1_EPE2*.xlsx *EPE_3*.xlsx
    python ba1_pipeline.py reconcile --email your.name@university.edu
    python ba1_pipeline.py extract   --email your.name@university.edu

Результати:
    out/register_manual.csv        — 40 рядків, зведено з трьох таблиць EPE
    out/Table1_reconciled.xlsx     — реєстр + дані API + розбіжності + 10-K/A і зміни назв
    out/item1a/{TICKER}_FY{YYYY}_item1a.txt
    out/Table1_reconciled.xlsx     — після extract додається аркуш Item1A_log і оновлюються статуси
"""
import argparse, csv, datetime as dt, json, os, re, sys, time
from pathlib import Path

OUT = Path("out")
YEARS = range(2021, 2026)
ACC_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
COLS = ["Company", "Ticker", "CIK", "Exchange", "Fiscal Year", "Fiscal Year End",
        "Filing Date", "Form", "Accession No.", "Link", "Auditor", "Big Four",
        "Item 1A Status", "Comment", "Source"]
BIG4 = ("KPMG", "PricewaterhouseCoopers", "Ernst & Young", "Deloitte")


# ---------------------------------------------------------------- helpers
def norm_date(v):
    """datetime / 'dd.mm.yyyy (…)' / 'yyyy-mm-dd' -> 'yyyy-mm-dd' або ''."""
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v)
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return m[0] if m else ""


def clean(v):
    s = "" if v is None else str(v).strip()
    return "" if s.lower().startswith("не знайдено") else s


class SEC:
    def __init__(self, email):
        import requests
        if not email or "@" not in email:
            sys.exit("Потрібна контактна пошта: --email you@domain (вимога SEC до User-Agent)")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": f"FoodRiskResearch {email}",
                               "Accept-Encoding": "gzip, deflate"})
        self.last = 0.0
        self.cache = OUT / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)

    def get(self, url, binary=False):
        key = self.cache / re.sub(r"[^A-Za-z0-9._-]", "_", url)[-180:]
        if key.exists():
            return key.read_bytes() if binary else key.read_text(encoding="utf-8", errors="ignore")
        for attempt in range(4):
            wait = 0.15 - (time.time() - self.last)          # ≤ ~7 запитів/с (ліміт SEC 10/с)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            r = self.s.get(url, timeout=60)
            if r.status_code == 200:
                key.write_bytes(r.content)
                return r.content if binary else r.content.decode("utf-8", errors="ignore")
            if r.status_code in (403, 429, 503):
                time.sleep(2 ** attempt * 2)
                continue
            r.raise_for_status()
        raise RuntimeError(f"SEC не віддав {url} (останній статус {r.status_code})")


# ---------------------------------------------------------------- step 1a: register
def read_epe(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and r[0] == "Company")
    hdr = [str(c).strip() if c else "" for c in rows[h]]
    out = []
    for r in rows[h + 1:]:
        if not r or not r[0]:
            continue
        d = dict(zip(hdr, r))
        fy = int(re.search(r"\d{4}", str(d["Fiscal Year"]))[0])
        acc_m = ACC_RE.search(str(d.get("Accession No.") or ""))
        link = str(d.get("Link") or "")
        link = link.split()[0] if link.startswith("https://www.sec.gov/") else ""
        notes = [clean(d.get("Comment"))]
        for k in ("Fiscal Year End", "Accession No.", "Link", "Auditor", "Filing Date"):
            raw = str(d.get(k) or "")
            if "(" in raw and not isinstance(d.get(k), dt.datetime):
                notes.append(f"{k}: {raw[raw.index('('):]}")
            if k == "Link" and raw and not link and not raw.startswith("не знайдено"):
                notes.append(f"Link (не EDGAR): {raw}")
        out.append({
            "Company": d["Company"], "Ticker": d["Ticker"],
            "CIK": str(d["CIK"]).zfill(10), "Exchange": d["Exchange"],
            "Fiscal Year": fy,
            "Fiscal Year End": norm_date(d["Fiscal Year End"]),
            "Filing Date": norm_date(d["Filing Date"]),
            "Form": d.get("Form") or "10-K",
            "Accession No.": acc_m[0] if acc_m else "",
            "Link": link,
            "Auditor": re.sub(r"\s*\(.*\)", "", clean(d.get("Auditor"))),
            "Big Four": d.get("Big Four") or "",
            "Item 1A Status": d.get("Item 1A Status") or "Not started",
            "Comment": "; ".join(n for n in notes if n),
            "Source": Path(path).name,
        })
    return out


def cmd_register(a):
    rows = []
    for p in a.inputs:
        rows += read_epe(p)
    dropped = [r for r in rows if r["Fiscal Year"] not in YEARS]
    rows = [r for r in rows if r["Fiscal Year"] in YEARS]
    rows.sort(key=lambda r: (r["Ticker"], r["Fiscal Year"]))
    OUT.mkdir(exist_ok=True)
    with open(OUT / "register_manual.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows)

    print(f"Рядків у межах FY2021–FY2025: {len(rows)} (очікується 40)")
    if dropped:
        print("Поза межами (не включено):", ", ".join(f"{r['Ticker']} FY{r['Fiscal Year']}" for r in dropped))
    tick = {}
    for r in rows:
        tick.setdefault(r["Ticker"], []).append(r["Fiscal Year"])
    for t, ys in tick.items():
        miss = sorted(set(YEARS) - set(ys))
        if miss:
            print(f"  {t}: бракує рядків за {miss}")
    print("\nНезаповнені поля (заповнить reconcile з API):")
    for r in rows:
        gaps = [k for k in ("Fiscal Year End", "Filing Date", "Accession No.", "Link", "Auditor") if not r[k]]
        if gaps or "index.htm" in r["Link"]:
            g = gaps + (["Link веде на index"] if "index.htm" in r["Link"] else [])
            print(f"  {r['Ticker']} FY{r['Fiscal Year']}: {', '.join(g)}")


# ---------------------------------------------------------------- step 1b: reconcile
def all_filings(sec, cik):
    j = json.loads(sec.get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    blocks = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        blocks.append(json.loads(sec.get(f"https://data.sec.gov/submissions/{f['name']}")))
    rows = []
    for b in blocks:
        for i, form in enumerate(b["form"]):
            if form in ("10-K", "10-K/A", "10-KT", "10-KT/A"):
                rows.append({k: b[k][i] for k in ("form", "accessionNumber", "filingDate",
                                                  "reportDate", "primaryDocument")})
    return j, rows


def edgar_link(cik, acc, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"


def cmd_reconcile(a):
    sec = SEC(a.email)
    rows = list(csv.DictReader(open(OUT / "register_manual.csv", encoding="utf-8")))
    disc, special = [], []
    by_cik = {}
    for cik in sorted({r["CIK"] for r in rows}):
        meta, fl = all_filings(sec, cik)
        by_cik[cik] = fl
        tk = meta.get("tickers") or []
        for fn in meta.get("formerNames", []):
            if fn.get("to", "")[:4] >= "2020":
                special.append([cik, ",".join(tk), "Зміна назви",
                                f"{fn['name']} (до {fn['to'][:10]}) → {meta['name']}"])
        if meta.get("fiscalYearEnd"):
            special.append([cik, ",".join(tk), "FYE (MMDD) за API", meta["fiscalYearEnd"]])
        for f in fl:
            if f["form"] != "10-K" and f["reportDate"][:4] in {str(y) for y in YEARS}:
                special.append([cik, ",".join(tk), f["form"],
                                f"{f['accessionNumber']} подано {f['filingDate']}, період {f['reportDate']}"])

    for r in rows:
        cands = [f for f in by_cik[r["CIK"]] if f["form"] == "10-K"
                 and f["reportDate"][:4] == str(r["Fiscal Year"])]
        if not cands:
            r["API status"] = "НЕМАЄ 10-K в API"
            disc.append([r["Ticker"], r["Fiscal Year"], "10-K", r["Accession No."], "—", "не знайдено в API"])
            continue
        f = sorted(cands, key=lambda x: x["filingDate"])[0]
        api = {"Fiscal Year End": f["reportDate"], "Filing Date": f["filingDate"],
               "Accession No.": f["accessionNumber"],
               "Link": edgar_link(r["CIK"], f["accessionNumber"], f["primaryDocument"])}
        flags = []
        for k, v in api.items():
            r[f"API {k}"] = v
            if not r[k]:
                r[k] = v
                flags.append(f"{k}: заповнено з API")
            elif r[k] != v:
                disc.append([r["Ticker"], r["Fiscal Year"], k, r[k], v, "розбіжність"])
                flags.append(f"{k}: розбіжність")
        r["API status"] = "OK" if not flags else "; ".join(flags)

    write_xlsx(rows, disc, special)
    n_ok = sum(1 for r in rows if r["API status"] == "OK")
    print(f"Звірено {len(rows)} рядків: повний збіг {n_ok}, з правками/розбіжностями {len(rows) - n_ok}.")
    print(f"Розбіжностей: {len(disc)}; особливих випадків (10-K/A, назви): {len(special)}")
    print(f"→ {OUT / 'Table1_reconciled.xlsx'}")


# ---------------------------------------------------------------- step 2: extract Item 1A
START = re.compile(r"(?im)^[ \t]*item[ \t]*1a\b\.?[\s\-–—:.]*risk[ \t]+factors")
END = re.compile(r"(?im)^[ \t]*item[ \t]*(?:1b\b\.?[\s\-–—:.]*unresolved|1c\b\.?[\s\-–—:.]*cybersecurity"
                 r"|2\b\.?[\s\-–—:.]*(?:description[ \t]+of[ \t]+)?propert)")
AUD = re.compile(r"/s/\s*(KPMG LLP|PricewaterhouseCoopers LLP|Ernst\s*&\s*Young LLP|Deloitte\s*&\s*Touche LLP)", re.I)


def html_to_text(raw):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(["script", "style", "ix:header"]):
        t.decompose()
    for t in soup.find_all(style=re.compile(r"display:\s*none", re.I)):
        t.decompose()
    txt = soup.get_text("\n")
    txt = txt.replace("\xa0", " ").replace("​", "")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n\n", txt)
    return txt


def find_item1a(text):
    """Повертає (текст, причина). Обирає найдовший відрізок Item 1A → наступний Item 1B/1C/2,
    тож рядок у змісті (короткий відрізок) автоматично відкидається."""
    starts = list(START.finditer(text))
    if not starts:
        return "", "немає заголовка Item 1A"
    ends = [m.start() for m in END.finditer(text)]
    best = ("", "немає заголовка кінця (1B/1C/2)")
    for s in starts:
        nxt = [e for e in ends if e > s.end()]
        if nxt and nxt[0] - s.start() > len(best[0]):
            best = (text[s.start():nxt[0]].strip(), "")
    return best


def words(t):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", t))


def cmd_extract(a):
    import openpyxl
    sec = SEC(a.email)
    xl = OUT / "Table1_reconciled.xlsx"
    if not xl.exists():
        sys.exit("Спершу запустіть reconcile")
    wb = openpyxl.load_workbook(xl)
    ws = wb["Register"]
    hdr = [c.value for c in ws[1]]
    ix = {h: i for i, h in enumerate(hdr)}
    for extra in ("Words", "Flags", "API Auditor", "File"):
        if extra not in ix:
            ws.cell(1, len(hdr) + 1, extra); hdr.append(extra); ix[extra] = len(hdr) - 1
    d = OUT / "item1a"; d.mkdir(parents=True, exist_ok=True)
    prev = {}
    rows = sorted(ws.iter_rows(min_row=2), key=lambda r: (r[ix["Ticker"]].value, int(r[ix["Fiscal Year"]].value)))
    log = []
    for r in rows:
        g = lambda k: r[ix[k]].value
        tk, fy, link = g("Ticker"), int(g("Fiscal Year")), g("Link") or ""
        fname = f"{tk}_FY{fy}_item1a.txt"
        flags = []
        if not link.startswith("https://www.sec.gov/") or link.endswith("-index.htm"):
            flags.append("немає прямого посилання на документ")
            body, n, aud = "", 0, ""
        else:
            text = html_to_text(sec.get(link))
            body, why = find_item1a(text)
            if why:
                flags.append(why)
            n = words(body)
            m = AUD.search(text)
            aud = re.sub(r"\s+", " ", m[1]) if m else ""
            if not aud:
                flags.append("аудитора не знайдено автоматично")
            elif g("Auditor") and aud.split()[0].lower() not in g("Auditor").lower():
                flags.append(f"аудитор у тексті: {aud}")
            if body:
                (d / fname).write_text(body, encoding="utf-8")
            if body and n < 2000:
                flags.append(f"короткий текст ({n} слів)")
            if tk in prev and prev[tk] and n:
                ch = (n - prev[tk]) / prev[tk]
                if abs(ch) > 0.4:
                    flags.append(f"зміна довжини {ch:+.0%} до FY{fy - 1}")
        prev[tk] = n
        r[ix["Words"]].value = n
        r[ix["Flags"]].value = "; ".join(flags)
        r[ix["API Auditor"]].value = aud
        r[ix["File"]].value = fname if body else ""
        if body and g("Item 1A Status") != "Reviewed":
            r[ix["Item 1A Status"]].value = "Extracted"
        log.append([tk, fy, n, "; ".join(flags) or "OK", fname if body else "—"])
        print(f"{tk} FY{fy}: {n:>6} слів  {'; '.join(flags) or 'OK'}")
    if "Item1A_log" in wb.sheetnames:
        del wb["Item1A_log"]
    lg = wb.create_sheet("Item1A_log")
    lg.append(["Ticker", "FY", "Words", "Flags", "File"])
    for row in log:
        lg.append(row)
    wb.save(xl)
    print(f"\nФайли: {d}/  •  Реєстр оновлено: {xl}")
    print("Підозрілі (перевірити вручну):", sum(1 for l in log if l[3] != "OK"))


# ---------------------------------------------------------------- xlsx
def write_xlsx(rows, disc, special):
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Register"
    cols = COLS + ["API status", "API Fiscal Year End", "API Filing Date", "API Accession No.", "API Link"]
    ws.append(cols)
    yellow = PatternFill("solid", fgColor="FFF2CC")
    for r in rows:
        ws.append([r.get(c, "") for c in cols])
        if r.get("API status", "OK") != "OK":
            for c in ws[ws.max_row]:
                c.fill = yellow
    for name, hdr, data in (("Discrepancies", ["Ticker", "FY", "Поле", "Вручну (EPE)", "API", "Тип"], disc),
                            ("Special cases", ["CIK", "Ticker", "Тип", "Деталі"], special)):
        s = wb.create_sheet(name); s.append(hdr)
        for x in data:
            s.append(x)
    for s in wb.worksheets:
        for c in s[1]:
            c.font = Font(bold=True)
        s.freeze_panes = "A2"
        for col in s.columns:
            s.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col) + 2))
    wb.save(OUT / "Table1_reconciled.xlsx")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("register"); s.add_argument("--inputs", nargs="+", required=True)
    for c in ("reconcile", "extract"):
        s = sp.add_parser(c); s.add_argument("--email", required=True)
    a = p.parse_args()
    {"register": cmd_register, "reconcile": cmd_reconcile, "extract": cmd_extract}[a.cmd](a)
