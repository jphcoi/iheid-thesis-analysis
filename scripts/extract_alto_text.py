#!/usr/bin/env python3
"""
Extract plain text from ALTO XML files.

ALTO (Analyzed Layout and Text Object) is an XML format for OCR output.
Text content is stored in <String CONTENT="..."/> elements within TextLine and TextBlock structures.

Usage:
    python extract_alto_text.py <input_dir> <output_dir>

Example:
    python extract_alto_text.py ALTO_theses/ ALTO_text/
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse

# ALTO namespace
ALTO_NS = {'alto': 'http://www.loc.gov/standards/alto/ns-v2#'}


def extract_text_from_alto(alto_path):
    """
    Extract plain text from a single ALTO XML file.

    Args:
        alto_path: Path to the ALTO XML file

    Returns:
        Extracted text as a string
    """
    try:
        tree = ET.parse(alto_path)
        root = tree.getroot()

        # Handle namespace
        ns = ALTO_NS

        # Find all String elements and extract CONTENT attribute
        # We traverse TextBlock -> TextLine -> String to maintain reading order
        text_parts = []

        # Try with namespace first
        text_blocks = root.findall('.//alto:TextBlock', ns)

        # If no results, try without namespace (some files might not use it)
        if not text_blocks:
            text_blocks = root.findall('.//{http://www.loc.gov/standards/alto/ns-v2#}TextBlock')

        if not text_blocks:
            # Fallback: try to find any element with CONTENT attribute
            for elem in root.iter():
                content = elem.get('CONTENT')
                if content:
                    text_parts.append(content)
            return ' '.join(text_parts)

        for block in text_blocks:
            block_lines = []

            # Find TextLines within this block
            text_lines = block.findall('.//alto:TextLine', ns)
            if not text_lines:
                text_lines = block.findall('.//{http://www.loc.gov/standards/alto/ns-v2#}TextLine')

            for line in text_lines:
                line_words = []

                # Find String elements (words) within this line
                strings = line.findall('.//alto:String', ns)
                if not strings:
                    strings = line.findall('.//{http://www.loc.gov/standards/alto/ns-v2#}String')

                for string in strings:
                    content = string.get('CONTENT', '')
                    if content:
                        # Decode XML entities
                        content = content.replace('&quot;', '"').replace('&apos;', "'")
                        content = content.replace('&lt;', '<').replace('&gt;', '>')
                        content = content.replace('&amp;', '&')
                        line_words.append(content)

                if line_words:
                    block_lines.append(' '.join(line_words))

            if block_lines:
                text_parts.append('\n'.join(block_lines))

        # Join blocks with double newline (paragraph break)
        return '\n\n'.join(text_parts)

    except ET.ParseError as e:
        print(f"XML parse error in {alto_path}: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Error processing {alto_path}: {e}", file=sys.stderr)
        return ""


def process_document(doc_folder, input_base, output_base, skip_existing=True):
    """
    Process all ALTO files for a single document and create a combined text file.

    Args:
        doc_folder: Name of the document folder (e.g., "HEIA_059736_411209")
        input_base: Base input directory containing document folders
        output_base: Base output directory for text files
        skip_existing: If True, skip documents that already have output files

    Returns:
        Tuple of (doc_folder, success, num_pages, error_message, skipped)
    """
    try:
        # Check if output already exists
        output_path = os.path.join(output_base, f"{doc_folder}.txt")
        if skip_existing and os.path.exists(output_path):
            return (doc_folder, True, 0, None, True)  # Skipped

        alto_dir = os.path.join(input_base, doc_folder, "ALTO")

        if not os.path.exists(alto_dir):
            return (doc_folder, False, 0, "ALTO directory not found", False)

        # Get all XML files sorted by name (to maintain page order)
        xml_files = sorted([f for f in os.listdir(alto_dir) if f.endswith('.xml')])

        if not xml_files:
            return (doc_folder, False, 0, "No XML files found", False)

        # Extract text from each page
        all_text = []
        for xml_file in xml_files:
            xml_path = os.path.join(alto_dir, xml_file)
            page_text = extract_text_from_alto(xml_path)
            if page_text:
                # Add page separator
                page_num = xml_file.split('_')[-1].replace('.xml', '')
                all_text.append(f"--- Page {page_num} ---\n{page_text}")

        # Combine all pages
        combined_text = '\n\n'.join(all_text)

        # Write output file
        output_path = os.path.join(output_base, f"{doc_folder}.txt")
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(combined_text)

        return (doc_folder, True, len(xml_files), None, False)

    except Exception as e:
        return (doc_folder, False, 0, str(e), False)


def main():
    parser = argparse.ArgumentParser(
        description='Extract plain text from ALTO XML files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('input_dir', help='Input directory containing document folders with ALTO subfolders')
    parser.add_argument('output_dir', help='Output directory for text files')
    parser.add_argument('--workers', '-w', type=int, default=4, help='Number of parallel workers (default: 4)')
    parser.add_argument('--limit', '-l', type=int, default=None, help='Limit number of documents to process (for testing)')
    parser.add_argument('--no-skip', action='store_true', help='Re-process documents even if output exists')

    args = parser.parse_args()

    input_base = args.input_dir
    output_base = args.output_dir

    # Create output directory
    os.makedirs(output_base, exist_ok=True)

    # Get list of document folders
    doc_folders = [f for f in os.listdir(input_base)
                   if os.path.isdir(os.path.join(input_base, f))]

    if args.limit:
        doc_folders = doc_folders[:args.limit]

    skip_existing = not args.no_skip

    total = len(doc_folders)
    print(f"Processing {total} documents...")
    print(f"Input: {input_base}")
    print(f"Output: {output_base}")
    print(f"Workers: {args.workers}")
    print(f"Skip existing: {skip_existing}")
    print("-" * 50)

    success_count = 0
    error_count = 0
    skipped_count = 0
    total_pages = 0

    # Process documents in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_document, doc, input_base, output_base, skip_existing): doc
            for doc in doc_folders
        }

        for i, future in enumerate(as_completed(futures)):
            doc_folder, success, num_pages, error, skipped = future.result()

            if skipped:
                skipped_count += 1
            elif success:
                success_count += 1
                total_pages += num_pages
            else:
                error_count += 1
                print(f"Error: {doc_folder} - {error}", file=sys.stderr)

            # Progress update every 100 documents
            if (i + 1) % 100 == 0:
                print(f"Progress: {i+1}/{total} ({(i+1)*100//total}%) - {success_count} new, {skipped_count} skipped")

    print("-" * 50)
    print(f"Completed!")
    print(f"  New: {success_count}")
    print(f"  Skipped (existing): {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total pages processed: {total_pages}")

    # Calculate output size
    total_size = sum(
        os.path.getsize(os.path.join(output_base, f))
        for f in os.listdir(output_base) if f.endswith('.txt')
    )
    print(f"  Output size: {total_size / 1024 / 1024:.2f} MB")


if __name__ == '__main__':
    main()
