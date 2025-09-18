# optimized_whatsapp_scraper.py
# Uso: ajustar CONFIG abaixo e rodar: python optimized_whatsapp_scraper.py
# Requisitos: requests, beautifulsoup4, phonenumbers, webdriver-manager, selenium, pillow, pytesseract (opcional)
# Instale: pip install requests beautifulsoup4 phonenumbers webdriver-manager selenium pillow pytesseract

import csv, time, re, random, json, logging, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import phonenumbers
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Optional OCR
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# ---------------- CONFIG ----------------
INPUT_NAMES = 'names.csv'   # headers: name,city
OUTPUT_CSV = 'output_clean.csv'
DEBUG_CSV  = 'debug_output.csv'
WAIT_BETWEEN_SEARCHES = (0.8, 2.0)
MAX_RESULTS_TO_VISIT = 6
MAX_WORKERS = 6                 # número de threads; ajuste conforme CPU/RAM
HEADLESS = True
ENABLE_OCR = False              # só True se tiver tesseract instalado no sistema
ENABLE_2CHAT = False            # habilite se fornecer URL/api key abaixo
TWOCHAT_API_URL = 'https://api.2chat.example/validate'  # substituir
TWOCHAT_API_KEY = 'UAK3b699790-19ba-48f6-9b94-3cbe1833be8c'    # substituir
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)"
]
SITE_PRIORITIES = [
    "doctoralia.com.br",
    "crmbr.org.br",
    "saude.gov.br",
    "google.com",
    "linkedin.com",
    "instagram.com",
    "linktr.ee",
    "bit.ly"
]
PROXIES = []  # ex: ['http://user:pass@ip:port'] ou vazio
# ----------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
WA_LINK_RE = re.compile(r'https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/|wa\.link/)(\+?55)?([0-9]{8,13})', re.I)
PHONE_RE = re.compile(r'(\+55|55)?\s*\(?\d{2}\)?\s*9?\d{4}[-.\s]?\d{4}')
TEL_LINK_RE = re.compile(r'^tel:\+?([0-9\-\.\s\(\)]+)', re.I)
SHORT_URL_DOMAINS = ('bit.ly','tinyurl.com','goo.gl','t.co','lnkd.in','rb.gy','shorturl.at','wa.me','wa.link','linktr.ee')

thread_local = threading.local()

def choose_user_agent():
    return random.choice(USER_AGENT_LIST)

def requests_session():
    sess = getattr(thread_local, 'session', None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update({'User-Agent': choose_user_agent()})
        # retries backoff
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        sess.mount('http://', adapter); sess.mount('https://', adapter)
        if PROXIES:
            sess.proxies.update({'http': random.choice(PROXIES), 'https': random.choice(PROXIES)})
        thread_local.session = sess
    return sess

def init_selenium_for_thread():
    drv = getattr(thread_local, 'driver', None)
    if drv is None:
        options = Options()
        if HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={choose_user_agent()}")
        options.add_argument("--log-level=3")
        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        thread_local.driver = drv
    return drv

def close_selenium_for_thread():
    drv = getattr(thread_local, 'driver', None)
    if drv:
        try:
            drv.quit()
        except: pass
        thread_local.driver = None

def expand_url(url, session=None, timeout=10):
    session = session or requests_session()
    try:
        r = session.head(url, allow_redirects=True, timeout=timeout)
        return r.url
    except Exception:
        try:
            r = session.get(url, allow_redirects=True, timeout=timeout)
            return r.url
        except Exception:
            return url

def normalize_number(raw):
    if not raw:
        return None
    s = re.sub(r'[^\d\+]', '', str(raw))
    # if no country code, add BR
    digits = re.sub(r'\D','', s)
    if not digits:
        return None
    if not digits.startswith('55'):
        digits = '55' + digits if len(digits) >= 10 else digits
    try:
        numobj = phonenumbers.parse('+' + digits, "BR")
        if phonenumbers.is_possible_number(numobj) and phonenumbers.is_valid_number(numobj):
            national = str(numobj.national_number)
            ddd = int(national[:2])
            if 11 <= ddd <= 99:
                return phonenumbers.format_number(numobj, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    if len(digits) >= 12:
        return '+' + digits
    return None

def format_brazilian_number(e164):
    if not e164:
        return ''
    try:
        numobj = phonenumbers.parse(e164, "BR")
        national = str(numobj.national_number)
        ddd = national[:2]; rest = national[2:]
        if len(rest) == 8:
            return f"+55 ({ddd}) {rest[:4]}-{rest[4:]}"
        else:
            return f"+55 ({ddd}) {rest[:5]}-{rest[5:]}"
    except:
        return e164

def extract_from_soup(soup, target_name_tokens=None):
    # 1) tel: links and whatsapp links
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        m = WA_LINK_RE.search(href)
        if m:
            n = normalize_number(m.group(0))
            if n: return n, href, 'wa_link'
        t = TEL_LINK_RE.search(href)
        if t:
            n = normalize_number(t.group(1))
            if n: return n, t.group(1), 'tel_link'
        # raw phone text in anchors
        m2 = PHONE_RE.search(href)
        if m2:
            n = normalize_number(m2.group(0))
            if n: return n, m2.group(0), 'anchor_text'
    # 2) JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or "{}")
            items = data if isinstance(data, list) else [data]
            for it in items:
                tel = None
                if isinstance(it, dict):
                    tel = it.get('telephone') or (it.get('contactPoint') and it.get('contactPoint').get('telephone'))
                if tel:
                    n = normalize_number(tel)
                    if n: return n, tel, 'json_ld'
        except Exception:
            continue
    # 3) visible text with proximity to name
    text = soup.get_text(" ")
    matches = list(PHONE_RE.finditer(text))
    if not matches:
        # 4) try images OCR if enabled
        if ENABLE_OCR and OCR_AVAILABLE:
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    try:
                        sess = requests_session()
                        imgurl = expand_url(urljoin('http://dummy', src), session=sess)
                        r = sess.get(imgurl, timeout=8)
                        if r.status_code == 200:
                            from io import BytesIO
                            im = Image.open(BytesIO(r.content))
                            txt = pytesseract.image_to_string(im)
                            m = PHONE_RE.search(txt)
                            if m:
                                n = normalize_number(m.group(0))
                                if n: return n, m.group(0), 'ocr'
                    except Exception:
                        continue
        return None, None, None
    lowered = text.lower()
    if target_name_tokens:
        for m in matches:
            start, end = m.start(), m.end()
            window = lowered[max(0,start-300):min(len(text),end+300)]
            if all(tok in window for tok in target_name_tokens):
                n = normalize_number(m.group(0))
                if n: return n, m.group(0), 'proximity_text'
    # fallback choose first plausible
    for m in matches:
        n = normalize_number(m.group(0))
        if n: return n, m.group(0), 'first_text'
    return None, None, None

def fetch_with_requests(url, timeout=10):
    sess = requests_session()
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and len(r.text)>100:
            return BeautifulSoup(r.text, 'html.parser'), r.url
    except Exception:
        return None, url
    return None, url

def fetch_with_selenium(url):
    try:
        drv = init_selenium_for_thread()
        drv.get(url)
        time.sleep(random.uniform(1.0,1.8))
        return BeautifulSoup(drv.page_source, 'html.parser'), url
    except Exception:
        return None, url

def bing_search_urls(query, max_results=6):
    sess = requests_session()
    try:
        r = sess.get('https://www.bing.com/search', params={'q': query}, timeout=10)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, 'html.parser')
        links = []
        for a in soup.select('li.b_algo h2 a')[:max_results]:
            href = a.get('href')
            if href: links.append(href)
        return links
    except Exception:
        return []

def try_wa_me_check(e164):
    if not e164: return None
    num = re.sub(r'\D','', e164)
    url = f'https://wa.me/{num}'
    try:
        r = requests_session().get(url, timeout=8)
        if r.status_code == 200 and 'WhatsApp' in r.text:
            return True
        if r.status_code == 404:
            return False
    except Exception:
        return None
    return None

def validate_with_2chat(e164):
    if not ENABLE_2CHAT or not TWOCHAT_API_URL or not TWOCHAT_API_KEY:
        return None
    try:
        payload = {'phone': re.sub(r'\D','', e164)}
        headers = {'Authorization': f'Bearer {TWOCHAT_API_KEY}', 'Content-Type': 'application/json'}
        r = requests_session().post(TWOCHAT_API_URL, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def build_query(name, city):
    base = f'"{name}" {city} contato telefone consultório'
    site_clause = " OR ".join("site:" + s for s in SITE_PRIORITIES)
    return f'{base} ({site_clause})'

def process_person(person):
    name = person.get('name','').strip()
    city = person.get('city','').strip()
    if not name:
        return {'name':name,'city':city,'number':''}
    tokens = [t.lower() for t in re.findall(r'\w+', name) if len(t)>2]
    query = build_query(name, city)
    logging.info(f'Query: {query}')
    urls = bing_search_urls(query, max_results=MAX_RESULTS_TO_VISIT)
    found = None; raw=''; method=''; source=''
    # try prioritized urls first
    for url in urls:
        time.sleep(random.uniform(*WAIT_BETWEEN_SEARCHES))
        # expand short urls
        if any(domain in urlparse(url).netloc for domain in SHORT_URL_DOMAINS):
            url = expand_url(url)
        soup, final = fetch_with_requests(url)
        if soup is None:
            soup, final = fetch_with_selenium(url)
        if soup is None:
            continue
        n, r, m = extract_from_soup(soup, tokens)
        if n:
            found, raw, method, source = n, r, m, final
            break
        # special handling for link collections (linktr.ee, instagram bio)
        netloc = urlparse(final).netloc.lower()
        if 'linktr.ee' in netloc or 'linktr.ee' in url:
            # get links inside and follow them
            for a in soup.find_all('a', href=True):
                l = expand_url(urljoin(final, a['href']))
                time.sleep(0.6)
                s2, f2 = fetch_with_requests(l)
                if s2 is None:
                    s2, f2 = fetch_with_selenium(l)
                if s2:
                    n2, r2, m2 = extract_from_soup(s2, tokens)
                    if n2:
                        found, raw, method, source = n2, r2, m2, f2
                        break
            if found: break
        if 'instagram.com' in netloc:
            # instagram bio often contains phone or external link
            # check meta description
            desc = ''
            meta = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attrs={'property':'og:description'})
            if meta:
                desc = meta.get('content','')
                m = PHONE_RE.search(desc)
                if m:
                    n = normalize_number(m.group(0))
                    if n:
                        found, raw, method, source = n, m.group(0), 'insta_meta', final
                        break
            # find external links in bio
            for a in soup.select('a'):
                href = a.get('href')
                if href and ('http' in href or href.startswith('/')):
                    l = expand_url(urljoin(final, href))
                    time.sleep(0.6)
                    s2, f2 = fetch_with_requests(l)
                    if s2 is None:
                        s2, f2 = fetch_with_selenium(l)
                    if s2:
                        n2, r2, m2 = extract_from_soup(s2, tokens)
                        if n2:
                            found, raw, method, source = n2, r2, m2, f2
                            break
            if found: break

    # last resort: broad search without site priority
    if not found:
        broad_q = f'"{name}" {city} telefone'
        more = bing_search_urls(broad_q, max_results=MAX_RESULTS_TO_VISIT)
        for url in more:
            time.sleep(random.uniform(*WAIT_BETWEEN_SEARCHES))
            if any(domain in urlparse(url).netloc for domain in SHORT_URL_DOMAINS):
                url = expand_url(url)
            soup, final = fetch_with_requests(url)
            if soup is None:
                soup, final = fetch_with_selenium(url)
            if soup:
                n, r, m = extract_from_soup(soup, tokens)
                if n:
                    found, raw, method, source = n, r, m, final
                    break

    wa_quick = try_wa_me_check(found) if found else None
    twochat_resp = validate_with_2chat(found) if found else None

    formatted = format_brazilian_number(found) if found else ''

    return {
        'name': name,
        'city': city,
        'number': formatted,
        'source_url': source or '',
        'raw_match': raw or '',
        'method': method or '',
        'wa_quick': wa_quick,
        'twochat': twochat_resp or ''
    }

def main():
    with open(INPUT_NAMES, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        people = list(reader)

    results = []
    debug = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_person, p): p for p in people}
        try:
            for fut in as_completed(futures):
                r = fut.result()
                results.append({'name': r['name'], 'city': r['city'], 'number': r['number']})
                debug.append(r)
        finally:
            # cleanup per-thread selenium
            close_selenium_for_thread()

    # final CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        keys = ['name','city','number']
        writer = csv.DictWriter(f, keys)
        writer.writeheader(); writer.writerows(results)

    with open(DEBUG_CSV, 'w', newline='', encoding='utf-8') as f:
        keys = ['name','city','number','source_url','raw_match','method','wa_quick','twochat']
        writer = csv.DictWriter(f, keys)
        writer.writeheader(); writer.writerows(debug)

if __name__ == '__main__':
    main()
