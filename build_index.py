import sys
import PyPDF2
import os
import re
import csv
from itertools import groupby
from operator import itemgetter

# List of relevant words to search for
relevant_words = [
    "abs", "all", "and", "any", "as", "ascii", "assert", "async", "await", 
    "bin", "bool", "break", "callable", "chr", "class", "compile", "complex", 
    "conf", "continue", "def", "del", "delattr", "delete", "dict", "dir", 
    "divmod", "DNS", "elif", "else", "enumerate", "Ether", "eval", "except", 
    "exec", "False", "findall", "function", "filter", "finally", "float", "for", "format", "from", 
    "frozenset", "get", "getattr", "global", "globals", "hasattr", "hash", 
    "head", "help", "hex", "HTTP", "ICMP", "id", "if", "import", "in", 
    "input", "int", "IP", "is", "isinstance", "issubclass", "iter", "lambda", 
    "len", "list", "locals", "ls", "lsc", "map", "match", "max", "memoryview", 
    "min", "next", "None", "nonlocal", "not", "object", "oct", "open", "or", 
    "ord", "options", "pass", "patch", "Pattern", "post", "pow", "print", 
    "property", "put", "raise", "RandIP", "RandMAC", "range", "Raw", "rdpcap", 
    "re.findall", "re.match", "re.search", ".*?", 
    "repr", "request", "Response", "return", "reversed", "round", "search", 
    "send", "sendp", "Session", "set", "setattr", "slice", "sniff", "sorted", 
    "split", "sr", "sr1", "srp", "srp1", "staticmethod", "str", "sub", "sum", 
    "super", "TCP", "Timeout", "TooManyRedirects", "True", "try", "tuple", 
    "type", "UDP", "vars", "while", "with", "wrpcap", "yield", "zip", 
    "DOTALL", "IGNORECASE", "MULTILINE", "VERBOSE", "UNICODE", "ConnectionError", 
    "Match", "RegexObject", "RequestException", "codes", "escape", "findall", 
    "finditer", "fullmatch", "purge", "status_codes", "subn"
]


def collapse_page_ranges(pages):
    """
    Collapse a sequence of page identifiers into a compact, human-readable
    string of page numbers and ranges.

    The input is normalized to unique, sorted integers, consecutive runs are
    collapsed into "start-end", and standalone pages are left as single
    numbers. The final output is a comma-separated list.

    Args:
        pages: Iterable of page identifiers. Each element can be an int or a
            string; if a string, the last whitespace-separated token is parsed
            as the page number (e.g., "Page 12" -> 12). Duplicates are removed.

    Returns:
        str: Comma-separated page numbers and ranges (e.g., "1-3, 5, 7-9").

    Examples:
        >>> collapse_page_ranges(["1", "2", "3", "5", "7", "8", "9"])
        '1-3, 5, 7-9'
        >>> collapse_page_ranges(["Page 10", "9", "11", "10", "12"])
        '9-12'
    """
    page_numbers = sorted(set(int(page.split()[-1]) for page in pages))
    ranges = []
    for k, g in groupby(enumerate(page_numbers), lambda ix: ix[0] - ix[1]):
        group = list(map(itemgetter(1), g))
        if len(group) > 1:
            ranges.append(f"{group[0]}-{group[-1]}")
        else:
            ranges.append(str(group[0]))
    return ', '.join(ranges)

def extract_words_from_directory(directory_path, password):
    """
    Extract occurrences of predefined relevant words from all PDF files in a directory.

    This function scans all .pdf files in the given directory, attempts to decrypt
    encrypted PDFs using the provided password, extracts text from each page using
    PyPDF2, tokenizes the text with a simple "\\w+" regex, normalizes tokens by
    stripping common punctuation and lowercasing, and records page references for
    tokens that appear in the global `relevant_words` list.
    Args:
        directory_path (str): Path to the directory containing PDF files.
        password (str): Password used to decrypt encrypted PDFs. If decryption
            fails for a file, that file is skipped.

    Returns:
        dict[str, list[str]]: A mapping of normalized relevant words to lists of
        unique page references in the form "filename:Page N" indicating where the
        word was found.

    Side Effects:
        - Prints progress messages (e.g., "Processing: <filename>") and error
          messages for decryption or processing failures.
        - Prints a message if the directory is not found.

    Notes:
        - Multiple occurrences of the same word on the same page are deduplicated.
        - Only exact matches to normalized tokens present in `relevant_words` are
          recorded.
    """
    word_pages = {}
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(directory_path, filename)
                print(f"Processing: {filename}")
                try:
                    with open(pdf_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        if pdf_reader.is_encrypted:
                            if not pdf_reader.decrypt(password):
                                print(f"Incorrect password for {filename}!")
                                continue
                        for page_num, page in enumerate(pdf_reader.pages, start=1):
                            text = page.extract_text()
                            if text:
                                words = re.findall(r"\w+", text)
                                for word in words:
                                    cleaned_word = word.strip('''.,!?()[]{}":;'|*&^!@#$%(\)''').lower()
                                    if cleaned_word in relevant_words:
                                        entry = f"{filename}:Page {page_num}"
                                        if cleaned_word in word_pages:
                                            if entry not in word_pages[cleaned_word]:
                                                word_pages[cleaned_word].append(entry)
                                        else:
                                            word_pages[cleaned_word] = [entry]
                except Exception as e:
                    print(f"Error processing {filename}: {str(e)}")
                    continue
    except FileNotFoundError:
        print("Directory not found!")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return word_pages

def write_index_to_csv(word_pages, output_file):
    """
    Write a CSV index summarizing where relevant words appear across PDF files.

    This function expects a mapping from words to page reference strings in the
    form "<filename>:Page N". For each word, it:
      - Extracts a file prefix matching r"(SEC573_\\d+)" from each reference.
      - Extracts the page number using r"Page (\\d+)" from the reference.
      - Groups page numbers by the extracted file prefix.
      - Collapses consecutive page numbers into compact ranges using
        collapse_page_ranges.
      - Writes a single CSV row with the word and a human-readable summary of
        occurrences (e.g., "SEC573_001 Pages 3-5, 7").

    Args:
        word_pages (dict[str, list[str]]): Mapping of words to a list of page
            reference strings formatted like "<filename>:Page N". Only references
            whose filename portion begins with a prefix matching r"(SEC573_\\d+)"
            are included.
        output_file (str): Path to the output CSV file. The file is created or
            overwritten using UTF-8 encoding.

    Returns:
        None

    Side Effects:
        - Creates or overwrites the CSV at output_file.
        - Writes a header row: ["Word", "Occurrences"].
        - Skips any page references that do not match the expected patterns.
    """
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Word', 'Occurrences'])
        for word, pages in word_pages.items():
            pages_by_file = {}
            for page in pages:
                match = re.match(r"(SEC573_\d+)", page)
                pagenum = re.search(r"Page (\d+)", page).group(1)
                if match:
                    file_prefix = match.group(1)
                    if file_prefix not in pages_by_file:
                        pages_by_file[file_prefix] = []
                    pages_by_file[file_prefix].append(pagenum)
            occurrences = []
            for file_prefix, file_pages in pages_by_file.items():
                page_range = collapse_page_ranges(file_pages)
                occurrences.append(f"{file_prefix} Pages {page_range}")
            writer.writerow([word, ', '.join(occurrences)])

if len(sys.argv) <= 2:
    print("Usage: python build_index.py <directory_path> <output_csv_file>")
else:
    directory_path = sys.argv[1]
    output_csv = sys.argv[2]
    password = input("What is your pdf password? ")
    word_pages = extract_words_from_directory(directory_path, password)
    write_index_to_csv(word_pages, output_csv)
    print(f"Index written to {output_csv}")