# IHEID Thesis Analysis

Interactive visualizations and network analysis of IHEID thesis documents (1928-2022).

## View the Dashboard

**[Open the Dashboard](https://jphcoi.github.io/iheid-thesis-analysis/)**

## Overview

This project analyzes 3,392 academic documents from IHEID (Graduate Institute of International and Development Studies) and its predecessor institutions (HEI and IUED), spanning nearly a century of research.

### Key Statistics

| Metric | Value |
|--------|-------|
| Documents analyzed | 3,392 |
| Words processed | 189.8 million |
| PhD theses | 704 |
| Master theses | 2,438 |
| Time span | 1928-2022 |

## Visualizations

### Named Entity Recognition
- **Countries** - Top 50 countries mentioned, with multilingual normalization (EN/FR/DE)
- **Continents** - Geographic focus by continent over time
- **International Organizations** - UN, WTO, ILO, ICRC, NATO, World Bank, etc.
- **NGOs** - MSF, Amnesty International, Oxfam, Human Rights Watch, etc.
- **Historical Figures** - Notable persons mentioned in theses

### Thesis Production
- **Timeline** - PhD vs Master thesis production over time
- **By Institution** - Breakdown by HEI, IUED, and IHEID

### Network Analysis (GEXF for Gephi)
- **PhD-Director Network** - 700 candidates linked to 210 directors
- **PhD-Jury Network** - 700 candidates linked to 582 committee members

## Features

- **Smoothing**: Raw, 3-year, 5-year, 7-year, 10-year moving averages
- **Normalization**: Per 100k words (accounts for variable document lengths)
- **Top N filtering**: View top 10, 20, or 50 entities
- **Interactive**: Hover for details, zoom, pan

## Methodology

1. **Text Extraction**: ALTO XML → Plain text
2. **Language Detection**: Keyword-based (EN/FR/DE)
3. **NER**: spaCy models (en_core_web_sm, fr_core_news_sm, de_core_news_sm)
4. **Normalization**: Multilingual entity merging
5. **Visualization**: Plotly interactive charts

See [PIPELINE_DOCUMENTATION.md](PIPELINE_DOCUMENTATION.md) for full details.

## Deploying to GitHub Pages

1. Create a new GitHub repository
2. Push the contents of this `output/` folder to the repository
3. Go to Settings → Pages → Source → Deploy from branch (main)
4. Your site will be live at `https://jphcoi.github.io/iheid-thesis-analysis/`

## Data Files

| File | Description |
|------|-------------|
| `consolidated_theses.csv` | All thesis metadata |
| `phd_director_network.gexf` | PhD-Director network (Gephi) |
| `phd_jury_network_filtered.gexf` | PhD-Jury network (Gephi) |

## License

Data sourced from IHEID archives. Analysis tools: spaCy, Plotly, NetworkX.
