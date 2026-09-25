# IHEID Thesis Entity Extraction Pipeline Documentation

This document describes all conversion, translation, and normalization operations used in the NER (Named Entity Recognition) pipeline for analyzing IHEID thesis documents.

---

## 1. Pipeline Overview

```
ALTO XML files → Plai n Text → NER Extraction → Entity Analysis → Visualizations
```

### Processing Statistics

| Stage | Count |
|-------|-------|
| Documents copied (ALTO folders) | 3,392 |
| Text files extracted | 3,392 |
| Documents with NER entities | 3,392 |
| German documents (re-processed) | 65 |
| Total text extracted | ~1.3 GB |
| **Total words processed (full docs)** | **189,836,734** |
| PhD theses identified | 704 |
| Master theses / other | 2,438 |

---

## 2. Text Extraction (ALTO XML → Plain Text)

**Script**: `extract_alto_text.py`

### Process
- Reads ALTO XML files (OCR output format)
- Extracts text from `<String CONTENT="..."/>` elements
- Preserves page markers: `--- Page N ---`
- Maintains reading order (top-to-bottom, left-to-right by bounding boxes)

### Statistics
- Total text files: 3,392
- Total text size: ~1.3 GB
- Average document length: ~400 KB

---

## 3. Language Detection

**Script**: `extract_ner.py`

### Method
Simple keyword-based detection using common words in each language:

| Language | Detection Keywords |
|----------|-------------------|
| **French** | le, la, les, de, du, des, et, en, un, une, est, sont, dans, pour, que, qui |
| **English** | the, of, and, to, in, is, for, that, with, as, was, are, be, this, by |
| **German** | der, die, das, und, ist, von, mit, für, auf, den, dem, ein, eine, auch, sich, nicht |

### Results
| Language | Documents |
|----------|-----------|
| French | ~1,800 |
| English | ~1,100 |
| German | 65 |

---

## 4. NER Extraction

**Script**: `extract_ner.py`

### spaCy Models Used
| Language | Model |
|----------|-------|
| English | `en_core_web_sm` |
| French | `fr_core_news_sm` |
| German | `de_core_news_sm` |

### Configuration
- **Full document extraction**: All words processed (average ~56k words/doc)
- Entity types extracted: LOC, ORG, PER, MISC
- Parallel workers: 6

### Output Files
| File | Description |
|------|-------------|
| `entities_full.jsonl` | Full document NER (19.6 MB, 189M words) |
| `entities_merged_20k.jsonl` | First 20k words only (legacy) |

### Entity Types
| Type | Description | Count (approx.) |
|------|-------------|-----------------|
| LOC | Locations (countries, cities, regions) | ~100,000 |
| ORG | Organizations (IOs, NGOs, companies) | ~80,000 |
| PER | Person names | ~50,000 |
| MISC | Miscellaneous entities | ~30,000 |

---

## 5. Country Normalization

**Script**: `analyze_entities.py`

### Purpose
Merge country name variants across English, French, and German into canonical English names.

### Complete Normalization Mapping

#### Major Countries (with full multilingual variants)

| Canonical | English | French | German |
|-----------|---------|--------|--------|
| **USA** | united states, usa, america, american, americans | états-unis, etats-unis, américain | vereinigte staaten, amerikanisch |
| **UK** | united kingdom, uk, britain, great britain, england, british | royaume-uni, angleterre | großbritannien |
| **Germany** | germany, german | allemagne, allemand | deutschland, deutsch, deutsche |
| **France** | france, french | français, française | frankreich, französisch |
| **Switzerland** | switzerland, swiss | suisse | schweiz, schweizerisch |
| **Russia** | russia, urss, ussr, soviet, soviets | russie, soviétique, sovietique | russland, russisch, sowjetunion, sovjet |
| **China** | china, chinese | chine, chinois | chinesisch |
| **Japan** | japan, japanese | japon, japonais | japanisch |
| **Italy** | italy, italian | italie | italien, italienisch |
| **Spain** | spain, spanish | espagne | spanien, spanisch |

#### European Countries

| Canonical | Variants (EN/FR/DE) |
|-----------|---------------------|
| Belgium | belgium, belgique, belgien, belgisch |
| Netherlands | netherlands, pays-bas, holland, niederlande, holländisch, niederländisch |
| Austria | austria, autriche, österreich, österreichisch |
| Poland | poland, pologne, polen, polnisch |
| Greece | greece, grèce, griechenland, griechisch |
| Portugal | portugal |
| Sweden | sweden, suède, schweden |
| Norway | norway, norvège, norwegen |
| Denmark | denmark, danemark, dänemark |
| Finland | finland, finlande, finnland |
| Hungary | hungary, hongrie, ungarn |
| Czech Republic | czech republic, république tchèque, tschechien |
| Romania | romania, roumanie, rumänien |
| Bulgaria | bulgaria, bulgarie, bulgarien |
| Ukraine | ukraine, ucrania |
| Yugoslavia | yugoslavia, yougoslavie, jugoslawien |
| Serbia | serbia, serbie, serbien |
| Croatia | croatia, croatie, kroatien |
| Bosnia | bosnia, bosnie, bosnien |
| Albania | albania, albanie, albanien |

#### Americas

| Canonical | Variants (EN/FR/DE) |
|-----------|---------------------|
| Canada | canada, kanada |
| Mexico | mexico, mexique, mexiko |
| Brazil | brazil, brésil, brasilien |
| Argentina | argentina, argentine, argentinien |
| Chile | chile, chili |
| Colombia | colombia, colombie, kolumbien |
| Peru | peru, pérou |
| Venezuela | venezuela |
| Cuba | cuba, kuba |

#### Asia & Middle East

| Canonical | Variants (EN/FR/DE) |
|-----------|---------------------|
| India | india, inde, indian, indien, indisch |
| Pakistan | pakistan |
| Indonesia | indonesia, indonésie, indonesien |
| Vietnam | vietnam, viêt nam |
| Thailand | thailand, thaïlande |
| Malaysia | malaysia, malaisie |
| Philippines | philippines, philippinen |
| Singapore | singapore, singapour, singapur |
| Korea | korea, corée, südkorea, nordkorea |
| Taiwan | taiwan |
| Iran | iran |
| Iraq | iraq, irak |
| Syria | syria, syrie, syrien |
| Israel | israel, israël |
| Palestine | palestine, palestinian, palästina |
| Lebanon | lebanon, liban, libanon |
| Turkey | turkey, turquie, türkei, türkisch |
| Saudi Arabia | saudi arabia, arabie saoudite, saudi-arabien |
| Afghanistan | afghanistan |
| Jordan | jordan, jordanie, jordanien |
| Kuwait | kuwait, koweït |
| UAE | uae, émirats, emirates |
| Qatar | qatar |
| Yemen | yemen, yémen, jemen |
| Oman | oman |
| Bahrain | bahrain, bahreïn |

#### Africa

| Canonical | Variants (EN/FR/DE) |
|-----------|---------------------|
| Egypt | egypt, égypte, ägypten, ägyptisch |
| Algeria | algeria, algérie, algerien |
| Morocco | morocco, maroc, marokko |
| Tunisia | tunisia, tunisie, tunesien |
| Libya | libya, libye, libyen |
| Sudan | sudan, soudan |
| Senegal | senegal, sénégal |
| Nigeria | nigeria |
| South Africa | south africa, afrique du sud, südafrika |
| Kenya | kenya, kenia |
| Ghana | ghana |
| Cameroon | cameroon, cameroun, kamerun |
| Ethiopia | ethiopia, éthiopie, äthiopien |
| Tanzania | tanzania, tanzanie, tansania |
| Congo | congo, kongo |
| Ivory Coast | ivory coast, côte d'ivoire, elfenbeinküste |
| Mali | mali |
| Niger | niger |
| Chad | chad, tchad, tschad |
| Burkina Faso | burkina, burkina faso |
| Rwanda | rwanda, ruanda |
| Burundi | burundi |
| Uganda | uganda, ouganda |
| Zimbabwe | zimbabwe, simbabwe |
| Zambia | zambia, zambie, sambia |
| Mozambique | mozambique, mosambik |
| Madagascar | madagascar, madagaskar |
| Angola | angola |

#### Oceania

| Canonical | Variants (EN/FR/DE) |
|-----------|---------------------|
| Australia | australia, australie, australien |
| New Zealand | new zealand, nouvelle-zélande, neuseeland |

---

## 6. Country to Continent Mapping

| Continent | Countries |
|-----------|-----------|
| **Europe** | France, Germany, UK, Switzerland, Italy, Spain, Belgium, Netherlands, Austria, Poland, Russia, Greece, Portugal, Sweden, Norway, Denmark, Finland |
| **Asia** | China, Japan, India, Pakistan, Indonesia, Vietnam, Thailand, Malaysia, Philippines, Singapore, Korea, Taiwan, Iran, Iraq, Syria, Israel, Palestine, Lebanon, Turkey, Saudi Arabia, Afghanistan |
| **North America** | USA, Canada, Mexico |
| **South America** | Brazil, Argentina, Chile, Colombia, Peru, Venezuela, Bolivia, Ecuador, Paraguay, Uruguay |
| **Central America** | Cuba, Guatemala, Honduras, Nicaragua, Costa Rica, Panama, Haiti, Dominican Republic |
| **Africa** | Egypt, Algeria, Morocco, Tunisia, Senegal, Nigeria, South Africa, Kenya, Ghana, Cameroon, Ethiopia, Tanzania |
| **Oceania** | Australia, New Zealand |

---

## 7. Excluded Locations

### Cities (excluded from country counts)
These are filtered out to avoid double-counting with countries:

```
genève, geneva, paris, london, londres, new york, berlin,
washington, tokyo, beijing, pékin, moscow, moscou, rome,
brussels, bruxelles, vienna, vienne, zurich, zürich, bern, berne
```

### Continent Keywords (tracked separately)
```
europe, european, européen, européenne, asia, asie, asian, asiatique,
africa, afrique, african, africain, america, americas, amérique,
latin america, amérique latine, oceania, océanie
```

---

## 8. International Organization (IO) Normalization

### Complete IO Mapping

| Canonical Name | Variants (EN/FR/DE) |
|----------------|---------------------|
| **United Nations** | onu, united nations, nations unies, the united nations, vereinte nationen, uno (note: 'un' excluded to avoid French false positives) |
| **World Bank** | world bank, banque mondiale, the world bank, weltbank |
| **IMF** | imf, fmi, international monetary fund, fonds monétaire, iwf, internationaler währungsfonds |
| **WTO** | wto, omc, world trade organization, world trade, welthandelsorganisation |
| **WHO** | who, oms, world health organization, world health, weltgesundheitsorganisation |
| **UNESCO** | unesco |
| **UNICEF** | unicef |
| **UNHCR** | unhcr, hcr, the unhcr, flüchtlingshilfswerk |
| **ILO** | ilo, oit, international labour, internationale arbeitsorganisation, iao |
| **ICRC** | icrc, cicr, red cross, croix-rouge, rotes kreuz, ikrk, internationales komitee vom roten kreuz |
| **African Union** | african union, union africaine, oua, oau, afrikanische union |
| **NATO** | nato, otan |
| **OECD** | oecd, ocde |
| **OPEC** | opec, opep |
| **ASEAN** | asean |
| **Mercosur** | mercosur |
| **FAO** | fao, world food |
| **IAEA** | iaea, aiea, iaeo |
| **WIPO** | wipo, ompi |
| **UN Security Council** | the security council, security council, conseil de sécurité, sicherheitsrat |
| **League of Nations** | league of nations, société des nations, völkerbund, sdn |
| **G7** | g7 |
| **G8** | g8 |
| **G20** | g20 |
| **Arab League** | arab league, ligue arabe, arabische liga |

---

## 9. NGO Keywords

NGOs are identified by keyword matching (not normalized):

```
amnesty, greenpeace, oxfam, médecins sans frontières, msf,
human rights watch, hrw, transparency international,
world wildlife, wwf, save the children, care international,
world vision, reporters sans frontières, rsf, doctors without borders,
international crisis group, freedom house
```

---

## 10. Entity Statistics (from 20k word extract)

*Note: These statistics are from the initial 20k word extraction. Full document statistics available in interactive visualizations.*

### Top 15 Countries by Mention Count

| Rank | Country | Mentions |
|------|---------|----------|
| 1 | USA | 7,033 |
| 2 | France | 6,774 |
| 3 | Switzerland | 3,925 |
| 4 | Germany | 3,077 |
| 5 | China | 2,922 |
| 6 | Russia | 2,063 |
| 7 | Italy | 1,650 |
| 8 | Japan | 1,340 |
| 9 | India | 1,303 |
| 10 | UK | 1,203 |
| 11 | Israel | 1,166 |
| 12 | Hungary | 1,066 |
| 13 | Canada | 1,013 |
| 14 | Turkey | 970 |
| 15 | Austria | 842 |

### Top 7 Continents by Mention Count

| Rank | Continent | Mentions |
|------|-----------|----------|
| 1 | Europe | 36,601 |
| 2 | Asia | 17,000 |
| 3 | North America | 8,123 |
| 4 | Africa | 7,183 |
| 5 | South America | 5,276 |
| 6 | Central America | 688 |
| 7 | Oceania | 240 |

### Top 15 International Organizations

| Rank | Organization | Mentions |
|------|--------------|----------|
| 1 | United Nations | 53,787 |
| 2 | ILO | 4,683 |
| 3 | WTO | 4,280 |
| 4 | League of Nations | 2,290 |
| 5 | ICRC | 2,138 |
| 6 | OECD | 1,984 |
| 7 | NATO | 1,818 |
| 8 | World Bank | 1,749 |
| 9 | UN Security Council | 1,466 |
| 10 | IMF | 1,361 |
| 11 | ASEAN | 1,265 |
| 12 | WHO | 787 |
| 13 | UNHCR | 459 |
| 14 | FAO | 337 |
| 15 | WIPO | 322 |

### Top 10 NGOs

| Rank | NGO | Mentions |
|------|-----|----------|
| 1 | MSF | 232 |
| 2 | Amnesty International | 140 |
| 3 | Oxfam | 42 |
| 4 | Human Rights Watch | 35 |
| 5 | Freedom House | 33 |
| 6 | International Crisis Group | 22 |
| 7 | Médecins Sans Frontières | 14 |
| 8 | HRW | 13 |
| 9 | WWF | 13 |
| 10 | Transparency International | 9 |

---

## 11. Known Limitations

1. **Language Detection**: Simple keyword-based detection may misclassify multilingual documents
2. **OCR Quality**: Text extraction depends on ALTO file quality; poor OCR affects entity recognition
3. **Entity Boundaries**: spaCy's entity boundaries may include articles (e.g., "l'URSS" vs "URSS")
4. **Partial Matches**: Normalization uses partial string matching, which may cause false positives
5. **Historical Entities**: Soviet Union entities are mapped to Russia; may not reflect historical accuracy
6. **French 'un' exclusion**: The word 'un' is excluded from UN detection to avoid French article false positives

---

## 12. PhD/Master Thesis Data Consolidation

### Sources
1. **Primary**: `IHEID_LOT_1_MD_FILTRE_SUR_THESES.xlsx` (10,230 records)
2. **Secondary**: `iheid_unified_academic_corpus_nomatch.csv` (8,511 records, 1,633 PhD theses)

### Matching Process
- Fuzzy matching on title and author (threshold: 0.8)
- Year constraint: ±1 year tolerance
- PhD identification: Has director OR matches secondary source PhD

### PhD Thesis Statistics

| Decade | Count |
|--------|-------|
| 1920s | 1 |
| 1930s | 31 |
| 1940s | 17 |
| 1950s | 31 |
| 1960s | 42 |
| 1970s | 54 |
| 1980s | 61 |
| 1990s | 136 |
| 2000s | 233 |
| 2010s | 96 |
| 2020s | 2 |
| **Total** | **704** |

### Output
- `output/consolidated_theses.csv`: All thesis records with standardized fields

---

## 13. PhD-Director and PhD-Jury Networks

**Script**: `create_phd_network.py`

### PhD-Director Network
- Links PhD candidates to their thesis directors
- All nodes retained
- File: `output/phd_director_network.gexf`

| Metric | Value |
|--------|-------|
| PhD candidates | 700 |
| Directors | 210 |
| Edges | 453 |

### Top Directors

| Director | PhDs Supervised |
|----------|-----------------|
| Hans Genberg | 25 |
| Georges Abi-Saab | 21 |
| Keith Krause | 18 |
| Harish Kapur | 14 |
| Richard Baldwin | 14 |
| Curt Gasteyger | 13 |
| Charles Wyplosz | 13 |
| Lucius Caflisch | 12 |
| Andrew Clapham | 12 |
| Philippe Burrin | 9 |

### PhD-Jury Network
- Links PhD candidates to committee members (extracted from NER)
- Filters committee members appearing only once
- Filters historical figures (Max Weber, Adam Smith, etc.)
- File: `output/phd_jury_network_filtered.gexf`

| Metric | Value |
|--------|-------|
| PhD candidates | 700 |
| Committee members (≥2 appearances) | 582 |
| Edges | 2,293 |

### Top Committee Members

| Name | Appearances |
|------|-------------|
| Hans Genberg | 98 |
| Georges Abi-Saab | 86 |
| Richard Baldwin | 45 |
| Keith Krause | 44 |
| Harish Kapur | 42 |
| Philippe Cahier | 36 |
| Paul Guggenheim | 36 |
| Lucius Caflisch | 34 |
| Hans Wehberg | 28 |
| Gilbert Etienne | 26 |

### Historical Figures Filtered
The following are excluded from jury networks (commonly cited but not actual committee members):
- Max Weber, Karl Marx, Adam Smith, John Locke, Thomas Hobbes
- Jean-Jacques Rousseau, Immanuel Kant, Michel Foucault
- John Maynard Keynes, Friedrich Hayek, Milton Friedman
- And ~50 other historical figures

---

## 14. Interactive Visualizations

### Features
- Smoothing options: Raw, 3-year, 5-year, 7-year, 10-year moving average
- **Normalization: Per 100k words** (accounts for variable document lengths)
- Top N filtering: Top 10, 20, or 50 entities
- Combined dropdown for smoothing × normalization

### Normalization Method
When smoothing is applied, both entity counts AND word counts are smoothed before dividing:
```
normalized = smoothed_entity_counts / smoothed_word_counts × 100,000
```

### Output Files

| File | Description |
|------|-------------|
| `continents_interactive.html` | Continent mentions over time |
| `countries_interactive.html` | Country mentions over time (top 50) |
| `ios_interactive.html` | International organizations over time (top 50) |
| `ngos_interactive.html` | NGO mentions over time (top 20) |
| `persons_interactive.html` | Historical figures over time (top 50) |

---

## 15. Thesis Timeline Visualization

**File**: `output/thesis_timeline.html`

Interactive plot showing the temporal distribution of PhD and Master theses.

### Thesis Counts by Decade

| Decade | PhD | Master/Other |
|--------|-----|--------------|
| 1920s | 1 | 7 |
| 1930s | 31 | 43 |
| 1940s | 17 | 34 |
| 1950s | 31 | 31 |
| 1960s | 42 | 62 |
| 1970s | 54 | 112 |
| 1980s | 61 | 282 |
| 1990s | 136 | 961 |
| 2000s | 233 | 905 |
| 2010s | 96 | 1 |
| 2020s | 2 | 0 |
| **Total** | **704** | **2,438** |

---

## 16. Complete Output File List

| File | Description |
|------|-------------|
| `entities_full.jsonl` | NER entities (full documents, 19.6 MB) |
| `entities_merged_20k.jsonl` | NER entities (first 20k words, legacy) |
| `output/consolidated_theses.csv` | Consolidated PhD/Master thesis metadata |
| `output/phd_director_network.gexf` | PhD candidate ↔ director network |
| `output/phd_jury_network_filtered.gexf` | PhD candidate ↔ committee network |
| `output/thesis_timeline.html` | PhD/Master thesis counts over time |
| `output/continents_interactive.html` | Continent mentions over time |
| `output/countries_interactive.html` | Country mentions over time |
| `output/ios_interactive.html` | International organizations over time |
| `output/ngos_interactive.html` | NGO mentions over time |
| `output/persons_interactive.html` | Historical figures over time |
| `output/entity_analysis.json` | Aggregated entity counts |

---

## 17. Scripts

| Script | Purpose |
|--------|---------|
| `extract_alto_text.py` | Extract text from ALTO XML files |
| `extract_ner.py` | Run spaCy NER on documents |
| `analyze_entities.py` | Normalize and analyze entities |
| `create_interactive_plots.py` | Generate Plotly visualizations |
| `create_phd_network.py` | Generate PhD-director/jury networks |

---

*Generated: September 2026*
*Pipeline Version: 2.0*
