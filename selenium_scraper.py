# selenium_scraper_bing_headless.py
import csv, time, re, random
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import phonenumbers

INPUT_NAMES = 'names.csv'   # headers: name,city
OUTPUT_CSV = 'output_from_bing_headless.csv'
WAIT_BETWEEN_SEARCHES = (1, 3)  # intervalo pequeno, randomizado
MAX_RESULTS_TO_VISIT = 3

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

WA_LINK_RE = re.compile(r'https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/|wa\.link/)(\+?55)?([0-9]{8,13})', re.I)
PHONE_RE = re.compile(r'(\+55|55)?\s*\(?\d{2}\)?\s*9?\d{4}[-.\s]?\d{4}')

def normalize_number(raw):
    digits = re.sub(r'\D','', raw)
    try:
        numobj = phonenumbers.parse(digits, "BR")
        if phonenumbers.is_possible_number(numobj):
            return phonenumbers.format_number(numobj, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    if len(digits) >= 10:
        if not digits.startswith('55'):
            digits = '55' + digits
        return '+' + digits
    return None

def extract_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        m = WA_LINK_RE.search(href)
        if m:
            return normalize_number(m.group(0)), href
    text = soup.get_text(" ")
    m = PHONE_RE.search(text)
    if m:
        return normalize_number(m.group(0)), None
    return None, None

def main():
    options = Options()
    options.add_argument("--headless")  # roda em background
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    with open(INPUT_NAMES, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        people = list(reader)

    out = []
    for person in people:
        name = person.get('name')
        city = person.get('city', '')
        query = f'"{name}" {city} contato telefone consultório'
        print("Buscando:", query)

        driver.get("https://www.bing.com")
        time.sleep(random.uniform(1,2))
        box = driver.find_element(By.NAME, "q")
        box.clear()
        box.send_keys(query)
        box.send_keys(Keys.RETURN)
        time.sleep(random.uniform(*WAIT_BETWEEN_SEARCHES))

        results = driver.find_elements(By.CSS_SELECTOR, 'li.b_algo h2 a')[:MAX_RESULTS_TO_VISIT]
        found_num = None
        found_href = None

        for r in results:
            href = r.get_attribute('href')
            try:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(href)
                time.sleep(random.uniform(1,3))
                html = driver.page_source
                num, link = extract_from_html(html)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                if num:
                    found_num = num
                    found_href = link or href
                    break
            except Exception:
                try:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                continue

        out.append({**person, 'extracted_phone': found_num or '', 'found_href': found_href or ''})
        time.sleep(random.uniform(*WAIT_BETWEEN_SEARCHES))

    driver.quit()

    keys = list(out[0].keys()) if out else []
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(out)

if __name__ == '__main__':
    main()
