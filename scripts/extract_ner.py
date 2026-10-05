#!/usr/bin/env python3
"""
Fast Named Entity Recognition (NER) extraction from thesis text files.
Extracts entities from the first N pages only for speed.

Uses spaCy with small models for fast processing.
Supports English and French (auto-detected).

Usage:
    python extract_ner.py <input_dir> <output_file> [--pages 20] [--workers 4]

Example:
    python extract_ner.py ALTO_text/ entities.jsonl --pages 20 --workers 8
"""

import os
import sys
import json
import re
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Lazy load spaCy to avoid import overhead in workers
nlp_en = None
nlp_fr = None
nlp_de = None


def load_models():
    """Load spaCy models (called once per worker process)."""
    global nlp_en, nlp_fr, nlp_de
    import spacy

    if nlp_en is None:
        # Use small models for speed
        nlp_en = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        nlp_en.max_length = 2000000  # Increase limit

    if nlp_fr is None:
        nlp_fr = spacy.load("fr_core_news_sm", disable=["parser", "lemmatizer"])
        nlp_fr.max_length = 2000000

    if nlp_de is None:
        nlp_de = spacy.load("de_core_news_sm", disable=["parser", "lemmatizer"])
        nlp_de.max_length = 2000000


def detect_language(text):
    """Simple language detection based on common words."""
    text_lower = text.lower()

    # Count French, English, German indicators
    fr_words = ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'en', 'un', 'une', 'est', 'sont', 'dans', 'pour', 'que', 'qui']
    en_words = ['the', 'of', 'and', 'to', 'in', 'is', 'for', 'that', 'with', 'as', 'was', 'are', 'be', 'this', 'by']
    de_words = ['der', 'die', 'das', 'und', 'ist', 'von', 'mit', 'für', 'auf', 'den', 'dem', 'ein', 'eine', 'auch', 'sich', 'nicht']

    words = set(re.findall(r'\b\w+\b', text_lower))

    fr_count = sum(1 for w in fr_words if w in words)
    en_count = sum(1 for w in en_words if w in words)
    de_count = sum(1 for w in de_words if w in words)

    max_count = max(fr_count, en_count, de_count)

    if max_count == de_count and de_count > 0:
        return 'de'
    elif max_count == fr_count and fr_count > 0:
        return 'fr'
    else:
        return 'en'


def extract_first_n_pages(text, n_pages=20):
    """Extract text from the first N pages."""
    # Split by page markers
    pages = re.split(r'--- Page \d+ ---', text)

    # Take first n_pages (skip empty first element if present)
    pages = [p.strip() for p in pages if p.strip()][:n_pages]

    return '\n\n'.join(pages)


def extract_word_range(text, start=0, n_words=10000):
    """Extract N words from text starting at word position 'start'."""
    # Remove page markers first
    text = re.sub(r'--- Page \d+ ---', '', text)

    words = text.split()
    return ' '.join(words[start:start + n_words])


def extract_entities(text, lang='en'):
    """Extract named entities using spaCy."""
    load_models()

    if lang == 'fr':
        nlp = nlp_fr
    elif lang == 'de':
        nlp = nlp_de
    else:
        nlp = nlp_en

    # Process text in chunks if too long
    max_chunk = 100000
    entities = []

    for i in range(0, len(text), max_chunk):
        chunk = text[i:i + max_chunk]
        doc = nlp(chunk)

        for ent in doc.ents:
            entities.append({
                'text': ent.text.strip(),
                'label': ent.label_,
                'start': ent.start_char + i,
                'end': ent.end_char + i
            })

    return entities


def process_document(doc_path, start_word=0, n_words=10000):
    """
    Process a single document and extract entities.

    Returns:
        Tuple of (doc_name, success, result_dict, error_message)
    """
    try:
        doc_name = os.path.basename(doc_path).replace('.txt', '')

        with open(doc_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

        # Extract word range
        text = extract_word_range(full_text, start_word, n_words)

        if not text.strip():
            return (doc_name, False, None, f"No text in word range {start_word}-{start_word+n_words}")

        # Detect language
        lang = detect_language(text)

        # Extract entities
        entities = extract_entities(text, lang)

        # Aggregate entity counts by type
        entity_counts = {}
        for ent in entities:
            label = ent['label']
            text_norm = ent['text'].lower().strip()

            if label not in entity_counts:
                entity_counts[label] = Counter()
            entity_counts[label][text_norm] += 1

        # Convert to serializable format
        result = {
            'doc_id': doc_name,
            'language': lang,
            'word_range': f"{start_word}-{start_word + n_words}",
            'words_processed': len(text.split()),
            'total_entities': len(entities),
            'entities_by_type': {
                label: dict(counter.most_common(50))  # Top 50 per type
                for label, counter in entity_counts.items()
            }
        }

        return (doc_name, True, result, None)

    except Exception as e:
        return (os.path.basename(doc_path), False, None, str(e))


def main():
    parser = argparse.ArgumentParser(
        description='Fast NER extraction from thesis text files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('input_dir', help='Input directory containing .txt files')
    parser.add_argument('output_file', help='Output JSONL file for entities')
    parser.add_argument('--words', '-p', type=int, default=10000,
                        help='Number of words to process per document (default: 10000)')
    parser.add_argument('--start', '-s', type=int, default=0,
                        help='Starting word position (default: 0)')
    parser.add_argument('--workers', '-w', type=int, default=4,
                        help='Number of parallel workers (default: 4)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Limit number of documents to process (for testing)')

    args = parser.parse_args()

    input_dir = args.input_dir
    output_file = args.output_file

    # Get list of text files
    txt_files = sorted([
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith('.txt')
    ])

    if args.limit:
        txt_files = txt_files[:args.limit]

    total = len(txt_files)
    print(f"Processing {total} documents...")
    print(f"Word range: {args.start} to {args.start + args.words}")
    print(f"Workers: {args.workers}")
    print("-" * 50)

    success_count = 0
    error_count = 0

    # Process documents in parallel
    with open(output_file, 'w', encoding='utf-8') as out_f:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(process_document, doc_path, args.start, args.words): doc_path
                for doc_path in txt_files
            }

            for i, future in enumerate(as_completed(futures)):
                doc_name, success, result, error = future.result()

                if success:
                    success_count += 1
                    out_f.write(json.dumps(result, ensure_ascii=False) + '\n')
                else:
                    error_count += 1
                    print(f"Error: {doc_name} - {error}", file=sys.stderr)

                # Progress update every 100 documents
                if (i + 1) % 100 == 0:
                    print(f"Progress: {i+1}/{total} ({(i+1)*100//total}%)")

    print("-" * 50)
    print(f"Completed!")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Output: {output_file}")

    # Show output size
    output_size = os.path.getsize(output_file)
    print(f"  Output size: {output_size / 1024 / 1024:.2f} MB")


if __name__ == '__main__':
    main()
