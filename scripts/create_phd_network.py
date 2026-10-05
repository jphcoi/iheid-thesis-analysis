#!/usr/bin/env python3
"""
Create PhD-jury and PhD-director networks from thesis metadata and documents.
"""

import os
import re
import json
from collections import defaultdict, Counter
import pandas as pd
import networkx as nx

# Noise words to filter out from jury names
NOISE_WORDS = {
    # Academic/institutional
    'remerciements', 'université', 'university', 'institut', 'institute',
    'professeur', 'professor', 'directeur', 'director', 'thèse', 'thesis',
    'monsieur', 'madame', 'mademoiselle', 'mr', 'mrs', 'ms', 'dr', 'prof',
    'membre', 'member', 'jury', 'président', 'president', 'rapporteur',
    'examinateur', 'examiner', 'soutenance', 'defense', 'faculté', 'faculty',
    'département', 'department', 'genève', 'geneva', 'suisse', 'switzerland',
    # Document structure
    'chapitre', 'chapter', 'introduction', 'conclusion', 'bibliographie',
    'abstract', 'résumé', 'table', 'contents', 'figure', 'annexe', 'appendix',
    'acknowledgements', 'acknowledgments', 'préface', 'preface', 'avant-propos',
    'copyright', 'droits', 'rights', 'reserved', 'publication', 'printed',
    'imprimé', 'édition', 'edition', 'volume', 'numéro', 'number', 'page',
    # Countries/places
    'united kingdom', 'united states', 'france', 'allemagne', 'germany',
    'royaume-uni', 'états-unis', 'etats-unis', 'europe', 'international',
    # Months
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre', 'january', 'february',
    'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
    'november', 'december',
    # Truncated prefixes
    'esseur', 'sident', 'irecteur',
    # Common French text fragments that are NOT names
    'propositions', 'premier', 'ministre', 'premier ministre', 'conseil',
    'commission', 'assemblée', 'général', 'secrétaire', 'délégation',
    # Common article/preposition fragments
    'qui', 'que', 'quoi', 'dont', 'lequel', 'laquelle',
    'doc', 'cit', 'ibid', 'cf', 'voir', 'voir aussi',
    # More noise patterns
    'de la', 'du', 'des', 'le', 'la', 'les', 'un', 'une',
    'press', 'oxford', 'cambridge', 'clarendon', 'university press',
    'mémoire', 'présenté', 'présentée', 'soutenu', 'soutenue',
    'pour obtenir', 'obtention', 'grade', 'doctorat', 'docteur',
    'ère partie', 'ème partie', 'partie', 'section', 'sous-section',
    'op cit', 'loc cit', 'et al', 'passim', 'supra', 'infra',
}

# Historical figures commonly cited but NOT committee members
HISTORICAL_FIGURES = {
    'max weber', 'karl marx', 'adam smith', 'john locke', 'thomas hobbes',
    'jean-jacques rousseau', 'immanuel kant', 'friedrich nietzsche', 'sigmund freud',
    'emile durkheim', 'georg hegel', 'karl popper', 'hannah arendt', 'michel foucault',
    'john maynard keynes', 'david ricardo', 'alfred marshall', 'joseph schumpeter',
    'milton friedman', 'friedrich hayek', 'john stuart mill', 'jeremy bentham',
    'woodrow wilson', 'winston churchill', 'charles de gaulle', 'adolf hitler',
    'joseph stalin', 'vladimir lenin', 'mao zedong', 'franklin roosevelt',
    'theodore roosevelt', 'abraham lincoln', 'napoleon bonaparte', 'otto von bismarck',
    'mahatma gandhi', 'nelson mandela', 'martin luther king', 'che guevara',
    'plato', 'aristotle', 'socrates', 'cicero', 'machiavelli', 'montesquieu',
    'voltaire', 'tocqueville', 'edmund burke', 'thomas jefferson', 'alexander hamilton',
    'carl schmitt', 'hans kelsen', 'hugo grotius', 'samuel huntington',
    'henry kissinger', 'zbigniew brzezinski', 'george kennan',
}

# Known professor name mappings for normalization
PROF_MAPPINGS = {
    'georges abi': 'Georges Abi-Saab',
    'georges abi-saab': 'Georges Abi-Saab',
    'abi-saab': 'Georges Abi-Saab',
    'hans genberg': 'Hans Genberg',
    'jacques freymond': 'Jacques Freymond',
    'philippe cahier': 'Philippe Cahier',
    'maurice bourquin': 'Maurice Bourquin',
    'miklos molnar': 'Miklos Molnar',
    'peter tschopp': 'Peter Tschopp',
    'jean pictet': 'Jean Pictet',
    'andré tunc': 'André Tunc',
    'paul guggenheim': 'Paul Guggenheim',
    'william rappard': 'William Rappard',
    'lubor jilek': 'Lubor Jilek',
    'victor monnier': 'Victor Monnier',
}


def is_valid_name(name):
    """Check if a string looks like a valid person name."""
    if not name or len(name) < 5:
        return False

    name_lower = name.lower()

    # Filter historical figures (commonly cited but not committee members)
    if name_lower in HISTORICAL_FIGURES:
        return False

    # Filter noise words
    for noise in NOISE_WORDS:
        if noise in name_lower:
            return False

    # Must have at least 2 parts (first + last name)
    parts = name.split()
    if len(parts) < 2:
        return False

    # Reject if more than 4 parts (likely a phrase, not a name)
    if len(parts) > 4:
        return False

    # Common stopwords that shouldn't be in names
    stopwords = {'de', 'la', 'le', 'les', 'du', 'des', 'un', 'une', 'et', 'the', 'of', 'and', 'in', 'on', 'to', 'for', 'a', 'an',
                 'would', 'could', 'should', 'will', 'can', 'may', 'might', 'must', 'shall',
                 'not', 'no', 'yes', 'but', 'or', 'if', 'then', 'so', 'as', 'is', 'are', 'was', 'were', 'be', 'been',
                 'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'he', 'she', 'his', 'her',
                 'who', 'what', 'which', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
                 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very', 'just', 'also'}

    # Each part should be mostly letters (allow hyphens, apostrophes)
    valid_parts = 0
    for part in parts:
        part_lower = part.lower()
        # Skip common particles in names (de, von, van, etc.)
        if part_lower in {'de', 'von', 'van', 'da', 'di', 'del', 'della', 'le', 'la', 'du'}:
            continue

        # Skip if it's a stopword
        if part_lower in stopwords:
            return False

        clean = part.replace('-', '').replace("'", '').replace("'", '')
        if not clean.isalpha():
            return False
        # Reject very short parts (single letters) unless it's an initial
        if len(clean) < 2:
            return False

        valid_parts += 1

    # Need at least 2 valid name parts
    return valid_parts >= 2


def normalize_name(name):
    """Normalize a person name to Title Case."""
    if not name:
        return None

    name = name.strip()
    name_lower = name.lower()

    # Check known mappings
    for key, normalized in PROF_MAPPINGS.items():
        if key in name_lower:
            return normalized

    # Convert to title case
    parts = name.split()
    normalized_parts = []
    for part in parts:
        # Handle hyphenated names (e.g., "abi-saab" -> "Abi-Saab")
        if '-' in part:
            subparts = part.split('-')
            normalized_parts.append('-'.join(sp.capitalize() for sp in subparts))
        else:
            normalized_parts.append(part.capitalize())

    return ' '.join(normalized_parts)


def extract_director_from_field(director_field):
    """Extract director name from the Directeur(s) field."""
    if not director_field or pd.isna(director_field):
        return None

    text = str(director_field)

    # Common patterns: "Directeur de thèse: Professeur X Y"
    patterns = [
        r'(?:directeur|director)[^:]*:\s*(?:professeur|professor|prof\.?|dr\.?)?\s*(.+)',
        r'(?:professeur|professor|prof\.?)\s+(.+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up trailing punctuation
            name = re.sub(r'[,;.]+$', '', name)
            return normalize_name(name)

    return None


def load_metadata_from_consolidated(csv_file, phd_only=True):
    """Load PhD metadata from consolidated CSV file.

    Args:
        csv_file: Path to consolidated_theses.csv
        phd_only: If True, only include PhD theses. If False, include all.
    """
    df = pd.read_csv(csv_file)

    phd_data = {}
    skipped = 0

    for _, row in df.iterrows():
        doc_id = row['doc_id']

        # Filter by thesis type
        if phd_only and row['thesis_type'] != 'PhD':
            skipped += 1
            continue

        author = row.get('author')
        if pd.isna(author):
            continue
        author = str(author).strip()

        director = row.get('director')
        if pd.notna(director):
            director = str(director).strip()
        else:
            director = None

        year = row.get('year')
        if pd.notna(year):
            year = int(year)
        else:
            year = None

        phd_data[doc_id] = {
            'author': author,
            'director': director,
            'year': year,
        }

    if phd_only:
        print(f"  Loaded {len(phd_data)} PhD records")
        print(f"  Skipped {skipped} non-PhD records")
    else:
        print(f"  Loaded {len(phd_data)} records")

    return phd_data


def load_metadata(excel_file, phd_only=True):
    """Load PhD metadata from Excel file (legacy function).

    Args:
        phd_only: If True, only include actual PhD theses (those with THESE in
                  Spécialisation or with a director listed). If False, include all.
    """
    df = pd.read_excel(excel_file)

    phd_data = {}
    skipped_non_phd = 0

    for _, row in df.iterrows():
        doc_id = str(row['Nom livrable']).replace('.txt', '')

        # Get author (PhD candidate)
        author = row.get('Auteur1')
        if pd.isna(author):
            continue
        author = str(author).strip()

        # Get director
        director_field = row.get('Directeur(s)')
        director = extract_director_from_field(director_field)

        # Filter to PhD theses only
        if phd_only:
            # Check if it's a PhD thesis:
            # 1. Has "THESE" in Spécialisation, OR
            # 2. Has a director listed
            spec = str(row.get('Spécialisation', '')).upper()
            is_phd = 'THESE' in spec or director is not None

            if not is_phd:
                skipped_non_phd += 1
                continue

        # Get year
        date_pub = row.get('Date de publication')
        year = None
        if pd.notna(date_pub):
            match = re.search(r'(19\d{2}|20\d{2})', str(date_pub))
            if match:
                year = int(match.group(1))

        phd_data[doc_id] = {
            'author': author,
            'director': director,
            'year': year,
            'raw_director': str(director_field) if pd.notna(director_field) else None
        }

    if phd_only:
        print(f"  Skipped {skipped_non_phd} non-PhD records (master theses, etc.)")

    return phd_data


def extract_jury_from_entities(entities_file, phd_data, n_words=1500):
    """Extract potential jury members from NER results."""
    jury_by_doc = defaultdict(list)

    with open(entities_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            doc = json.loads(line)
            doc_id = doc['doc_id']

            if doc_id not in phd_data:
                continue

            # Get PER/PERSON entities
            for per_type in ['PER', 'PERSON']:
                per_entities = doc.get('entities_by_type', {}).get(per_type, {})
                for name, count in per_entities.items():
                    if is_valid_name(name):
                        normalized = normalize_name(name)
                        if normalized:
                            jury_by_doc[doc_id].append(normalized)

    return jury_by_doc


def create_phd_director_network(phd_data, output_file):
    """Create network linking PhD candidates to their directors (keep all nodes)."""
    G = nx.Graph()

    director_counts = Counter()

    # First pass: count director occurrences
    for doc_id, data in phd_data.items():
        if data['director']:
            director_counts[data['director']] += 1

    # Add all nodes and edges
    for doc_id, data in phd_data.items():
        author = data['author']
        director = data['director']
        year = data['year']

        # Add PhD candidate node (always)
        if author not in G:
            G.add_node(author, node_type='phd_candidate', label=author)

        # Add director and edge if exists
        if director:
            if director not in G:
                G.add_node(director, node_type='director',
                          label=director,
                          supervised_count=director_counts[director])

            edge_attrs = {'doc_id': doc_id}
            if year:
                edge_attrs['year'] = year
            G.add_edge(author, director, **edge_attrs)

    # Write GEXF
    nx.write_gexf(G, output_file)

    n_phd = sum(1 for n, d in G.nodes(data=True) if d.get('node_type') == 'phd_candidate')
    n_dir = sum(1 for n, d in G.nodes(data=True) if d.get('node_type') == 'director')

    print(f"PhD-Director Network: {output_file}")
    print(f"  Nodes: {G.number_of_nodes()} ({n_phd} PhD candidates, {n_dir} directors)")
    print(f"  Edges: {G.number_of_edges()}")

    # Top directors
    top_dirs = director_counts.most_common(10)
    print("  Top directors:")
    for name, count in top_dirs:
        print(f"    {name}: {count}")

    return G


def create_phd_jury_network(phd_data, jury_by_doc, output_file, min_committee_count=2):
    """Create network linking PhD candidates to jury members.

    Args:
        min_committee_count: Minimum times a committee member must appear to be included.
                            PhD candidates are always included.
    """
    G = nx.Graph()

    # Count committee member occurrences
    committee_counts = Counter()
    for doc_id, jury_members in jury_by_doc.items():
        for member in set(jury_members):  # Deduplicate per doc
            committee_counts[member] += 1

    # Also count directors as committee members
    for doc_id, data in phd_data.items():
        if data['director']:
            committee_counts[data['director']] += 1

    # Filter committee members by count
    valid_committee = {name for name, count in committee_counts.items()
                       if count >= min_committee_count}

    # Add nodes and edges
    edges_added = 0
    for doc_id, data in phd_data.items():
        author = data['author']
        director = data['director']
        year = data['year']

        # Add PhD candidate node (always)
        if author not in G:
            G.add_node(author, node_type='phd_candidate', label=author)

        # Add director if valid
        if director and director in valid_committee:
            if director not in G:
                G.add_node(director, node_type='committee_member',
                          label=director,
                          appearances=committee_counts[director])
            edge_attrs = {'role': 'director'}
            if year:
                edge_attrs['year'] = year
            G.add_edge(author, director, **edge_attrs)
            edges_added += 1

        # Add jury members if valid
        jury_members = jury_by_doc.get(doc_id, [])
        for member in set(jury_members):
            if member in valid_committee and member != author:
                if member not in G:
                    G.add_node(member, node_type='committee_member',
                              label=member,
                              appearances=committee_counts[member])
                if not G.has_edge(author, member):
                    edge_attrs = {'role': 'jury'}
                    if year:
                        edge_attrs['year'] = year
                    G.add_edge(author, member, **edge_attrs)
                    edges_added += 1

    # Write GEXF
    nx.write_gexf(G, output_file)

    n_phd = sum(1 for n, d in G.nodes(data=True) if d.get('node_type') == 'phd_candidate')
    n_comm = sum(1 for n, d in G.nodes(data=True) if d.get('node_type') == 'committee_member')

    print(f"\nPhD-Jury Network: {output_file}")
    print(f"  Min committee appearances: {min_committee_count}")
    print(f"  Nodes: {G.number_of_nodes()} ({n_phd} PhD candidates, {n_comm} committee members)")
    print(f"  Edges: {G.number_of_edges()}")

    # Top committee members
    top_comm = [(name, committee_counts[name]) for name in valid_committee]
    top_comm.sort(key=lambda x: -x[1])
    print("  Top committee members:")
    for name, count in top_comm[:10]:
        print(f"    {name}: {count}")

    return G


def main():
    base_dir = '/Users/jpcointet/Desktop/iheid these'
    consolidated_file = os.path.join(base_dir, 'output/consolidated_theses.csv')
    entities_file = os.path.join(base_dir, 'entities_merged_20k.jsonl')
    output_dir = os.path.join(base_dir, 'output')

    os.makedirs(output_dir, exist_ok=True)

    print("Loading PhD metadata from consolidated dataset...")
    phd_data = load_metadata_from_consolidated(consolidated_file, phd_only=True)

    print("\nExtracting jury members from entities...")
    jury_by_doc = extract_jury_from_entities(entities_file, phd_data)
    print(f"  Found jury candidates in {len(jury_by_doc)} documents")

    # Create PhD-Director network (all nodes)
    print("\nCreating PhD-Director network...")
    create_phd_director_network(
        phd_data,
        os.path.join(output_dir, 'phd_director_network.gexf')
    )

    # Create PhD-Jury network (filter committee members appearing only once)
    print("\nCreating PhD-Jury network...")
    create_phd_jury_network(
        phd_data,
        jury_by_doc,
        os.path.join(output_dir, 'phd_jury_network_filtered.gexf'),
        min_committee_count=2  # Keep committee members appearing 2+ times
    )

    print("\nDone!")


if __name__ == '__main__':
    main()
