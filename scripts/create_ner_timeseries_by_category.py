#!/usr/bin/env python3
"""
Create separate interactive NER time series visualizations for each subcategory:
- PhD at IHEID
- PhD at HEI
- PhD at IUED
- Master at IHEID
- Master at HEI
- Master at IUED
- All PhD (across institutions)
- All Master (across institutions)

Output: Individual HTML files for each subcategory.
"""

import os
import sys
import json
import re
from collections import defaultdict, Counter
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add parent directory to path for imports
sys.path.insert(0, '/Users/jpcointet/Desktop/iheid these')

# Import normalization functions from analyze_entities
from analyze_entities import (
    get_continent_from_text, classify_location, normalize_io, is_ngo, normalize_person
)


def load_data(entities_file, excel_file, thesis_type_file=None):
    """Load entities and metadata with thesis type and institution."""
    # Load entities
    entities = []
    with open(entities_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entities.append(json.loads(line))

    # Load thesis type mapping from wordkrill_positions.csv if available
    thesis_type_map = {}
    if thesis_type_file and os.path.exists(thesis_type_file):
        df_thesis = pd.read_csv(thesis_type_file)
        for _, row in df_thesis.iterrows():
            doc_id = str(row['doc_id'])
            thesis_type = row['thesis_type']
            # Normalize: "Master/Other" -> "Master"
            if 'Master' in thesis_type:
                thesis_type_map[doc_id] = 'Master'
            elif 'PhD' in thesis_type:
                thesis_type_map[doc_id] = 'PhD'
            else:
                thesis_type_map[doc_id] = 'Other'
        print(f"  Loaded thesis type mapping for {len(thesis_type_map)} documents")

    # Load metadata from Excel
    df = pd.read_excel(excel_file)
    metadata = {}

    for _, row in df.iterrows():
        doc_id = str(row['Nom livrable']).replace('.txt', '')

        # Extract year
        date_pub = row.get('Date de publication')
        year = None
        if pd.notna(date_pub):
            match = re.search(r'(19\d{2}|20\d{2})', str(date_pub))
            if match:
                year = int(match.group(1))

        # Get thesis type from mapping file (preferred) or fall back to 'Unknown'
        thesis_type = thesis_type_map.get(doc_id, 'Unknown')

        # Extract institution
        institut_raw = str(row.get('Institut', '')).strip().upper() if pd.notna(row.get('Institut')) else ''
        if 'HEI' in institut_raw and 'IHEID' not in institut_raw:
            institution = 'HEI'
        elif 'IUED' in institut_raw:
            institution = 'IUED'
        elif 'IHEID' in institut_raw:
            institution = 'IHEID'
        else:
            institution = 'Unknown'

        metadata[doc_id] = {
            'year': year,
            'thesis_type': thesis_type,
            'institution': institution,
        }

    return entities, metadata


def filter_entities_by_category(entities, metadata, thesis_type=None, institution=None):
    """Filter entities based on thesis type and/or institution."""
    filtered = []
    for doc in entities:
        doc_id = doc['doc_id']
        meta = metadata.get(doc_id, {})

        # Apply filters
        if thesis_type and meta.get('thesis_type') != thesis_type:
            continue
        if institution and meta.get('institution') != institution:
            continue
        if not meta.get('year'):
            continue

        filtered.append((doc, meta))

    return filtered


def analyze_filtered_entities(filtered_docs):
    """Analyze entities from filtered documents."""

    results = {
        'countries': defaultdict(lambda: defaultdict(int)),  # year -> entity -> count
        'continents': defaultdict(lambda: defaultdict(int)),
        'ios': defaultdict(lambda: defaultdict(int)),
        'ngos': defaultdict(lambda: defaultdict(int)),
        'persons': defaultdict(lambda: defaultdict(int)),
    }

    words_by_year = defaultdict(int)
    docs_by_year = defaultdict(int)

    for doc, meta in filtered_docs:
        year = meta['year']
        docs_by_year[year] += 1
        words_by_year[year] += doc.get('words_processed', 0)

        # Process LOC entities
        loc_entities = doc.get('entities_by_type', {}).get('LOC', {})
        for entity_text, count in loc_entities.items():
            continent = get_continent_from_text(entity_text)
            if continent:
                results['continents'][year][continent] += count

            country, country_continent, _ = classify_location(entity_text)
            if country:
                results['countries'][year][country] += count
                if country_continent:
                    results['continents'][year][country_continent] += count

        # Process ORG entities
        org_entities = doc.get('entities_by_type', {}).get('ORG', {})
        for entity_text, count in org_entities.items():
            io_name = normalize_io(entity_text)
            if io_name:
                results['ios'][year][io_name] += count
            elif is_ngo(entity_text):
                ngo_name = entity_text.lower().strip()
                results['ngos'][year][ngo_name] += count

        # Process PER entities
        for per_type in ['PER', 'PERSON']:
            per_entities = doc.get('entities_by_type', {}).get(per_type, {})
            for entity_text, count in per_entities.items():
                person_name = normalize_person(entity_text)
                if person_name:
                    results['persons'][year][person_name] += count

    return results, dict(words_by_year), dict(docs_by_year)


def get_top_entities(data_by_year, top_n=20):
    """Get top N entities across all years."""
    total_counts = Counter()
    for year_data in data_by_year.values():
        total_counts.update(year_data)
    return [e for e, _ in total_counts.most_common(top_n)]


def create_subcategory_plot(results, words_by_year, docs_by_year, category_name,
                            title_suffix, output_file, top_n=15):
    """Create interactive plot for a single subcategory."""

    data_by_year = results.get(category_name, {})
    if not data_by_year:
        print(f"  No data for {category_name}")
        return

    top_entities = get_top_entities(data_by_year, top_n)
    if not top_entities:
        print(f"  No entities for {category_name}")
        return

    all_years = sorted(data_by_year.keys())

    # Extended color palette
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#636363', '#969696', '#bdbdbd', '#d9d9d9', '#252525',
    ]

    # Smoothing windows
    smoothing_windows = [1, 3, 5, 7, 10]
    norm_modes = ['raw', 'normalized']

    fig = go.Figure()

    # Add traces for each entity, smoothing window, and normalization mode
    for i, entity in enumerate(top_entities):
        years = []
        counts_raw = []

        for year in all_years:
            years.append(year)
            counts_raw.append(data_by_year.get(year, {}).get(entity, 0))

        years = list(years)
        counts_raw = list(counts_raw)

        for window in smoothing_windows:
            for norm_mode in norm_modes:
                if window == 1:
                    if norm_mode == 'raw':
                        values = counts_raw
                    else:
                        values = []
                        for j, year in enumerate(years):
                            word_count = words_by_year.get(year, 1)
                            normalized = (counts_raw[j] / word_count * 100000) if word_count > 0 else 0
                            values.append(normalized)
                else:
                    # Apply smoothing
                    smoothed = pd.Series(counts_raw).rolling(
                        window=window, center=True, min_periods=1).mean().values

                    if norm_mode == 'raw':
                        values = list(smoothed)
                    else:
                        values = []
                        word_counts = [words_by_year.get(y, 1) for y in years]
                        smoothed_words = pd.Series(word_counts).rolling(
                            window=window, center=True, min_periods=1).mean().values
                        for j in range(len(years)):
                            normalized = (smoothed[j] / smoothed_words[j] * 100000) if smoothed_words[j] > 0 else 0
                            values.append(normalized)

                # Default: raw, no smoothing
                visible = (window == 1 and norm_mode == 'raw')

                fig.add_trace(go.Scatter(
                    x=years,
                    y=values,
                    mode='lines+markers',
                    name=entity,
                    line=dict(color=colors[i % len(colors)], width=2),
                    marker=dict(size=4),
                    visible=visible,
                    showlegend=True,
                    legendgroup=entity
                ))

    # Create visibility arrays for dropdown
    n_windows = len(smoothing_windows)
    n_norms = len(norm_modes)
    n_entities = len(top_entities)
    n_traces = n_entities * n_windows * n_norms

    def get_visibility(window_idx, norm_idx):
        vis = [False] * n_traces
        for i in range(n_entities):
            trace_idx = i * (n_windows * n_norms) + window_idx * n_norms + norm_idx
            vis[trace_idx] = True
        return vis

    # Combined dropdown buttons
    combined_buttons = []
    for w_idx, window in enumerate(smoothing_windows):
        smooth_label = "Raw" if window == 1 else f"{window}y MA"
        for n_idx, norm_mode in enumerate(norm_modes):
            norm_label = "Counts" if norm_mode == 'raw' else "Per 100k words"
            label = f"{smooth_label} | {norm_label}"
            vis = get_visibility(w_idx, n_idx)
            y_title = "Mentions" if norm_mode == 'raw' else "Mentions per 100k words"
            combined_buttons.append(
                dict(label=label, method="update",
                     args=[{"visible": vis}, {"yaxis.title.text": y_title}])
            )

    # Calculate summary stats
    total_docs = sum(docs_by_year.values())
    total_words = sum(words_by_year.values())
    year_range = f"{min(all_years)}-{max(all_years)}" if all_years else "N/A"

    category_display = {
        'countries': 'Countries',
        'continents': 'Continents',
        'ios': 'International Organizations',
        'ngos': 'NGOs',
        'persons': 'Historical Figures'
    }

    fig.update_layout(
        title=dict(
            text=f"{category_display.get(category_name, category_name)}: {title_suffix}<br>"
                 f"<sup>{total_docs} documents | {total_words:,} words | {year_range}</sup>",
            font=dict(size=16),
            y=0.95,
            x=0.5,
            xanchor='center'
        ),
        xaxis_title='Year',
        yaxis_title='Mentions',
        hovermode='x unified',
        margin=dict(t=100),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02,
            font=dict(size=10)
        ),
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                buttons=combined_buttons,
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.0,
                xanchor="left",
                y=1.18,
                yanchor="top"
            ),
        ],
        annotations=[
            dict(text="View:", x=-0.01, xref="paper", y=1.18, yref="paper",
                 showarrow=False, xanchor="right"),
        ],
        width=1100,
        height=620,
    )

    fig.write_html(output_file)
    print(f"  Saved: {output_file}")


def create_all_categories_for_subcategory(entities, metadata, thesis_type, institution, output_dir):
    """Create all category plots for a specific thesis_type + institution combination."""

    # Filter entities
    filtered_docs = filter_entities_by_category(entities, metadata, thesis_type, institution)

    if not filtered_docs:
        print(f"  No documents found for {thesis_type} at {institution}")
        return

    print(f"\n  Processing {thesis_type} at {institution}: {len(filtered_docs)} documents")

    # Analyze
    results, words_by_year, docs_by_year = analyze_filtered_entities(filtered_docs)

    # Create title suffix
    title_suffix = f"{thesis_type} Theses at {institution}"

    # Create subdirectory
    subdir = os.path.join(output_dir, f"{thesis_type.lower()}_{institution.lower()}")
    os.makedirs(subdir, exist_ok=True)

    # Create plots for each category
    categories = [
        ('countries', 15),
        ('continents', 6),
        ('ios', 15),
        ('ngos', 10),
        ('persons', 15),
    ]

    for category_name, top_n in categories:
        output_file = os.path.join(subdir, f"{category_name}.html")
        create_subcategory_plot(
            results, words_by_year, docs_by_year,
            category_name, title_suffix, output_file, top_n
        )


def create_thesis_type_aggregate(entities, metadata, thesis_type, output_dir):
    """Create plots for a thesis type across all institutions."""

    filtered_docs = filter_entities_by_category(entities, metadata, thesis_type=thesis_type)

    if not filtered_docs:
        print(f"  No documents found for {thesis_type}")
        return

    print(f"\n  Processing all {thesis_type}: {len(filtered_docs)} documents")

    results, words_by_year, docs_by_year = analyze_filtered_entities(filtered_docs)

    title_suffix = f"All {thesis_type} Theses"

    subdir = os.path.join(output_dir, f"all_{thesis_type.lower()}")
    os.makedirs(subdir, exist_ok=True)

    categories = [
        ('countries', 15),
        ('continents', 6),
        ('ios', 15),
        ('ngos', 10),
        ('persons', 15),
    ]

    for category_name, top_n in categories:
        output_file = os.path.join(subdir, f"{category_name}.html")
        create_subcategory_plot(
            results, words_by_year, docs_by_year,
            category_name, title_suffix, output_file, top_n
        )


def create_institution_aggregate(entities, metadata, institution, output_dir):
    """Create plots for an institution across all thesis types."""

    filtered_docs = filter_entities_by_category(entities, metadata, institution=institution)

    if not filtered_docs:
        print(f"  No documents found for {institution}")
        return

    print(f"\n  Processing all at {institution}: {len(filtered_docs)} documents")

    results, words_by_year, docs_by_year = analyze_filtered_entities(filtered_docs)

    title_suffix = f"All Theses at {institution}"

    subdir = os.path.join(output_dir, f"all_{institution.lower()}")
    os.makedirs(subdir, exist_ok=True)

    categories = [
        ('countries', 15),
        ('continents', 6),
        ('ios', 15),
        ('ngos', 10),
        ('persons', 15),
    ]

    for category_name, top_n in categories:
        output_file = os.path.join(subdir, f"{category_name}.html")
        create_subcategory_plot(
            results, words_by_year, docs_by_year,
            category_name, title_suffix, output_file, top_n
        )


def main():
    print("Loading data...")
    entities, metadata = load_data(
        '/Users/jpcointet/Desktop/iheid these/entities_full.jsonl',
        '/Users/jpcointet/Desktop/iheid these/IHEID_LOT_1_MD_FILTRE_SUR_THESES.xlsx',
        '/Users/jpcointet/Desktop/iheid these/output/wordkrill_positions.csv'
    )
    print(f"  Loaded {len(entities)} documents")

    # Print metadata statistics
    thesis_type_counts = defaultdict(int)
    institution_counts = defaultdict(int)
    combo_counts = defaultdict(int)

    for meta in metadata.values():
        thesis_type_counts[meta['thesis_type']] += 1
        institution_counts[meta['institution']] += 1
        combo_counts[(meta['thesis_type'], meta['institution'])] += 1

    print("\n=== Thesis Type Distribution ===")
    for t, c in sorted(thesis_type_counts.items()):
        print(f"  {t}: {c}")

    print("\n=== Institution Distribution ===")
    for i, c in sorted(institution_counts.items()):
        print(f"  {i}: {c}")

    print("\n=== Combination Distribution ===")
    for (t, i), c in sorted(combo_counts.items()):
        print(f"  {t} at {i}: {c}")

    # Create output directory
    output_dir = '/Users/jpcointet/Desktop/iheid these/output/ner_by_subcategory'
    os.makedirs(output_dir, exist_ok=True)

    print("\n" + "="*60)
    print("Creating subcategory visualizations...")
    print("="*60)

    # Define thesis types and institutions
    thesis_types = ['PhD', 'Master']
    institutions = ['HEI', 'IUED', 'IHEID']

    # 1. Create plots for each thesis_type + institution combination
    for thesis_type in thesis_types:
        for institution in institutions:
            create_all_categories_for_subcategory(
                entities, metadata, thesis_type, institution, output_dir
            )

    # 2. Create aggregate plots by thesis type (all institutions)
    print("\n" + "="*60)
    print("Creating thesis type aggregates...")
    print("="*60)
    for thesis_type in thesis_types:
        create_thesis_type_aggregate(entities, metadata, thesis_type, output_dir)

    # 3. Create aggregate plots by institution (all thesis types)
    print("\n" + "="*60)
    print("Creating institution aggregates...")
    print("="*60)
    for institution in institutions:
        create_institution_aggregate(entities, metadata, institution, output_dir)

    # Print summary
    print("\n" + "="*60)
    print("=== Output Directory Structure ===")
    print("="*60)
    print(f"\n{output_dir}/")

    # List created directories
    for thesis_type in thesis_types:
        for institution in institutions:
            subdir = f"{thesis_type.lower()}_{institution.lower()}"
            print(f"  {subdir}/")
            print("    countries.html, continents.html, ios.html, ngos.html, persons.html")

    for thesis_type in thesis_types:
        print(f"  all_{thesis_type.lower()}/")
        print("    countries.html, continents.html, ios.html, ngos.html, persons.html")

    for institution in institutions:
        print(f"  all_{institution.lower()}/")
        print("    countries.html, continents.html, ios.html, ngos.html, persons.html")

    print("\nDone!")


if __name__ == '__main__':
    main()
