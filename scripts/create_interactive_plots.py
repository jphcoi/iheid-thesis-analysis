#!/usr/bin/env python3
"""
Create interactive Plotly visualizations for entity analysis.
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


def load_data(entities_file, excel_file):
    """Load entities and metadata."""
    # Load entities
    entities = []
    with open(entities_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entities.append(json.loads(line))

    # Load metadata
    df = pd.read_excel(excel_file)
    metadata = {}
    for _, row in df.iterrows():
        doc_id = str(row['Nom livrable']).replace('.txt', '')
        date_pub = row.get('Date de publication')
        year = None
        if pd.notna(date_pub):
            match = re.search(r'(19\d{2}|20\d{2})', str(date_pub))
            if match:
                year = int(match.group(1))
        metadata[doc_id] = {'year': year}

    return entities, metadata


def analyze_for_plotly(entities, metadata):
    """Analyze entities for Plotly visualization."""

    country_by_year = defaultdict(lambda: defaultdict(int))
    continent_by_year = defaultdict(lambda: defaultdict(int))
    io_by_year = defaultdict(lambda: defaultdict(int))
    ngo_by_year = defaultdict(lambda: defaultdict(int))
    person_by_year = defaultdict(lambda: defaultdict(int))
    docs_by_year = defaultdict(int)  # Count documents per year
    words_by_year = defaultdict(int)  # Count words per year for normalization

    for doc in entities:
        doc_id = doc['doc_id']
        meta = metadata.get(doc_id, {})
        year = meta.get('year')
        if not year:
            continue

        docs_by_year[year] += 1
        # Track word count for proper normalization
        words_processed = doc.get('words_processed', 0)
        words_by_year[year] += words_processed

        # Locations
        loc_entities = doc.get('entities_by_type', {}).get('LOC', {})
        for entity_text, count in loc_entities.items():
            continent = get_continent_from_text(entity_text)
            if continent:
                continent_by_year[year][continent] += count

            country, country_continent, _ = classify_location(entity_text)
            if country:
                country_by_year[year][country] += count
                if country_continent:
                    continent_by_year[year][country_continent] += count

        # Organizations
        org_entities = doc.get('entities_by_type', {}).get('ORG', {})
        for entity_text, count in org_entities.items():
            io_name = normalize_io(entity_text)
            if io_name:
                io_by_year[year][io_name] += count
            elif is_ngo(entity_text):
                # Normalize NGO name (lowercase, clean up)
                ngo_name = entity_text.lower().strip()
                ngo_by_year[year][ngo_name] += count

        # Persons (from PER and PERSON entity types)
        for per_type in ['PER', 'PERSON']:
            per_entities = doc.get('entities_by_type', {}).get(per_type, {})
            for entity_text, count in per_entities.items():
                person_name = normalize_person(entity_text)
                if person_name:
                    person_by_year[year][person_name] += count

    return {
        'country_by_year': dict(country_by_year),
        'continent_by_year': dict(continent_by_year),
        'io_by_year': dict(io_by_year),
        'ngo_by_year': dict(ngo_by_year),
        'person_by_year': dict(person_by_year),
        'docs_by_year': dict(docs_by_year),
        'words_by_year': dict(words_by_year),
    }


def create_interactive_plot(data_by_year, title, output_file, top_n=15, words_by_year=None):
    """Create interactive Plotly time series with smoothing and normalization options.

    Normalization is by word count (per 100k words) for rigorous comparison across years.
    """

    all_years = sorted(data_by_year.keys())
    if not all_years:
        return

    # Get top entities
    total_counts = Counter()
    for year_data in data_by_year.values():
        total_counts.update(year_data)

    top_entities = [e for e, _ in total_counts.most_common(top_n)]

    # Build dataframe with both raw counts and normalized values
    df_data = []
    for year in all_years:
        word_count = words_by_year.get(year, 1) if words_by_year else 1
        for entity in top_entities:
            count = data_by_year.get(year, {}).get(entity, 0)
            # Normalize: mentions per 100k words (standard text analysis metric)
            normalized = (count / word_count * 100000) if word_count > 0 else 0
            df_data.append({
                'year': year,
                'entity': entity,
                'count': count,
                'normalized': normalized,
                'word_count': word_count
            })

    df = pd.DataFrame(df_data)

    # Create figure
    fig = go.Figure()

    # Extended color palette for up to 50 entities
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#636363', '#969696', '#bdbdbd', '#d9d9d9', '#252525',
        '#31a354', '#74c476', '#a1d99b', '#c7e9c0', '#e5f5e0',
        '#3182bd', '#6baed6', '#9ecae1', '#c6dbef', '#deebf7',
        '#e6550d', '#fd8d3c', '#fdae6b', '#fdd0a2', '#fee6ce',
        '#756bb1', '#9e9ac8', '#bcbddc', '#dadaeb', '#efedf5',
        '#843c39', '#ad494a', '#d6616b', '#e7969c', '#fcbba1',
        '#7b4173', '#a55194', '#ce6dbd', '#de9ed6', '#f1b6da'
    ]

    # Smoothing windows to support
    smoothing_windows = [1, 3, 5, 7, 10]  # 1 = no smoothing
    norm_modes = ['raw', 'normalized']  # raw counts vs normalized per 100k words

    # Get word counts series for normalization
    word_counts_series = pd.Series({year: words_by_year.get(year, 1) for year in all_years}).sort_index()

    # Add traces: for each entity, for each smoothing window, for each norm mode
    # Structure: [entity0_smooth1_raw, entity0_smooth1_norm, entity0_smooth3_raw, ...]
    for i, entity in enumerate(top_entities):
        entity_df = df[df['entity'] == entity].sort_values('year')
        years = entity_df['year'].values
        counts_raw = entity_df['count'].values

        for window in smoothing_windows:
            for norm_mode in norm_modes:
                if window == 1:
                    # No smoothing
                    if norm_mode == 'raw':
                        values = counts_raw
                    else:
                        # Per-year normalization: mentions per 100k words
                        word_counts = word_counts_series.loc[years].values
                        values = counts_raw / word_counts * 100000
                else:
                    # Apply smoothing
                    smoothed_counts = pd.Series(counts_raw).rolling(
                        window=window, center=True, min_periods=1).mean().values

                    if norm_mode == 'raw':
                        values = smoothed_counts
                    else:
                        # Smooth both entity counts AND word counts, then divide
                        word_counts = word_counts_series.loc[years].values
                        smoothed_words = pd.Series(word_counts).rolling(
                            window=window, center=True, min_periods=1).mean().values
                        values = smoothed_counts / smoothed_words * 100000

                # Only show raw counts, no smoothing by default
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

    # Create visibility arrays
    n_windows = len(smoothing_windows)
    n_norms = len(norm_modes)
    n_traces = top_n * n_windows * n_norms

    def get_visibility_and_legend(window_idx, norm_idx, top_filter=None):
        """Get visibility and showlegend arrays for given settings."""
        vis = [False] * n_traces
        legend = [False] * n_traces
        for i in range(top_n):
            for w in range(n_windows):
                for n in range(n_norms):
                    trace_idx = i * (n_windows * n_norms) + w * n_norms + n
                    if w == window_idx and n == norm_idx and (top_filter is None or i < top_filter):
                        vis[trace_idx] = True
                        legend[trace_idx] = True
        return vis, legend

    # Create combined dropdown for smoothing + normalization combinations
    combined_buttons = []
    for w_idx, window in enumerate(smoothing_windows):
        smooth_label = "Raw" if window == 1 else f"{window}y MA"
        for n_idx, norm_mode in enumerate(norm_modes):
            norm_label = "Counts" if norm_mode == 'raw' else "Per 100k words"
            label = f"{smooth_label} | {norm_label}"
            vis, legend = get_visibility_and_legend(w_idx, n_idx)
            y_title = "Mentions" if norm_mode == 'raw' else "Mentions per 100k words"
            combined_buttons.append(
                dict(label=label, method="update",
                     args=[{"visible": vis, "showlegend": legend},
                           {"yaxis.title.text": y_title}])
            )

    # Top N buttons (use default settings: raw, no smoothing)
    vis10, leg10 = get_visibility_and_legend(0, 0, 10)
    vis20, leg20 = get_visibility_and_legend(0, 0, 20)
    vis50, leg50 = get_visibility_and_legend(0, 0, min(50, top_n))
    top_buttons = [
        dict(label="Top 10", method="update",
             args=[{"visible": vis10, "showlegend": leg10}]),
        dict(label="Top 20", method="update",
             args=[{"visible": vis20, "showlegend": leg20}]),
        dict(label="Top 50", method="update",
             args=[{"visible": vis50, "showlegend": leg50}]),
    ]

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis_title='Year',
        yaxis_title='Mentions',
        hovermode='x unified',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02
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
                y=1.2,
                yanchor="top"
            ),
            dict(
                type="buttons",
                direction="left",
                buttons=top_buttons,
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.35,
                xanchor="left",
                y=1.2,
                yanchor="top"
            ),
        ],
        annotations=[
            dict(text="View:", x=0, xref="paper", y=1.2, yref="paper",
                 showarrow=False, xanchor="right"),
            dict(text="Filter:", x=0.33, xref="paper", y=1.2, yref="paper",
                 showarrow=False, xanchor="right"),
        ],
        width=1200,
        height=700,
    )

    fig.write_html(output_file)
    print(f"Saved: {output_file}")


def main():
    print("Loading data...")
    entities, metadata = load_data(
        '/Users/jpcointet/Desktop/iheid these/entities_full.jsonl',
        '/Users/jpcointet/Desktop/iheid these/IHEID_LOT_1_MD_FILTRE_SUR_THESES.xlsx'
    )
    print(f"  Loaded {len(entities)} documents")

    print("Analyzing entities...")
    analysis = analyze_for_plotly(entities, metadata)

    # Create output directory
    os.makedirs('/Users/jpcointet/Desktop/iheid these/output', exist_ok=True)

    print("Creating interactive plots...")

    words_by_year = analysis['words_by_year']

    # Print word count stats for verification
    total_words = sum(words_by_year.values())
    print(f"  Total words across all years: {total_words:,}")

    create_interactive_plot(
        analysis['continent_by_year'],
        'Continents Mentioned Over Time (Interactive)',
        '/Users/jpcointet/Desktop/iheid these/output/continents_interactive.html',
        top_n=10,  # Include all continents
        words_by_year=words_by_year
    )

    create_interactive_plot(
        analysis['country_by_year'],
        'Countries Mentioned Over Time (Interactive)',
        '/Users/jpcointet/Desktop/iheid these/output/countries_interactive.html',
        top_n=50,
        words_by_year=words_by_year
    )

    create_interactive_plot(
        analysis['io_by_year'],
        'International Organizations Over Time (Interactive)',
        '/Users/jpcointet/Desktop/iheid these/output/ios_interactive.html',
        top_n=50,
        words_by_year=words_by_year
    )

    create_interactive_plot(
        analysis['ngo_by_year'],
        'NGOs Mentioned Over Time (Interactive)',
        '/Users/jpcointet/Desktop/iheid these/output/ngos_interactive.html',
        top_n=20,
        words_by_year=words_by_year
    )

    create_interactive_plot(
        analysis['person_by_year'],
        'Historical Figures Mentioned Over Time (Interactive)',
        '/Users/jpcointet/Desktop/iheid these/output/persons_interactive.html',
        top_n=50,
        words_by_year=words_by_year
    )

    print("\nDone!")


if __name__ == '__main__':
    main()
