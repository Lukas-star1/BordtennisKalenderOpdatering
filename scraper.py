from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

# Links til holdturneringerne. Indsæt det andet holds link som det andet element.
turnerings_urls = [
    'https://www.bordtennisportalen.dk/DBTU/HoldTurnering/Stilling/#4,42026,15478,4006,4000,,,,',
    'https://www.bordtennisportalen.dk/DBTU/HoldTurnering/Stilling/#4,42026,15477,4006,4000,,,,',
]


def hent_rækker(url):
    print(f"1. Henter data fra {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Giver Bordtennisportalen 3 sekunder til at trække tabellen ind via JavaScript
        page.wait_for_timeout(3000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    return soup.find_all('tr')


rækker = []
for turnerings_url in turnerings_urls:
    if turnerings_url:
        rækker.extend(hent_rækker(turnerings_url))

# --- KALENDER OPSÆTNING ---
cal = Calendar()
cal.add('prodid', '-//Sisu Kampkalender Scraper//')
cal.add('version', '2.0')

# Vi sætter tidszonen til Danmark (meget vigtigt for Apple Kalender)
cph_tz = pytz.timezone('Europe/Copenhagen')
kampe_fundet = 0
sete_kampnumre = set()

print("2. Analyserer tabellen og bygger din kalender...\n")

for række in rækker:
    # Find alle relevante celler i rækken
    dato_celle = række.find('td', class_='time')
    kamp_celle = række.find('td', class_='matchno')
    sted_celle = række.find('td', class_='venue')
    hold_celler = række.find_all('td', class_='team')
    
    # Tjek om vi er i en rigtig datarække (og ikke en overskrift)
    if dato_celle and kamp_celle and sted_celle and len(hold_celler) >= 2:
        hjemmehold = hold_celler[0].text.strip()
        udehold = hold_celler[1].text.strip()
        
        # Filtrer efter "Sisu" (uanset store/små bogstaver)
        if "sisu" in hjemmehold.lower() or "sisu" in udehold.lower():
            dato_str = dato_celle.text.strip()  # Ser f.eks. ud som: "lø 06‑09‑2025 12:00"
            kamp_nr = kamp_celle.text.strip()
            sted = sted_celle.text.strip()

            if kamp_nr in sete_kampnumre:
                continue
            
            # --- DATO & TID LOGIK ---
            # Vi splitter teksten ved mellemrum for at fjerne ugedagen (f.eks. "lø")
            dele = dato_str.split(' ')
            if len(dele) >= 3:
                # Samler dato og tid igen uden ugedagen
                ren_dato_tid = f"{dele[1]} {dele[2]}"
                
                # RETTELSEN: Vi udskifter den usynlige/falske bindestreg med en normal bindestreg!
                ren_dato_tid = ren_dato_tid.replace("‑", "-")
                
                # Konverterer teksten til et tids-objekt computeren forstår
                start_tid = datetime.strptime(ren_dato_tid, "%d-%m-%Y %H:%M")
                start_tid = cph_tz.localize(start_tid)
                
                # Vi antager, at en bordtenniskamp tager ca. 2 timer
                slut_tid = start_tid + timedelta(hours=2)
                
                # --- OPRET BEGIVENHED I KALENDEREN ---
                event = Event()
                titel = f"Bordtennis: {hjemmehold} vs {udehold}"
                event.add('summary', titel)
                event.add('dtstart', start_tid)
                event.add('dtend', slut_tid)
                event.add('location', sted)
                event.add('description', f"Kampnummer: {kamp_nr}\nAutomatisk hentet fra Bordtennisportalen.")
                event.add('uid', f"sisu-kamp-{kamp_nr}@bordtennisportalen.dk")
                
                # Læg begivenheden ind i selve kalenderen
                cal.add_component(event)
                sete_kampnumre.add(kamp_nr)
                kampe_fundet += 1
                
                print(f"Tilføjet: {titel} ({start_tid.strftime('%d/%m/%Y kl. %H:%M')})")

# --- GEM KALENDERFILEN ---
filnavn = 'calendar.ics'
with open(filnavn, 'wb') as f:
    f.write(cal.to_ical())

if kampe_fundet > 0:
    print("-" * 40)
    print(f"SUCCES! {kampe_fundet} kampe blev gemt i filen '{filnavn}'.")
    print("Klar til at blive sendt til din iPhone!")
else:
    print("\nFandt ingen Sisu kampe. En tom kalenderfil blev oprettet.")