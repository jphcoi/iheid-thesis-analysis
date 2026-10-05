#!/usr/bin/env python3
"""
Analyze named entities from thesis documents and create time series visualizations.

- Plots top entities by continent/country over time
- Extracts organizations (NGOs, IOs)
- Uses publication dates from Excel metadata

Usage:
    python analyze_entities.py entities.jsonl IHEID_LOT_1_MD_FILTRE_SUR_THESES.xlsx output/
"""

import os
import json
import re
import argparse
from collections import defaultdict, Counter
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Normalized country names (merge variants)
COUNTRY_NORMALIZE = {
    # USA variants
    'united states': 'USA', 'usa': 'USA', 'états-unis': 'USA', 'etats-unis': 'USA',
    'america': 'USA', 'américain': 'USA', 'american': 'USA', 'americans': 'USA',
    'vereinigte staaten': 'USA', 'amerikanisch': 'USA',
    # UK variants
    'united kingdom': 'UK', 'uk': 'UK', 'royaume-uni': 'UK', 'britain': 'UK',
    'great britain': 'UK', 'england': 'UK', 'angleterre': 'UK', 'british': 'UK',
    # Germany variants
    'germany': 'Germany', 'allemagne': 'Germany', 'german': 'Germany', 'allemand': 'Germany',
    'deutschland': 'Germany', 'deutsch': 'Germany', 'deutsche': 'Germany',
    # France variants
    'france': 'France', 'french': 'France', 'français': 'France', 'française': 'France',
    'frankreich': 'France', 'französisch': 'France',
    # Switzerland variants
    'switzerland': 'Switzerland', 'suisse': 'Switzerland', 'swiss': 'Switzerland',
    'schweiz': 'Switzerland', 'schweizerisch': 'Switzerland',
    # Russia variants
    'russia': 'Russia', 'russie': 'Russia', 'urss': 'Russia', 'ussr': 'Russia', 'soviet': 'Russia',
    'soviets': 'Russia', 'soviétique': 'Russia', 'sovietique': 'Russia', 'sovjet': 'Russia',
    'russland': 'Russia', 'russisch': 'Russia', 'sowjetunion': 'Russia',
    # China variants
    'china': 'China', 'chine': 'China', 'chinese': 'China', 'chinois': 'China',
    'chinesisch': 'China',
    # Japan variants
    'japan': 'Japan', 'japon': 'Japan', 'japanese': 'Japan', 'japonais': 'Japan',
    'japanisch': 'Japan',
    # Others - EN/FR/DE variants
    'italy': 'Italy', 'italie': 'Italy', 'italian': 'Italy', 'italien': 'Italy', 'italienisch': 'Italy',
    'spain': 'Spain', 'espagne': 'Spain', 'spanish': 'Spain', 'spanien': 'Spain', 'spanisch': 'Spain',
    'belgium': 'Belgium', 'belgique': 'Belgium', 'belgien': 'Belgium', 'belgisch': 'Belgium',
    'netherlands': 'Netherlands', 'pays-bas': 'Netherlands', 'holland': 'Netherlands',
    'niederlande': 'Netherlands', 'holländisch': 'Netherlands', 'niederländisch': 'Netherlands',
    'austria': 'Austria', 'autriche': 'Austria', 'österreich': 'Austria', 'österreichisch': 'Austria',
    'poland': 'Poland', 'pologne': 'Poland', 'polen': 'Poland', 'polnisch': 'Poland',
    'greece': 'Greece', 'grèce': 'Greece', 'griechenland': 'Greece', 'griechisch': 'Greece',
    'portugal': 'Portugal', 'sweden': 'Sweden', 'suède': 'Sweden', 'schweden': 'Sweden',
    'norway': 'Norway', 'norvège': 'Norway', 'norwegen': 'Norway',
    'denmark': 'Denmark', 'danemark': 'Denmark', 'dänemark': 'Denmark',
    'finland': 'Finland', 'finlande': 'Finland', 'finnland': 'Finland',
    'canada': 'Canada', 'kanada': 'Canada',
    'mexico': 'Mexico', 'mexique': 'Mexico', 'mexiko': 'Mexico',
    'brazil': 'Brazil', 'brésil': 'Brazil', 'brasilien': 'Brazil',
    'argentina': 'Argentina', 'argentine': 'Argentina', 'argentinien': 'Argentina',
    'chile': 'Chile', 'chili': 'Chile',
    'colombia': 'Colombia', 'colombie': 'Colombia', 'kolumbien': 'Colombia',
    'peru': 'Peru', 'pérou': 'Peru',
    'venezuela': 'Venezuela', 'cuba': 'Cuba', 'kuba': 'Cuba',
    'india': 'India', 'inde': 'India', 'indian': 'India', 'indien': 'India', 'indisch': 'India',
    'pakistan': 'Pakistan',
    'indonesia': 'Indonesia', 'indonésie': 'Indonesia', 'indonesien': 'Indonesia',
    'vietnam': 'Vietnam', 'viêt nam': 'Vietnam',
    'thailand': 'Thailand', 'thaïlande': 'Thailand',
    'malaysia': 'Malaysia', 'malaisie': 'Malaysia',
    'philippines': 'Philippines', 'philippinen': 'Philippines',
    'singapore': 'Singapore', 'singapour': 'Singapore', 'singapur': 'Singapore',
    'korea': 'Korea', 'corée': 'Korea', 'südkorea': 'Korea', 'nordkorea': 'Korea',
    'taiwan': 'Taiwan',
    'iran': 'Iran', 'iraq': 'Iraq', 'irak': 'Iraq',
    'syria': 'Syria', 'syrie': 'Syria', 'syrien': 'Syria',
    'israel': 'Israel', 'israël': 'Israel',
    'palestine': 'Palestine', 'palestinian': 'Palestine', 'palästina': 'Palestine',
    'lebanon': 'Lebanon', 'liban': 'Lebanon', 'libanon': 'Lebanon',
    'turkey': 'Turkey', 'turquie': 'Turkey', 'türkei': 'Turkey', 'türkisch': 'Turkey',
    'saudi arabia': 'Saudi Arabia', 'arabie saoudite': 'Saudi Arabia', 'saudi-arabien': 'Saudi Arabia',
    'afghanistan': 'Afghanistan',
    'egypt': 'Egypt', 'égypte': 'Egypt', 'ägypten': 'Egypt', 'ägyptisch': 'Egypt',
    'algeria': 'Algeria', 'algérie': 'Algeria', 'algerien': 'Algeria',
    'morocco': 'Morocco', 'maroc': 'Morocco', 'marokko': 'Morocco',
    'tunisia': 'Tunisia', 'tunisie': 'Tunisia', 'tunesien': 'Tunisia',
    'senegal': 'Senegal', 'sénégal': 'Senegal',
    'nigeria': 'Nigeria',
    'south africa': 'South Africa', 'afrique du sud': 'South Africa', 'südafrika': 'South Africa',
    'kenya': 'Kenya', 'kenia': 'Kenya', 'ghana': 'Ghana',
    'cameroon': 'Cameroon', 'cameroun': 'Cameroon', 'kamerun': 'Cameroon',
    'ethiopia': 'Ethiopia', 'éthiopie': 'Ethiopia', 'äthiopien': 'Ethiopia',
    'tanzania': 'Tanzania', 'tanzanie': 'Tanzania', 'tansania': 'Tanzania',
    'australia': 'Australia', 'australie': 'Australia', 'australien': 'Australia',
    'new zealand': 'New Zealand', 'nouvelle-zélande': 'New Zealand', 'neuseeland': 'New Zealand',
    # Additional countries
    'hungary': 'Hungary', 'hongrie': 'Hungary', 'ungarn': 'Hungary',
    'czech republic': 'Czech Republic', 'république tchèque': 'Czech Republic', 'tschechien': 'Czech Republic',
    'romania': 'Romania', 'roumanie': 'Romania', 'rumänien': 'Romania',
    'bulgaria': 'Bulgaria', 'bulgarie': 'Bulgaria', 'bulgarien': 'Bulgaria',
    'ukraine': 'Ukraine', 'ucrania': 'Ukraine',
    'yugoslavia': 'Yugoslavia', 'yougoslavie': 'Yugoslavia', 'jugoslawien': 'Yugoslavia',
    'serbia': 'Serbia', 'serbie': 'Serbia', 'serbien': 'Serbia',
    'croatia': 'Croatia', 'croatie': 'Croatia', 'kroatien': 'Croatia',
    'bosnia': 'Bosnia', 'bosnie': 'Bosnia', 'bosnien': 'Bosnia',
    'albania': 'Albania', 'albanie': 'Albania', 'albanien': 'Albania',
    'iraq': 'Iraq', 'irak': 'Iraq',
    'jordan': 'Jordan', 'jordanie': 'Jordan', 'jordanien': 'Jordan',
    'kuwait': 'Kuwait', 'koweït': 'Kuwait',
    'uae': 'UAE', 'émirats': 'UAE', 'emirates': 'UAE',
    'qatar': 'Qatar',
    'yemen': 'Yemen', 'yémen': 'Yemen', 'jemen': 'Yemen',
    'oman': 'Oman',
    'bahrain': 'Bahrain', 'bahreïn': 'Bahrain',
    'libya': 'Libya', 'libye': 'Libya', 'libyen': 'Libya',
    'sudan': 'Sudan', 'soudan': 'Sudan',
    'congo': 'Congo', 'kongo': 'Congo',
    'ivory coast': 'Ivory Coast', "côte d'ivoire": 'Ivory Coast', 'elfenbeinküste': 'Ivory Coast',
    'mali': 'Mali', 'niger': 'Niger', 'chad': 'Chad', 'tchad': 'Chad', 'tschad': 'Chad',
    'burkina': 'Burkina Faso', 'burkina faso': 'Burkina Faso',
    'rwanda': 'Rwanda', 'ruanda': 'Rwanda',
    'burundi': 'Burundi',
    'uganda': 'Uganda', 'ouganda': 'Uganda',
    'zimbabwe': 'Zimbabwe', 'simbabwe': 'Zimbabwe',
    'zambia': 'Zambia', 'zambie': 'Zambia', 'sambia': 'Zambia',
    'mozambique': 'Mozambique', 'mosambik': 'Mozambique',
    'madagascar': 'Madagascar', 'madagaskar': 'Madagascar',
    'angola': 'Angola',
}

# Country to continent mapping
COUNTRY_TO_CONTINENT = {
    # North America
    'USA': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    # South America
    'Brazil': 'South America', 'Argentina': 'South America', 'Chile': 'South America',
    'Colombia': 'South America', 'Peru': 'South America', 'Venezuela': 'South America',
    'Bolivia': 'South America', 'Ecuador': 'South America', 'Paraguay': 'South America',
    'Uruguay': 'South America', 'Guyana': 'South America', 'Suriname': 'South America',
    # Central America / Caribbean
    'Cuba': 'Central America', 'Guatemala': 'Central America', 'Honduras': 'Central America',
    'Nicaragua': 'Central America', 'Costa Rica': 'Central America', 'Panama': 'Central America',
    'Haiti': 'Central America', 'Dominican Republic': 'Central America',
    # Europe
    'France': 'Europe', 'Germany': 'Europe', 'UK': 'Europe', 'Switzerland': 'Europe',
    'Italy': 'Europe', 'Spain': 'Europe', 'Belgium': 'Europe', 'Netherlands': 'Europe',
    'Austria': 'Europe', 'Poland': 'Europe', 'Russia': 'Europe', 'Greece': 'Europe',
    'Portugal': 'Europe', 'Sweden': 'Europe', 'Norway': 'Europe', 'Denmark': 'Europe',
    'Finland': 'Europe',
    # Asia
    'China': 'Asia', 'Japan': 'Asia', 'India': 'Asia', 'Pakistan': 'Asia',
    'Indonesia': 'Asia', 'Vietnam': 'Asia', 'Thailand': 'Asia', 'Malaysia': 'Asia',
    'Philippines': 'Asia', 'Singapore': 'Asia', 'Korea': 'Asia', 'Taiwan': 'Asia',
    'Iran': 'Asia', 'Iraq': 'Asia', 'Syria': 'Asia', 'Israel': 'Asia',
    'Palestine': 'Asia', 'Lebanon': 'Asia', 'Turkey': 'Asia', 'Saudi Arabia': 'Asia',
    'Afghanistan': 'Asia',
    # Africa
    'Egypt': 'Africa', 'Algeria': 'Africa', 'Morocco': 'Africa', 'Tunisia': 'Africa',
    'Senegal': 'Africa', 'Nigeria': 'Africa', 'South Africa': 'Africa',
    'Kenya': 'Africa', 'Ghana': 'Africa', 'Cameroon': 'Africa',
    'Ethiopia': 'Africa', 'Tanzania': 'Africa',
    # Oceania
    'Australia': 'Oceania', 'New Zealand': 'Oceania',
}

# Cities to exclude from country counts
CITIES = {'genève', 'geneva', 'paris', 'london', 'londres', 'new york', 'berlin',
          'washington', 'tokyo', 'beijing', 'pékin', 'moscow', 'moscou', 'rome',
          'brussels', 'bruxelles', 'vienna', 'vienne', 'zurich', 'zürich', 'bern', 'berne'}

# Continent keywords to exclude from country counts
CONTINENT_KEYWORDS = {'europe', 'european', 'européen', 'européenne', 'asia', 'asie',
                      'asian', 'asiatique', 'africa', 'afrique', 'african', 'africain',
                      'america', 'americas', 'amérique', 'latin america', 'amérique latine',
                      'north america', 'south america', 'amérique du nord', 'amérique du sud',
                      'central america', 'amérique centrale', 'nordamerika', 'südamerika',
                      'oceania', 'océanie'}

# IO normalization: map variants to canonical name (EN/FR/DE)
IO_NORMALIZE = {
    # United Nations
    # Note: 'un' removed - too common in French ("un/une" = a/one)
    'onu': 'United Nations', 'united nations': 'United Nations',
    'nations unies': 'United Nations', 'the united nations': 'United Nations',
    'vereinte nationen': 'United Nations',
    # World Bank
    'world bank': 'World Bank', 'banque mondiale': 'World Bank', 'the world bank': 'World Bank',
    'weltbank': 'World Bank',
    # IMF
    'imf': 'IMF', 'fmi': 'IMF', 'international monetary fund': 'IMF', 'fonds monétaire': 'IMF',
    'iwf': 'IMF', 'internationaler währungsfonds': 'IMF',
    # WTO
    'wto': 'WTO', 'omc': 'WTO', 'world trade organization': 'WTO', 'world trade': 'WTO',
    'welthandelsorganisation': 'WTO',
    # WHO
    'who': 'WHO', 'oms': 'WHO', 'world health organization': 'WHO', 'world health': 'WHO',
    'weltgesundheitsorganisation': 'WHO',
    # UNESCO/UNICEF
    'unesco': 'UNESCO', 'unicef': 'UNICEF',
    # UNHCR
    'unhcr': 'UNHCR', 'hcr': 'UNHCR', 'the unhcr': 'UNHCR', 'flüchtlingshilfswerk': 'UNHCR',
    # ILO
    'ilo': 'ILO', 'oit': 'ILO', 'international labour': 'ILO',
    'internationale arbeitsorganisation': 'ILO', 'iao': 'ILO',
    # ICRC
    'icrc': 'ICRC', 'cicr': 'ICRC', 'red cross': 'ICRC', 'croix-rouge': 'ICRC',
    'rotes kreuz': 'ICRC', 'ikrk': 'ICRC', 'internationales komitee vom roten kreuz': 'ICRC',
    # African Union
    'african union': 'African Union', 'union africaine': 'African Union',
    'oua': 'African Union', 'oau': 'African Union', 'afrikanische union': 'African Union',
    # NATO
    'nato': 'NATO', 'otan': 'NATO',
    # OECD
    'oecd': 'OECD', 'ocde': 'OECD',
    # OPEC
    'opec': 'OPEC', 'opep': 'OPEC',
    # Regional
    'asean': 'ASEAN', 'mercosur': 'Mercosur',
    # FAO
    'fao': 'FAO', 'world food': 'FAO',
    # IAEA
    'iaea': 'IAEA', 'aiea': 'IAEA', 'iaeo': 'IAEA',
    # WIPO
    'wipo': 'WIPO', 'ompi': 'WIPO',
    # Security Council
    'the security council': 'UN Security Council', 'security council': 'UN Security Council',
    'conseil de sécurité': 'UN Security Council', 'sicherheitsrat': 'UN Security Council',
    # League of Nations (historical)
    'league of nations': 'League of Nations', 'société des nations': 'League of Nations',
    'völkerbund': 'League of Nations', 'sdn': 'League of Nations',
    # Others
    'g7': 'G7', 'g8': 'G8', 'g20': 'G20',
    'arab league': 'Arab League', 'ligue arabe': 'Arab League', 'arabische liga': 'Arab League',
}

# Keywords to identify IOs
IO_KEYWORDS = list(IO_NORMALIZE.keys())

NGO_KEYWORDS = [
    'amnesty', 'greenpeace', 'oxfam', 'médecins sans frontières', 'msf',
    'human rights watch', 'hrw', 'transparency international',
    'world wildlife', 'wwf', 'save the children',
    'care international', 'world vision',
    'reporters sans frontières', 'rsf',
    'doctors without borders',
    'international crisis group',
    'freedom house',
]

# Person name normalization (merge variants)
PERSON_NORMALIZE = {
    # Political leaders
    'de gaulle': 'De Gaulle', 'charles de gaulle': 'De Gaulle', 'général de gaulle': 'De Gaulle',
    'hitler': 'Hitler', 'adolf hitler': 'Hitler',
    'staline': 'Stalin', 'stalin': 'Stalin', 'joseph stalin': 'Stalin', 'joseph staline': 'Stalin',
    'roosevelt': 'Roosevelt', 'fdr': 'Roosevelt', 'franklin roosevelt': 'Roosevelt',
    'churchill': 'Churchill', 'winston churchill': 'Churchill',
    'marx': 'Marx', 'karl marx': 'Marx',
    'lenin': 'Lenin', 'lénine': 'Lenin', 'vladimir lenin': 'Lenin',
    'mao': 'Mao', 'mao zedong': 'Mao', 'mao tse-tung': 'Mao',
    'wilson': 'Wilson', 'woodrow wilson': 'Wilson',
    'truman': 'Truman', 'harry truman': 'Truman',
    'kennedy': 'Kennedy', 'jfk': 'Kennedy', 'john kennedy': 'Kennedy',
    'nixon': 'Nixon', 'richard nixon': 'Nixon',
    'reagan': 'Reagan', 'ronald reagan': 'Reagan',
    'thatcher': 'Thatcher', 'margaret thatcher': 'Thatcher',
    'gorbachev': 'Gorbachev', 'gorbatchev': 'Gorbachev', 'mikhail gorbachev': 'Gorbachev',
    'mussolini': 'Mussolini', 'benito mussolini': 'Mussolini',
    'franco': 'Franco', 'francisco franco': 'Franco',
    'bismarck': 'Bismarck', 'otto von bismarck': 'Bismarck',
    'napoléon': 'Napoleon', 'napoleon': 'Napoleon', 'napoléon bonaparte': 'Napoleon',
    # Thinkers/Philosophers
    'weber': 'Weber', 'max weber': 'Weber',
    'keynes': 'Keynes', 'john maynard keynes': 'Keynes',
    'hayek': 'Hayek', 'friedrich hayek': 'Hayek',
    'kant': 'Kant', 'immanuel kant': 'Kant',
    'hegel': 'Hegel', 'georg hegel': 'Hegel',
    'rousseau': 'Rousseau', 'jean-jacques rousseau': 'Rousseau',
    'locke': 'Locke', 'john locke': 'Locke',
    'hobbes': 'Hobbes', 'thomas hobbes': 'Hobbes',
    'grotius': 'Grotius', 'hugo grotius': 'Grotius',
    'montesquieu': 'Montesquieu',
    'tocqueville': 'Tocqueville', 'alexis de tocqueville': 'Tocqueville',
    # International relations figures
    'kissinger': 'Kissinger', 'henry kissinger': 'Kissinger',
    'kofi annan': 'Kofi Annan', 'annan': 'Kofi Annan',
    'dag hammarskjöld': 'Hammarskjöld', 'hammarskjöld': 'Hammarskjöld',
}

# Noise patterns to filter out from PER entities
PERSON_NOISE = {
    "n'", "l'", "d'", "m.", "m'", "s'", "c'", "j'", "qu'",
    "cit.", "op.cit", "ibidem", "ibid", "cf.", "etc.",
    "they", "he", "she", "it", "we", "i", "you",
    "président", "president", "minister", "le", "la", "les",
    "l'homme", "l'etat", "l'état", "l'ue", "l'urss", "l'onu",
    "french", "english", "german", "american", "british",
    "n", "p", "pp", "no", "vol", "art",
}


def normalize_person(text):
    """Normalize person name, return canonical name or None if noise."""
    text_clean = text.strip()
    text_lower = text_clean.lower()

    # Filter out noise
    if text_lower in PERSON_NOISE:
        return None

    # Filter out short strings (likely OCR artifacts)
    if len(text_clean) < 4:
        return None

    # Filter out strings that are all punctuation/numbers
    if not any(c.isalpha() for c in text_clean):
        return None

    # Check for known person normalization
    for variant, canonical in PERSON_NORMALIZE.items():
        if variant in text_lower:
            return canonical

    # Return cleaned name (title case) if it looks like a real name
    # (contains at least one uppercase letter in original)
    if any(c.isupper() for c in text_clean):
        return text_clean

    return None


def load_entities(jsonl_path):
    """Load entities from JSONL file."""
    entities = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entities.append(json.loads(line))
    return entities


def load_metadata(excel_path):
    """Load document metadata from Excel file."""
    df = pd.read_excel(excel_path)

    # Create doc_id to date mapping
    # doc_id is based on "Nom livrable" column
    metadata = {}
    for _, row in df.iterrows():
        doc_id = str(row['Nom livrable']).replace('.txt', '')

        # Try to get year from "Date de publication"
        date_pub = row.get('Date de publication')
        year = None

        if pd.notna(date_pub):
            date_str = str(date_pub)
            # Extract 4-digit year
            match = re.search(r'(19\d{2}|20\d{2})', date_str)
            if match:
                year = int(match.group(1))

        metadata[doc_id] = {
            'year': year,
            'type': row.get('Type', ''),
            'institut': row.get('Institut', ''),
            'titre': row.get('Titre', ''),
        }

    return metadata


def classify_location(entity_text):
    """Classify a location entity to normalized country and continent."""
    text_lower = entity_text.lower().strip()

    # Skip cities
    if text_lower in CITIES:
        return None, None, None

    # Skip continent keywords (we track continents separately)
    if text_lower in CONTINENT_KEYWORDS:
        return None, None, None

    # Try to normalize to a country
    for variant, normalized in COUNTRY_NORMALIZE.items():
        if variant in text_lower:
            continent = COUNTRY_TO_CONTINENT.get(normalized)
            return normalized, continent, None

    return None, None, None


def get_continent_from_text(entity_text):
    """Extract continent mention from text."""
    text_lower = entity_text.lower().strip()

    # Order matters: check more specific terms first
    continent_patterns = [
        # North America (check before generic 'america')
        ('north america', 'North America'), ('amérique du nord', 'North America'),
        ('nordamerika', 'North America'),
        # South America / Latin America (check before generic 'america')
        ('south america', 'South America'), ('amérique du sud', 'South America'),
        ('südamerika', 'South America'),
        ('latin america', 'South America'), ('amérique latine', 'South America'),
        ('lateinamerika', 'South America'),
        # Central America
        ('central america', 'Central America'), ('amérique centrale', 'Central America'),
        ('zentralamerika', 'Central America'), ('mittelamerika', 'Central America'),
        # Generic America (fallback to South America as most common in context)
        ('america', 'South America'), ('americas', 'South America'), ('amérique', 'South America'),
        # Europe
        ('europe', 'Europe'), ('european', 'Europe'), ('européen', 'Europe'), ('européenne', 'Europe'),
        # Asia
        ('asia', 'Asia'), ('asie', 'Asia'), ('asian', 'Asia'), ('asiatique', 'Asia'),
        # Africa
        ('africa', 'Africa'), ('afrique', 'Africa'), ('african', 'Africa'), ('africain', 'Africa'),
        # Oceania
        ('oceania', 'Oceania'), ('océanie', 'Oceania'),
    ]

    for keyword, continent in continent_patterns:
        if keyword in text_lower:
            return continent

    return None


def normalize_io(entity_text):
    """Normalize IO name, return canonical name or None."""
    text_lower = entity_text.lower().strip()

    for variant, canonical in IO_NORMALIZE.items():
        if variant in text_lower:
            return canonical

    return None


def is_ngo(entity_text):
    """Check if entity is an NGO."""
    text_lower = entity_text.lower()
    return any(kw in text_lower for kw in NGO_KEYWORDS)


def analyze_entities(entities, metadata):
    """Analyze entities and aggregate by year."""

    # Time series data
    country_by_year = defaultdict(lambda: defaultdict(int))
    continent_by_year = defaultdict(lambda: defaultdict(int))
    io_by_year = defaultdict(lambda: defaultdict(int))
    ngo_by_year = defaultdict(lambda: defaultdict(int))

    # Overall counts
    all_countries = Counter()
    all_continents = Counter()
    all_ios = Counter()
    all_ngos = Counter()

    for doc in entities:
        doc_id = doc['doc_id']
        meta = metadata.get(doc_id, {})
        year = meta.get('year')

        if not year:
            continue

        # Process location entities
        loc_entities = doc.get('entities_by_type', {}).get('LOC', {})
        for entity_text, count in loc_entities.items():
            # Check for continent mention
            continent = get_continent_from_text(entity_text)
            if continent:
                continent_by_year[year][continent] += count
                all_continents[continent] += count

            # Check for country (excludes cities and continents)
            country, country_continent, _ = classify_location(entity_text)
            if country:
                country_by_year[year][country] += count
                all_countries[country] += count
                # Also count the continent for this country
                if country_continent:
                    continent_by_year[year][country_continent] += count
                    all_continents[country_continent] += count

        # Process organization entities
        org_entities = doc.get('entities_by_type', {}).get('ORG', {})
        for entity_text, count in org_entities.items():
            # Try to normalize as IO
            io_name = normalize_io(entity_text)
            if io_name:
                io_by_year[year][io_name] += count
                all_ios[io_name] += count
            elif is_ngo(entity_text):
                ngo_name = entity_text.strip()[:50]
                ngo_by_year[year][ngo_name] += count
                all_ngos[ngo_name] += count

    return {
        'country_by_year': dict(country_by_year),
        'continent_by_year': dict(continent_by_year),
        'io_by_year': dict(io_by_year),
        'ngo_by_year': dict(ngo_by_year),
        'all_countries': all_countries,
        'all_continents': all_continents,
        'all_ios': all_ios,
        'all_ngos': all_ngos,
    }


def smooth_series(values, window=3):
    """Apply rolling average smoothing."""
    if len(values) < window:
        return values

    smoothed = []
    for i in range(len(values)):
        start = max(0, i - window // 2)
        end = min(len(values), i + window // 2 + 1)
        smoothed.append(sum(values[start:end]) / (end - start))

    return smoothed


def plot_time_series(data_by_year, top_n, title, output_path, ylabel='Mentions', smooth=True):
    """Plot time series for top N entities with optional smoothing."""

    # Get all years and entities
    all_years = sorted(data_by_year.keys())
    if not all_years:
        print(f"No data for {title}")
        return

    # Aggregate total counts per entity
    total_counts = Counter()
    for year_data in data_by_year.values():
        total_counts.update(year_data)

    # Get top N entities (default to 8 for cleaner plots)
    top_entities = [e for e, _ in total_counts.most_common(min(top_n, 8))]

    if not top_entities:
        print(f"No entities for {title}")
        return

    # Use a nice color palette
    colors = plt.cm.tab10(range(len(top_entities)))

    # Build time series
    fig, ax = plt.subplots(figsize=(14, 6))

    for i, entity in enumerate(top_entities):
        counts = [data_by_year.get(year, {}).get(entity, 0) for year in all_years]

        if smooth and len(counts) > 3:
            counts_smooth = smooth_series(counts, window=3)
            ax.plot(all_years, counts_smooth, label=entity, linewidth=2.5,
                    color=colors[i], alpha=0.9)
            # Add faint raw data
            ax.plot(all_years, counts, linewidth=0.5, color=colors[i], alpha=0.3)
        else:
            ax.plot(all_years, counts, marker='o', label=entity, linewidth=2,
                    markersize=3, color=colors[i])

    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Better legend
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlim(min(all_years) - 1, max(all_years) + 1)

    # Add subtle background shading for decades
    for decade in range(1930, 2020, 10):
        if decade % 20 == 0:
            ax.axvspan(decade, decade + 10, alpha=0.05, color='gray')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Analyze entities from thesis documents')
    parser.add_argument('entities_file', help='JSONL file with extracted entities')
    parser.add_argument('excel_file', help='Excel file with document metadata')
    parser.add_argument('output_dir', help='Output directory for plots and data')
    parser.add_argument('--top', '-t', type=int, default=8, help='Number of top entities to plot (default: 8)')

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading entities...")
    entities = load_entities(args.entities_file)
    print(f"  Loaded {len(entities)} documents")

    print("Loading metadata...")
    metadata = load_metadata(args.excel_file)
    print(f"  Loaded metadata for {len(metadata)} documents")

    print("Analyzing entities...")
    analysis = analyze_entities(entities, metadata)

    # Print summaries
    print(f"\n=== Top {args.top} Countries ===")
    for country, count in analysis['all_countries'].most_common(args.top):
        print(f"  {country}: {count}")

    print(f"\n=== Top {args.top} Continents ===")
    for continent, count in analysis['all_continents'].most_common(args.top):
        print(f"  {continent}: {count}")

    print(f"\n=== Top {args.top} International Organizations ===")
    for io, count in analysis['all_ios'].most_common(args.top):
        print(f"  {io}: {count}")

    print(f"\n=== Top {args.top} NGOs ===")
    for ngo, count in analysis['all_ngos'].most_common(args.top):
        print(f"  {ngo}: {count}")

    # Generate plots
    print("\nGenerating plots...")

    plot_time_series(
        analysis['continent_by_year'], args.top,
        f'Top {args.top} Continents Mentioned Over Time',
        os.path.join(args.output_dir, 'continents_timeseries.png')
    )

    plot_time_series(
        analysis['country_by_year'], args.top,
        f'Top {args.top} Countries Mentioned Over Time',
        os.path.join(args.output_dir, 'countries_timeseries.png')
    )

    plot_time_series(
        analysis['io_by_year'], args.top,
        f'Top {args.top} International Organizations Over Time',
        os.path.join(args.output_dir, 'ios_timeseries.png')
    )

    plot_time_series(
        analysis['ngo_by_year'], min(args.top, len(analysis['all_ngos'])),
        'NGOs Mentioned Over Time',
        os.path.join(args.output_dir, 'ngos_timeseries.png')
    )

    # Save data as JSON
    output_json = os.path.join(args.output_dir, 'entity_analysis.json')
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'top_countries': dict(analysis['all_countries'].most_common(50)),
            'top_continents': dict(analysis['all_continents'].most_common()),
            'top_ios': dict(analysis['all_ios'].most_common(50)),
            'top_ngos': dict(analysis['all_ngos'].most_common(50)),
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_json}")

    print("\nDone!")


if __name__ == '__main__':
    main()
