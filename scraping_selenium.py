import os
import re
import json
import time
from groq import Groq
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Import API key from environment
os.environ["GROQ_API_KEY"] = "" # Write here your GROQ API key

def extract_event_details(driver):
    wait = WebDriverWait(driver, 10)

    def get_text_by_selector(selector):
        try:
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return element.text
        except:
            return "N/A"

    # Estrai e normalizza la data
    data = driver.find_elements(by='xpath', value='/html/body/div/section/section/article/article/div/div[@class="eventTime"]')
    normalized_dates = [reformat_date(date.text) for date in data]  # Normalizza le date qui

    return {
        'Evento': driver.find_elements(by='xpath', value='//article[@class="ev_grid"]'),
        'Titolo evento': driver.find_elements(by='xpath', value='//article/div/h2[@itemprop="name"]'),
        'Descrizione di Virgilio.it': driver.find_elements(by='xpath', value='//article/div/p[@itemprop="description"]'),
        'Data': normalized_dates,  # Usa le date normalizzate qui
        'Prezzo': driver.find_element(By.CLASS_NAME, '#prztime_1732230000_div > div > ul.evt_ticket > li:nth-child(3) > strong'),
        'Orario': driver.find_element(By.CLASS_NAME, '#prztime_1732230000_div > div > ul.evt_time > li > strong'),
        'Luogo': driver.find_elements(by='xpath', value='//article/a[@itemprop="location"]')
    }

# Function to generate event description using Groq
def generate_event_description(event):
    client = Groq()
    messages = [
        {
            "role": "user",
            "content": (f"Act like an expert copywriter who creates precise and non-rhetorical descriptions, "
                        f"using natural language. Do not add any information that is not already present. "
                        f"Take inspiration from the description of Virgilio.it to write a short description of the event:\n\n"
                        f"Titolo: {event['Titolo evento']}\n"
                        f"Data: {event['Data']}\n"
                        f"Luogo: {event['Luogo']}\n"
                        f"Prezzo: {event['Prezzo']}\n\n"
                        f"Crea una descrizione che catturi l'atmosfera dell'evento, ma senza essere retorica.")
        }
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.2-11b-vision-preview",
        max_tokens=150
    )

    return chat_completion.choices[0].message.content

# Function to reformat the date
def reformat_date(date_str):
    months = {'Gen': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'Mag': '05',
              'Giu': '06', 'Lug': '07', 'Ago': '08', 'Set': '09', 'Ott': '10',
              'Nov': '11', 'Dic': '12'}
    date_str = re.sub(r'\s+', ' ', date_str.strip())
    
    if re.match(r'\d{1,2} \w{3}', date_str):
        day, month = date_str.split()
        return f"{int(day)}/{months[month]}"
    elif re.match(r'Dal \d{1,2} \w{3} Al \d{1,2} \w{3}', date_str):
        date_parts = re.findall(r'\d{1,2} \w{3}', date_str)
        start_day, start_month = date_parts[0].split()
        end_day, end_month = date_parts[1].split()
        return f"Dal {int(start_day)}/{months[start_month]} al {int(end_day)}/{months[end_month]}"
    
    return date_str

def save_to_json(new_data):
    existing_data = []
    file_path = 'Eventi_Virgilio.it_selenium.json'
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as json_file:
            existing_data = json.load(json_file)
    
    existing_event_ids = {(event['Titolo evento'], event['Data'], event['Luogo']) for event in existing_data}
    unique_new_data = [event for event in new_data if (event['Titolo evento'], event['Data'], event['Luogo']) not in existing_event_ids]

    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(existing_data + unique_new_data, json_file, ensure_ascii=False, indent=4)

    return len(unique_new_data), len(existing_data), unique_new_data

def scrape_events():
    start_time = time.time()
    print("Web Scraping in esecuzione.")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3") #meno log per maggior readability

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.get('https://www.virgilio.it/italia/siena/eventi/concerti')

        wait = WebDriverWait(driver, 10)
        # Step 2: Accetta i cookie
        try:
            # Trova e clicca su "accetta e chiudi"
            cookie_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/div/div/div/button[@id="iol_cmp_cont_senz_acce"]'))
            )
            cookie_button.click()
            
            # Trova e clicca su "accetta strettamente necessari"
            accept_necessary_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/div/div/div/button[@class="ubl__cnt__btn ubl-ncs__btn ubl-cst__btn ubl-ncs__btn--reject iubenda-cs-reject-btn"]'))
            )
            accept_necessary_button.click()
            print("Cookie consent accepted.")
        except Exception as e:
            print("Nessun banner dei cookie trovato o già accettato:", e)

        # Step 3: Trova tutti i link degli eventi
        wait.until(EC.presence_of_all_elements_located((By.XPATH, '//h2/a[@itemprop="url"]')))
        event_links = []
        event_elements = driver.find_elements(By.XPATH, '//h2/a[@itemprop="url"]')

        for event in event_elements:
            event_links.append(event.get_attribute("href"))  # Prendi l'attributo href per ogni link

        # Step 4: Cicla su ogni link e fai lo scraping
        events_data = []
        for link in event_links:
            driver.get(link)
            
            # Estrai i dettagli dell'evento
            try:
                # Trova gli elementi e preleva i dati
                titolo_evento = wait.until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/div/section/section/section/article/div/div/h2[@itemprop="name"]'))
                ).text
                
                descrizione = driver.find_element(By.XPATH, '/html/body/div/section/section/section/article/div/div/div[@itemprop="description"]').text
                data = driver.find_element(By.XPATH, '/html/body/div/section/section/section/article/div/div/div[@class="eventTime"]').text
                normalized_data = reformat_date(data)  # Normalizza qui
                
                orario_elements = driver.find_elements(By.XPATH, '//ul[@class="evt_time"]/li[@class="osl16 c1"]/strong')
                
                # Estrai i prezzi in modo flessibile
                prezzo_elements = driver.find_elements(By.XPATH, '//ul[@class="evt_ticket"]/li')
                prezzi = [elem.get_attribute("innerText").strip() for elem in prezzo_elements]

                # Estrai il nome del luogo e l'indirizzo
                luogo = driver.find_element(By.XPATH, '//article/div/div/div[@class="luogo_eventi bgc1 c2"]/a/h5').text
                indirizzo = driver.find_element(By.XPATH, '//article/div/div/div[@class="luogo_eventi bgc1 c2"]/address').text
                
                # Crea un dizionario con i dettagli dell'evento
                event = {
                    "Titolo evento": titolo_evento,
                    "Descrizione di Virgilio.it": descrizione,
                    "Descrizione Groq": None,  # Imposta inizialmente a None
                    "Data": normalized_data,
                    "Orario": orario_elements[0].text if orario_elements else None,
                    "Luogo": luogo,
                    "Indirizzo": indirizzo,
                    "Prezzo": prezzi
                }

                # Genera la descrizione di Groq e aggiungila al dizionario
                event["Descrizione Groq"] = generate_event_description(event)

                # Aggiungi l'evento a `events_data`
                events_data.append(event)
                print(f"Scraping eseguito con successo di: {titolo_evento}")

            except Exception as e:
                print(f"Errore nello scraping su {link} di: {e}")

        # Step 5: Salva i dati in JSON
        new_entries, existing_entries, unique_data = save_to_json(events_data)
        print(f"{new_entries} nuove voci aggiunte al JSON. Voci totali nel file: {existing_entries + new_entries}.")
    
    except Exception as e:
        print("Errore nello scraping:", e)
    finally:
        if driver:
            driver.quit()

    print(f"Tempo totale di esecuzione: {time.time() - start_time:.2f} secondi.")

# Execute scraping
scrape_events()
