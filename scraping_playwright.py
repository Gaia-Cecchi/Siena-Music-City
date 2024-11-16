import asyncio
from playwright.async_api import async_playwright
import os
import re
import json
from groq import Groq
import time

# Import API key from environment
os.environ["GROQ_API_KEY"] = "" # Write here your GROQ API key

# Function to extract event details
async def extract_event_details(page):
    await page.wait_for_selector('h2')  # Wait for the title to be present
    
    title_selectors = [
        'h2',  # Generalized selector
    ]
    
    description_selectors = [
        '#long-desc > div', 
        '#long-desc > div > p', 
        '#long-desc'
    ]
    
    date_selectors = [
        '.eventTime',
        'body > div.container > section:nth-child(4) > section.col.col-wider.less-coll > section > article > div.colDx > div.contentEvento > div.eventTime'
    ]
    
    price_selectors = [
        'ul.evt_ticket', 
        '#prztime', 
        '#evt_ticket'
    ]
    
    time_selectors = [
        'ul.evt_time', 
        '#evt_time'
    ]
    
    location_selectors = [
        '.link_vicinanze .luogo_eventi', 
        'address'
    ]

    async def get_first_valid_selector(page, selectors):
        for selector in selectors:
            element = await page.query_selector(selector)
            if element:
                return await element.inner_text()
        return None

    title = await get_first_valid_selector(page, title_selectors)
    description = await get_first_valid_selector(page, description_selectors)
    date = await get_first_valid_selector(page, date_selectors)
    price = await get_first_valid_selector(page, price_selectors)
    time = await get_first_valid_selector(page, time_selectors)
    location = await get_first_valid_selector(page, location_selectors)

    return {
        'Titolo evento': title or 'N/A',
        'Descrizione di Virgilio.it': description or 'N/A',
        'Data': date or 'N/A',
        'Prezzo': price or 'N/A',
        'Orario': time or 'N/A',
        'Luogo': location or 'N/A'
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
    date_str = re.sub(r'\s+', ' ', date_str.strip())
    
    months = {
        'Gen': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'Mag': '05',
        'Giu': '06', 'Lug': '07', 'Ago': '08', 'Set': '09', 'Ott': '10',
        'Nov': '11', 'Dic': '12'
    }
    
    if re.match(r'\d{1,2} \w{3}', date_str):
        day, month = date_str.split(' ')
        return f"{int(day)}/{months[month]}"

    elif re.match(r'Dal \d{1,2} \w{3} Al \d{1,2} \w{3}', date_str):
        date_parts = re.findall(r'\d{1,2} \w{3}', date_str)
        start_day, start_month = date_parts[0].split(' ')
        end_day, end_month = date_parts[1].split(' ')
        return f"Dal {int(start_day)}/{months[start_month]} al {int(end_day)}/{months[end_month]}"
    
    return date_str

# Function to save data in JSON format, adding new events without duplicates
async def save_to_json(new_data):
    if os.path.exists('Eventi_Virgilio.it.json'):
        with open('Eventi_Virgilio.it.json', 'r', encoding='utf-8') as json_file:
            existing_data = json.load(json_file)
    else:
        existing_data = []

    existing_event_ids = {
        (event['Titolo evento'], event['Data'], event['Luogo']) for event in existing_data
    }

    unique_new_data = [
        event for event in new_data 
        if (event['Titolo evento'], event['Data'], event['Luogo']) not in existing_event_ids
    ]

    combined_data = existing_data + unique_new_data

    with open('Eventi_Virgilio.it.json', 'w', encoding='utf-8') as json_file:
        json.dump(combined_data, json_file, ensure_ascii=False, indent=4)

    return unique_new_data

# Main scraping function
async def scrape_events():
    start_time = time.time()
    print("Web Scraping in esecuzione.")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto('https://www.virgilio.it/italia/siena/eventi/concerti')
            await page.wait_for_load_state('networkidle', timeout=60000)

            events_data = []
            event_links = await page.query_selector_all('body > div.container > section:nth-child(6) > section > article div.eventContent > h2 > a')

            for event_link in event_links:
                event_url = await event_link.get_attribute('href')
                if not event_url.startswith('https://www.virgilio.it'):
                    event_url = f"https://www.virgilio.it{event_url}"

                new_page = await browser.new_page()
                await new_page.goto(event_url)

                event_details = await extract_event_details(new_page)

                # Reformat the date immediately after extraction
                event_details['Data'] = reformat_date(event_details['Data'])

                events_data.append(event_details)
                await new_page.close()

            # Save the events to JSON and check for new entries
            unique_new_data = await save_to_json(events_data)
            if unique_new_data:
                print("Eventi salvati nel file JSON.")
            else:
                print("Nessun nuovo evento da aggiungere.")

            await browser.close()

    except Exception as e:
        print(f"Si è verificato un errore: {e}")

    end_time = time.time()
    elapsed_time = end_time - start_time
    hours, remainder = divmod(int(elapsed_time), 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"Operazione completata in: {hours} ore, {minutes} minuti, {seconds} secondi.")

# Execute scraping
asyncio.run(scrape_events())
