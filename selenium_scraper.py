import csv, re, time, random, requests
from bs4 import BeautifulSoup
import phonenumbers

# Configurações
INPUT_NAMES = 'names.csv'
OUTPUT_CSV = 'output_from_bing_http.csv'
WAIT_BETWEEN_SEARCHES = (1, 2)

# API 2Chat
API_KEY = "UAK3b699790-19ba-48f6-9b94-3cbe1833be8c"
API_URL = "https://api.2chat.com.br/v1/whatsapp/check-number"

# Regex
WA_LINK_RE = re.compile(r'https?://(?:api\.whatsapp\.com/send\?phone=|wa\.me/|wa\.link/)(\+?55)?([0-9]{8,13})', re.I)
PHONE_RE = re.compile(r'(\+55|55)?\s*\(?\d{2}\)?\s*9?\d{4}[-.\s]?\d{4}')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Normaliza números
def normalize_number(raw):
    digits = re.sub(r'\D','', raw)
    try:
        numobj = phonenumbers.parse(digits, "BR")
        if phonenumbers.is_possible_number(numobj):
            return phonenumbers.format_number(numobj, phonenumbers.PhoneNumberFormat.E164)
    except:
        pass
    if len(digits) >= 10:
        if not digits.startswith('55'):
            digits = '55' + digits
        return '+' + digits
    return None

# Extrai números de HTML
def extract_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        m = WA_LINK_RE.search(href)
        if m:
            return normalize_number(m.group(0))
    text = soup.get_text(" ")
    m = PHONE_RE.search(text)
    if m:
        return normalize_number(m.group(0))
    return None

# Checa WhatsApp via 2Chat
def check_whatsapp_number(phone_number):
    payload = {"phone": phone_number}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("exists", False)
    except Exception as e:
        print(f"Erro ao checar {phone_number}: {e}")
        return False

# Faz busca no Bing via HTTP
def search_bing(query, max_results=4):
    url = f"https://www.bing.com/search?q={query}"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = [a['href'] for a in soup.select('li.b_algo h2 a')][:max_results]
        return links
    except Exception as e:
        print(f"Erro ao buscar {query}: {e}")
        return []

# Função principal
def main():
    with open(INPUT_NAMES, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        people = list(reader)

    out = []

    for person in people:
        name = person.get('name')
        city = person.get('city', '')
        query = f'"{name}" {city} contato telefone consultório'
        print("Buscando:", query)

        results = search_bing(query)
        found_num = None
        is_whatsapp = False
        has_instagram = False

        for url in results:
            if "instagram.com" in url:
                has_instagram = True
                continue
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                num = extract_from_html(resp.text)
                if num:
                    found_num = num
                    is_whatsapp = check_whatsapp_number(found_num)
                    break
            except:
                continue

        out.append({**person, 'extracted_phone': found_num or '', 'whatsapp': is_whatsapp, 'instagram': has_instagram})
        time.sleep(random.uniform(*WAIT_BETWEEN_SEARCHES))

    keys = list(out[0].keys()) if out else []
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(out)

    print("Busca finalizada! Resultado salvo em:", OUTPUT_CSV)

if __name__ == '__main__':
    main()
