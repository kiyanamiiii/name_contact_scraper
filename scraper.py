import os, sys, time, shutil, subprocess, csv, re, random, logging, urllib.parse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
INPUT_CSV = 'nomes.csv'
OUTPUT_CSV = 'resultados.csv'
MAX_RESULTS = 8
LOTE = 30
TIMEOUT = 8
SRC_USER_DATA = r"C:\Users\kiyoshi\AppData\Local\Google\Chrome\User Data"
PROFILE_NAME = "Profile 1"
COPY_BASE = r"C:\Users\kiyoshi\selenium_profile_test"
VERBOSE = True
DDD_SC = {"47", "48", "49"}

# controla se o scraper deve abrir sites no navegador quando requests falham
RENDER_FALLBACK = False

# salva snippets / debug em arquivos textuais
SAVE_SNIPPETS = True
SNIPPET_DIR = "snippets_debug"
os.makedirs(SNIPPET_DIR, exist_ok=True)

# regexs
PHONE_REGEX = re.compile(r'(\+?55[\s\-\.\u00A0]?)?(\(?\d{2}\)?)[\s\-\.\u00A0]?(9?\d{4})[\s\-\.\u00A0]?(\d{4})')
PHONE_GENERIC = re.compile(r'(\+?\d{1,3}[\s\-\.\u00A0]?)?(\(?\d{2,3}\)?)[\s\-\.\u00A0]?\d{4,5}[\s\-\.\u00A0]?\d{4}')
PHONE_SIMPLE = re.compile(r'\(?\d{2}\)?\s?\d{4,5}[-\s]\d{4}')

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG if VERBOSE else logging.ERROR)
h = logging.StreamHandler(); h.setLevel(logging.DEBUG if VERBOSE else logging.ERROR)
h.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
root_logger.handlers = []; root_logger.addHandler(h)
logging.getLogger('WDM').setLevel(logging.ERROR); logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('selenium').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

def kill_processes():
    if os.name == 'nt':
        subprocess.call('taskkill /F /IM chrome.exe /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call('taskkill /F /IM chromedriver.exe /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.call('pkill -f chrome', shell=True); subprocess.call('pkill -f chromedriver', shell=True)
    time.sleep(1)

def ensure_profile_copy():
    src_profile = os.path.join(SRC_USER_DATA, PROFILE_NAME)
    src_local = os.path.join(SRC_USER_DATA, "Local State")
    dst_base = COPY_BASE
    dst_profile = os.path.join(dst_base, PROFILE_NAME)
    dst_local = os.path.join(dst_base, "Local State")
    if not os.path.exists(src_profile):
        logger.error("Perfil fonte não encontrado: %s", src_profile); sys.exit(1)
    os.makedirs(dst_base, exist_ok=True)
    if os.path.exists(dst_profile) and os.path.exists(dst_local):
        return dst_base
    if os.path.exists(dst_profile):
        shutil.rmtree(dst_profile)
    if os.path.exists(dst_local):
        try: os.remove(dst_local)
        except Exception: pass
    if os.path.exists(src_local):
        try: shutil.copy2(src_local, dst_local)
        except Exception: logger.debug("Não foi possível copiar Local State")
    shutil.copytree(src_profile, dst_profile, dirs_exist_ok=True)
    return dst_base

def init_driver(user_data_dir, profile_name):
    opts = Options()
    opts.headless = False
    opts.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_name:
        opts.add_argument(f"--profile-directory={profile_name}")
    opts.add_argument("--remote-debugging-port=9222")
    opts.add_argument("--no-first-run"); opts.add_argument("--no-default-browser-check")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    try:
        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        try: drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source":"Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
        except Exception: pass
        return drv
    except SessionNotCreatedException as e:
        logger.error("SessionNotCreatedException: %s", e); raise
    except WebDriverException as e:
        logger.error("WebDriverException: %s", e); raise

def human_delay(a=0.8, b=2.0): time.sleep(random.uniform(a, b))
def only_digits(s): return re.sub(r'\D', '', (s or ''))

def check_google_logged_in(drv):
    try:
        drv.get("https://myaccount.google.com/")
        time.sleep(2)
        url = drv.current_url.lower()
        if "myaccount.google.com" in url and "signin" not in url: return True
        cookies = {c["name"].upper() for c in drv.get_cookies()}
        return any(t in cookies for t in ("SID","HSID","SSID","SAPISID"))
    except Exception:
        return False

def digitar_como_humano(el, texto):
    for ch in texto:
        el.send_keys(ch); time.sleep(random.uniform(0.04, 0.12))
    el.send_keys(Keys.RETURN)

def clean_google_url(href):
    if not href: return None
    parsed = urllib.parse.urlparse(href)
    if parsed.path == '/url':
        q = urllib.parse.parse_qs(parsed.query).get('q')
        if q: return q[0]
    return href

def extract_phones_from_text(text):
    if not text: return []
    found = []
    for m in PHONE_REGEX.finditer(text): found.append(m.group(0).strip())
    for m in PHONE_GENERIC.finditer(text): found.append(m.group(0).strip())
    for m in PHONE_SIMPLE.finditer(text): found.append(m.group(0).strip())
    seen = set(); out = []
    for v in found:
        n = only_digits(v)
        if not n: continue
        if n not in seen: seen.add(n); out.append(v)
    return out

def _try_accept_consent(drv):
    candidates = [
        "//button[contains(., 'Aceitar')]", "//button[contains(., 'ACEITAR')]",
        "//button[contains(., 'Concordo')]", "//button[contains(., 'I agree')]",
        "//button[contains(., 'Accept')]", "//button[contains(., 'Aceitar tudo')]",
        "//button[contains(., 'OK') and contains(., 'cookies')]"
    ]
    for xp in candidates:
        try:
            el = drv.find_element(By.XPATH, xp)
            if el and el.is_displayed():
                try:
                    el.click()
                    time.sleep(1.0)
                    return True
                except Exception:
                    pass
        except Exception:
            pass
    return False

def _is_captcha_like(page_text):
    if not page_text: return False
    txt = page_text.lower()
    checks = [
        "unusual traffic", "detected unusual traffic",
        "por favor", "confirme que você não é um robô", "verificação", "captcha",
        "confirme que não é um robô", "are you a robot", "please verify"
    ]
    for c in checks:
        if c in txt:
            return True
    if "g-recaptcha" in txt or "recaptcha" in txt or "h-captcha" in txt:
        return True
    return False

def detect_knowledge_panel_phones(page_src):
    if not page_src: return []
    phones = []
    for m in PHONE_REGEX.finditer(page_src):
        phones.append((m.group(0), m.start()))
    for m in PHONE_SIMPLE.finditer(page_src):
        phones.append((m.group(0), m.start()))
    keywords = ['telefone', 'ligar', 'contato', 'localiza', 'endereço', 'site', 'horário']
    prioritized = []
    for ph, idx in phones:
        window = page_src[max(0, idx-200): idx+200].lower()
        if any(k in window for k in keywords):
            prioritized.append(ph)
    if prioritized:
        return list(dict.fromkeys(prioritized))
    uniq = []
    seen = set()
    for ph, _ in phones:
        nd = only_digits(ph)
        if nd and nd not in seen:
            seen.add(nd); uniq.append(ph)
    return uniq

def save_snippet_file(prefix, snippet_text):
    if not SAVE_SNIPPETS or not snippet_text: return
    safe = re.sub(r'[^0-9A-Za-z_\-\.]', '_', prefix)[:80]
    path = os.path.join(SNIPPET_DIR, f"{safe}.txt")
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(snippet_text)
    except Exception:
        pass

def buscar_links_google(q, drv, wait):
    try:
        drv.get("https://www.google.com")
        human_delay(1.0, 2.0)
        _try_accept_consent(drv)
        try: ActionChains(drv).move_by_offset(random.randint(50,400), random.randint(50,400)).perform()
        except Exception: pass
        human_delay(0.3, 0.8)
        caixa = wait.until(EC.presence_of_element_located((By.NAME, "q")))
        caixa.clear(); digitar_como_humano(caixa, q)
        try:
            WebDriverWait(drv, max(12, TIMEOUT)).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "search")),
                    EC.presence_of_element_located((By.ID, "rso")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div#search")),
                )
            )
        except Exception:
            try:
                with open("debug_google_no_results.html", "w", encoding="utf-8") as fh:
                    fh.write(drv.page_source or "")
            except Exception:
                pass
        time.sleep(0.8)
        page_src = drv.page_source or ""
        knowledge_phones = detect_knowledge_panel_phones(page_src)
        out = []
        try:
            anchors = drv.find_elements(By.CSS_SELECTOR, "#search .g a, #search a[href^='http']")
        except Exception:
            try:
                anchors = drv.find_elements(By.CSS_SELECTOR, "a")
            except Exception:
                anchors = []
        seen_urls = set()
        for a in anchors:
            try:
                href = a.get_attribute('href') or ""
                href = href.strip()
                if not href: continue
                if href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("file:"):
                    continue
                parsed = urllib.parse.urlparse(href)
                if parsed.path == '/url':
                    qv = urllib.parse.parse_qs(parsed.query).get('q')
                    if qv: href = qv[0]
                if not href.startswith("http"): continue
                if href in seen_urls: continue
                seen_urls.add(href)
                snippet = ""
                try:
                    parent = a.find_element(By.XPATH, "./ancestor::div[contains(@class,'g')][1]")
                    snippet = parent.text
                except Exception:
                    try:
                        el_snip = a.find_element(By.XPATH, "./following::div[contains(@class,'VwiC3b') or contains(@class,'IsZvec') or contains(@class,'aCOp')][1]")
                        snippet = el_snip.text
                    except Exception:
                        try:
                            search_block = drv.find_element(By.CSS_SELECTOR, "#search")
                            snippet = search_block.text[:800]
                        except Exception:
                            snippet = ""
                phones_in_snippet = extract_phones_from_text(snippet)
                title = ""
                try:
                    title_el = a.find_element(By.XPATH, ".//h3")
                    title = title_el.text
                except Exception:
                    pass
                out.append({
                    'url': href,
                    'snippet': snippet,
                    'title': title,
                    'phones_snippet': phones_in_snippet,
                    'knowledge_phones': knowledge_phones
                })
                if SAVE_SNIPPETS:
                    save_snippet_file(f"snippet_{len(out)}_{only_digits(href)[:10]}", snippet or title or href)
                if len(out) >= MAX_RESULTS: break
            except Exception:
                continue
        if not out:
            try:
                with open("debug_google_no_results.html", "w", encoding="utf-8") as fh:
                    fh.write(page_src)
            except Exception:
                pass
        return out
    except Exception as e:
        logger.error("Erro ao buscar no Google: %s", e)
        try:
            with open("debug_google_error.html", "w", encoding="utf-8") as fh:
                fh.write(drv.page_source or "")
        except Exception:
            pass
        return []

def extrair_telefones_com_html(html):
    encontrados = []
    try: soup = BeautifulSoup(html, 'html.parser')
    except Exception: soup = None
    if soup:
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.lower().startswith('tel:'):
                num = href.split(':',1)[1].strip()
                if num: encontrados.append(num)
        text = soup.get_text(separator=' ')
    else:
        text = html or ""
    for m in PHONE_REGEX.finditer(text): encontrados.append(m.group(0).strip())
    for m in PHONE_GENERIC.finditer(text): encontrados.append(m.group(0).strip())
    for m in PHONE_SIMPLE.finditer(text): encontrados.append(m.group(0).strip())
    seen = set(); unique = []
    for item in encontrados:
        norm = only_digits(item)
        if not norm: continue
        if norm not in seen: seen.add(norm); unique.append(item)
    return unique

def extrair_telefones_renderizados(url, drv, wait, timeout=12, poll_interval=0.8):
    url = clean_google_url(url)
    if not url: return []
    original = drv.current_window_handle
    drv.execute_script("window.open('');")
    handles = drv.window_handles; drv.switch_to.window(handles[-1])
    try:
        try:
            drv.get(url)
        except Exception:
            try:
                drv.get("http://" + url.split("://")[-1])
            except Exception:
                pass
        WebDriverWait(drv, 10).until(lambda d: d.execute_script("return document.readyState") in ("interactive","complete"))
        end = time.time() + timeout
        found = []
        while time.time() < end:
            page = drv.page_source or ""
            soup = BeautifulSoup(page, 'html.parser')
            for a in soup.find_all('a', href=True):
                if a['href'].lower().startswith('tel:'):
                    found.append(a['href'].split(':',1)[1].strip())
            for tag in soup.find_all(True):
                for attr in ('data-phone','data-telefone','data-telef','aria-label','title'):
                    val = tag.get(attr)
                    if val:
                        found += extract_phones_from_text(val)
            text = soup.get_text(separator=' ')
            found += extract_phones_from_text(text)
            seen = set(); uniq = []
            for p in found:
                n = only_digits(p)
                if not n: continue
                if n not in seen: seen.add(n); uniq.append(p)
            if uniq:
                return uniq
            time.sleep(poll_interval)
    finally:
        try:
            if not found:
                safe_name = re.sub(r'[^0-9A-Za-z_-]', '_', url)[:120]
                with open(f"debug_{safe_name}.html", "w", encoding="utf-8") as fh:
                    fh.write(drv.page_source or "")
        except Exception:
            pass
        try:
            drv.close(); drv.switch_to.window(original)
        except Exception:
            pass
    return []

def extrair_telefones(url, drv=None, wait=None, render_fallback=RENDER_FALLBACK):
    url = clean_google_url(url)
    if not url: return []
    headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 100:
            telefones = extrair_telefones_com_html(resp.text)
            if telefones:
                return telefones
    except Exception:
        pass
    if drv and wait and render_fallback:
        return extrair_telefones_renderizados(url, drv, wait, timeout=max(12, TIMEOUT))
    return []

def debug_print_result_list(resultados, limit=5):
    print("\n--- LINKS CAPTURADOS ---")
    for i,res in enumerate(resultados[:limit],1):
        print(f"{i}. URL: {res.get('url')}")
        s = res.get('snippet','').replace('\n',' ')[:300]
        print(f"   Snippet: {s}")
        phones = res.get('phones_snippet', [])
        if phones: print(f"   PhonesSnippet: {phones}")
        kp = res.get('knowledge_phones', [])
        if kp: print(f"   KnowledgePhones: {kp}")
        title = res.get('title','')
        if title: print(f"   Title: {title}")
    print("--- FIM ---\n")

def prioritize_sc_numbers(numbers):
    sc = DDD_SC
    sc_list = []; other = []
    for n in numbers:
        d = only_digits(n)
        if not d: continue
        if d.startswith('55') and len(d) >= 4:
            ddd = d[2:4]
        elif len(d) >= 2:
            ddd = d[0:2]
        else:
            ddd = ''
        if ddd in sc:
            sc_list.append(n)
        else:
            other.append(n)
    return sc_list + other

def format_phone_standard(original_phone):
    """
    Tentativa de padronizar para +55DDDN... quando possível.
    Retorna formatted (string) e norm_digits.
    """
    norm = only_digits(original_phone)
    if not norm:
        return original_phone, ''
    # se já tem country code 55 no começo
    if norm.startswith('55'):
        # aceitável se length 12 (55+10) ou 13 (55+11)
        if len(norm) in (12,13):
            return '+' + norm, norm
        # se maior, ainda retorna +norm
        if len(norm) > 11:
            return '+' + norm, norm
    # sem 55: se tem 10 ou 11 dígitos -> assume DDD presente
    if len(norm) in (10,11):
        return '+55' + norm, norm
    # se tem 8 ou 9 (sem DDD) não tenta adicionar +55 (ambíguo)
    if len(norm) in (8,9):
        return norm, norm
    # fallback: retorna com + se plausível
    if len(norm) > 11:
        return '+' + norm, norm
    return original_phone, norm

def choose_most_common_phone(phone_sources):
    """
    phone_sources: list of tuples (phone_str, source)
    Retorna: (chosen_phone_formatted, source, chosen_norm_digits) ou (None, None, None)
    """
    if not phone_sources:
        return None, None, None
    counts = {}
    for ph, src in phone_sources:
        norm = only_digits(ph)
        if not norm: continue
        entry = counts.setdefault(norm, {"count":0, "originals":[], "sources":[]})
        entry["count"] += 1
        if ph not in entry["originals"]:
            entry["originals"].append(ph)
        if src not in entry["sources"]:
            entry["sources"].append(src)
    if not counts:
        return None, None, None
    max_count = max(v["count"] for v in counts.values())
    candidates = [norm for norm,v in counts.items() if v["count"] == max_count]
    # tie-breaker 1: favor SC DDDs
    def is_sc(norm):
        if norm.startswith("55") and len(norm) >= 4:
            ddd = norm[2:4]
        elif len(norm) >= 2:
            ddd = norm[0:2]
        else:
            ddd = ""
        return ddd in DDD_SC
    sc_candidates = [c for c in candidates if is_sc(c)]
    if sc_candidates:
        candidates = sc_candidates
    # tie-breaker 2: maior número de dígitos
    candidates.sort(key=lambda n: len(n), reverse=True)
    chosen_norm = candidates[0]
    chosen_entry = counts[chosen_norm]
    # pick original formatting with country code if present
    preferred = None
    for o in chosen_entry["originals"]:
        if only_digits(o).startswith('55') or o.startswith('+'):
            preferred = o; break
    if not preferred:
        preferred = chosen_entry["originals"][0]
    chosen_source = chosen_entry["sources"][0]
    formatted, norm_digits = format_phone_standard(preferred)
    return formatted, chosen_source, norm_digits

def processar_linha(nome, cidade, drv, wait):
    q = f"{nome} {cidade} contato"
    resultados = buscar_links_google(q, drv, wait)
    debug_print_result_list(resultados, limit=5)
    if not resultados:
        return {"nome": nome, "cidade": cidade, "telefone": "Verificar", "url_origem": ""}
    phone_sources = []
    for res in resultados:
        kp = res.get('knowledge_phones') or []
        for ph in kp:
            phone_sources.append((ph, "google_panel"))
        snip = res.get('phones_snippet') or []
        for ph in snip:
            phone_sources.append((ph, res.get('url') or "snippet"))
    for res in resultados:
        url = res.get('url') or ""
        if not url: continue
        if "instagram.com" in url.lower():
            continue
        try:
            telefones_site = extrair_telefones(url, drv, wait, render_fallback=RENDER_FALLBACK)
            for ph in telefones_site:
                phone_sources.append((ph, url))
        except Exception:
            continue
    chosen_phone, chosen_source, norm_digits = choose_most_common_phone(phone_sources)
    if chosen_phone:
        return {"nome": nome, "cidade": cidade, "telefone": chosen_phone, "url_origem": chosen_source}
    # fallbacks
    for res in resultados:
        kp = res.get('knowledge_phones') or []
        if kp:
            ordered = prioritize_sc_numbers(kp)
            return {"nome":nome,"cidade":cidade,"telefone":"; ".join(ordered),"url_origem":"google_panel"}
    for res in resultados:
        phones = res.get('phones_snippet', []) or []
        if phones:
            ordered = prioritize_sc_numbers(phones)
            return {"nome":nome,"cidade":cidade,"telefone":"; ".join(ordered),"url_origem":res.get('url','')}
    for res in resultados:
        url = res.get('url','')
        try: host = urlparse(url).hostname or ""
        except Exception: host = ""
        if (host and host.endswith('.tel')) or (url or "").lower().find('.tel/') != -1:
            telefones = extrair_telefones(url, drv, wait, render_fallback=RENDER_FALLBACK)
            if telefones:
                ordered = prioritize_sc_numbers(telefones)
                return {"nome":nome,"cidade":cidade,"telefone":"; ".join(ordered),"url_origem":url}
    for res in resultados:
        url = res.get('url','')
        if not url: continue
        telefones = extrair_telefones(url, drv, wait, render_fallback=RENDER_FALLBACK)
        if telefones:
            ordered = prioritize_sc_numbers(telefones)
            return {"nome":nome,"cidade":cidade,"telefone":"; ".join(ordered),"url_origem":url}
    return {"nome":nome,"cidade":cidade,"telefone":"Verificar","url_origem":""}

def main():
    kill_processes()
    user_data_dir = COPY_BASE if os.path.exists(COPY_BASE) and os.path.exists(os.path.join(COPY_BASE, PROFILE_NAME)) else ensure_profile_copy()
    try:
        drv = init_driver(user_data_dir, PROFILE_NAME)
    except Exception:
        sys.exit(1)
    wait = WebDriverWait(drv, TIMEOUT)
    try:
        if not check_google_logged_in(drv):
            print("Sessão Google não detectada. Faça login manualmente na janela aberta e pressione Enter para continuar.")
            input()
            if not check_google_logged_in(drv):
                print("Login ainda não detectado. Encerrando."); return
        try:
            with open(INPUT_CSV, newline='', encoding='utf-8') as f: reader = list(csv.DictReader(f))
        except Exception as e:
            logger.error("Erro ao abrir input CSV: %s", e); return
        resultados = []
        for idx, row in enumerate(reader[:LOTE]):
            nome = row.get('name','').strip(); cidade = row.get('city','').strip()
            if not nome: continue
            try:
                resultados.append(processar_linha(nome, cidade, drv, wait))
                human_delay(3.5, 7.0)
            except Exception as e:
                logger.error("Erro processando %s - %s: %s", nome, cidade, e)
                resultados.append({"nome":nome,"cidade":cidade,"telefone":"Verificar","url_origem":""})
        try:
            with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['nome','cidade','telefone','url_origem']); w.writeheader(); w.writerows(resultados)
        except Exception as e:
            logger.error("Erro ao salvar output CSV: %s", e)
    finally:
        try: drv.quit()
        except Exception: pass

if __name__ == "__main__":
    main()
