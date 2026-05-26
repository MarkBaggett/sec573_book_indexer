"""Build a cross-reference index of curated terms found in a directory of PDFs.

The script supports three matching modes per entry:

    * Plain word        - "hashlib"          - case-insensitive whole-word match
    * Phrase            - "big endian"       - flexible phrase match that
                                               tolerates PDF extraction quirks
                                               (line breaks, hyphens, NBSP, ...)
    * Regex pattern     - "re:if\\s\\w+:"     - any regex, matched case-
                                               insensitively with re.DOTALL

The output CSV has one row per matched term, with all page references
grouped per source book.  Source files are labeled as follows:

    * "Workbook"  -> "WB"
    * "Book <N>"  -> "B<N>"   (e.g., "SEC573 - Book 1_..." -> "B1")

Within each "Occurrences" cell, each book appears on its own line:

    B1: 38, 93
    B2: 46, 70, 88
    B3: 14, 19, 27
"""

import csv
import os
import re
import sys
from itertools import groupby
from operator import itemgetter

import PyPDF2


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# Regex entries are flagged with this prefix in RELEVANT_TERMS so the
# classifier can distinguish them from plain words / phrases.
REGEX_PREFIX = "re:"

# "Workbook" is checked first because the string "Workbook" also contains
# "Book", which would otherwise win the BOOK_RE match below.
WORKBOOK_RE = re.compile(r"Workbook", re.IGNORECASE)
BOOK_RE = re.compile(r"Book[\s_-]*(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# RELEVANT_TERMS - the curated list scanned across every PDF.
#
# Three entry types:
#   "word"              -> whole-word match (case-insensitive)
#   "two or more words" -> phrase match (case-insensitive, hyphen/whitespace
#                          tolerant - see compile_term())
#   "re:<pattern>"      -> regex match (case-insensitive, DOTALL)
#
# Regex examples:
#   "re:if\\s+\\w+(\\s+\\w+)*\\s*:"   -> if-statement headers
#   "re:0x[0-9a-fA-F]+"               -> hex literals
#   "re:\\b\\d+\\.\\d+\\.\\d+\\.\\d+\\b"   -> IPv4-looking strings
# ---------------------------------------------------------------------------
RELEVANT_TERMS = {
    # A
    "abs", "accept", "add", "af_inet", "af_inet6", "agent context",
    "agents", "append", "append mode", "ascii", "async",
    "async function", "asyncio", "auth", "await",

    # B
    "base", "bearer", "big endian", "bin", "binary file", "binary mode",
    "bind", "bitwise", "blocking", "bodmas", "bool", "bpf", "break",
    "byte", "byte order", "byte string", "bytearray", "bytes",

    # C
    "callable", "capture group", "casting", "character",
    "chat completion", "chat completions", "chr", "class", "close",
    "codecs", "codes", "collections", "command injection", "command line",
    "command line argument", "comments", "communicate", "compile", "complex",
    "comprehension", "conf", "connect", "context", "context manager",
    "context window", "continue", "control", "cookie jar", "cookies",
    "copy", "count", "counter", "cpython", "curl", "cwd", "cython",

    # D
    "decimal", "decode", "decompress", "decorator", "deepcopy",
    "default value", "defaultdict", "del", "delattr", "delete", "delimiters",
    "dict", "difference", "difference_update", "dir", "dns", "docstring",
    "dotall", "dump", "dumps", "dunder",

    # E
    "encode", "encoding", "end", "endian", "enumerate", "escape", "ether",
    "event loop", "except", "exception", "exec", "executable", "exists",
    "exit code", "extend",

    # F
    "f string", "false", "fastmcp", "file", "file handle", "file pointer",
    "filter", "finally", "find", "findall", "float", "format",
    "format specifier", "format string", "freq", "freqcounter", "fstring",
    "function",

    # G
    "geoip2", "get", "gethostbyaddr", "gethostbyname", "getsize", "getsizeof",
    "global", "globals", "globbing", "group", "groupdict", "guardrail",
    "guardrails", "gzip",

    # H
    "hash", "hashlib", "head", "help", "hex", "hive", "home", "html",
    "http", "http headers",

    # I
    "icmp", "id", "ide", "ignorecase", "index", "input", "input guardrail",
    "insert", "instance", "int", "intersection", "ioctl", "ip", "isdisjoint",
    "islower", "issubset", "issuperset", "items", "iter", "iterator",
    "iterfind", "itertools",

    # J
    "jq", "join", "json",

    # K
    "keyword argument", "keys", "keywords", "kwargs",

    # L
    "langchain", "large language model", "layer", "legb", "len", "list",
    "list comprehension", "listen", "litellm", "literals", "little endian",
    "llm", "load", "loads", "log", "logging",  "lower", "ls",

    # M
    "mac", "machine learning", "magic", "map", "match", "max", "maxmind",
    "mcp", "min", "model", "module", "most_common", "multiline", "mypy",

    # N
    "n8n", "named group", "namespaces", "next", "nmap", "non greedy", "none",
    "nonlocal", "ntohs",

    # O
    "object", "ollama", "open", "openai", "openai api", "operator",
    "operators", "options", "ord", "os", "output", "output guardrail", "owasp",

    # P
    "packet", "packetlist", "packing", "parser", "patch", "path", "pathlib",
    "pattern", "pcap", "pcapreader", "pdb", "pemdas", "pep", "physical drive",
    "pip", "pkt", "pop", "popen", "port", "post", "print", "probability",
    "promiscuous mode", "prompt", "prompt injection", "property", "protocol",
    "proxy", "put", "pydantic", "pyinstaller", "python",

    # Q
    "quote",

    # R
    "rag", "range", "raw", "raw socket", "raw string", "re", "read", "read mode",
    "readlines", "recursive", "recv", "recvall", "recvfrom", "regex", "regfhive",
    "regular expression", "regular expressions", "remove", "replace",
    "reputation", "request", "requests", "response", "retrieval augmented",
    "return", "return value", "reverse", "reversed", "rfc", "rglob", "round",
    "run", "run_until_complete", "runner",

    # S
    "salt", "scaffolding", "scapy", "search", "seek", "select", "send",
    "sendall", "session", "session cookie", "session cookies", "sessions",
    "set cookie", "set_event_loop", "setblocking", "setdefault", "sha1",
    "sha256", "shebang", "slice", "slicing", "sniff", "sock_dgram",
    "sock_stream", "socket", "sorted", "split", "splitlines", "sql",
    "sql injection", "ssl", "standard input", "standard output", "start",
    "stat", "stderr", "stdin", "stdout", "str", "string", "strings", "struct",
    "sub", "subkey", "subprocess", "sum", "super", "supergateway",
    "supply chain", "symmetric_difference", "sys", "system prompt",

    # T
    "tail", "tally_str", "tcp", "tcpdump", "tell", "temperature", "text mode",
    "third party", "thread", "threading", "timeout", "title", "tls", "token",
    "tokens", "tool call", "tool_choice", "traceback", "tracker", "transports",
    "true", "tshark", "ttl", "tuple", "type", "type hint", "type hints",
    "typeerror",

    # U
    "udp", "unescape", "unicode", "union", "unpack", "unpacking", "update",
    "upper", "url", "urlencode", "urllib", "urlopen", "user agent",
    "user prompt", "utc",

    # V
    "validation", "value", "values", "variables", "vector", "venv", "verbose",
    "verify", "vibe", "virtual",

    # W
    "walk", "wireshark", "wrpcap", "write", "write mode",
    "writelines",

    # X-Z
    "xor", "yaml", "zip", "zlib",

    # --- Regex patterns (kept together at the end so they're easy to
    #     find when tuning; the classifier handles them by prefix anyway) ---
    r"re:\bif\s+\w+.*?:",                    # if-statement headers
    r"re:\belif\s+.*?:",                     # elif headers
    r"re:\belse\s*:",                        # else: blocks
    r"re:\bfor\s+\w+\s+in\s+",               # for-loops
    r"re:\bwhile\s+.*?:",                    # while-loops
    r"re:\btry\s*:",                         # try: blocks
    r"re:\bexcept\b.*?:",                    # except: blocks
    r"re:\bwith\s+.*?\bas\s+\w+\s*:",        # with ... as ...:
    r"re:\bdef\s+\w+\s*\(",                  # def function declarations
    r"re:\bclass\s+\w+",                     # class declarations
    r"re:\blambda\s+\w+",                    # lambda expressions
    r"re:\bimport\s+\w+",                    # import statements
    r"re:\bfrom\s+\w+\s+import",             # from X import Y
    r"re:\breturn\b",                        # return statements
    r"re:\braise\s+\w+",                     # raise SomeException
    r"re:\bassert\b",                        # assert statements
    r"re:\byield\b",                         # yield statements
    r"re:big[\s\-]*endian",                  # also matches "bigendian"
}


# ---------------------------------------------------------------------------
# FILENAME -> BOOK LABEL
# ---------------------------------------------------------------------------

def filename_to_book_label(filename):
    """Return a short label ("WB", "B1", ...) for a given PDF filename.

    A filename containing "Workbook" beats a filename containing "Book"
    because the latter substring is contained in the former.  When neither
    pattern matches, the filename's stem is returned as-is.
    """
    stem = os.path.splitext(filename)[0]

    # Workbook detection is intentionally disabled while the user works
    # without that distinction.  Re-enable by uncommenting WORKBOOK_RE
    # at the top of the module and the block below.
    #
    # if WORKBOOK_RE.search(stem):
    #     return "WB"

    match = BOOK_RE.search(stem)
    if match:
        return f"B{int(match.group(1))}"

    return stem


# ---------------------------------------------------------------------------
# PAGE-NUMBER COMPACTION
# ---------------------------------------------------------------------------

def collapse_page_ranges(pages):
    """Compact a list of page numbers into a "1-3, 5, 7-9"-style string.

    Consecutive integers are grouped into runs; non-consecutive ones stay
    standalone.  Input may contain duplicates or strings; both are coerced
    to ints and deduplicated before processing.
    """
    page_numbers = sorted(
        {int(str(page).split()[-1]) for page in pages}
    )

    ranges = []
    # itertools.groupby trick: each consecutive run has a constant
    # difference between index-in-list and value (ix[0] - ix[1]).
    for _, run in groupby(enumerate(page_numbers),
                          lambda ix: ix[0] - ix[1]):
        group = list(map(itemgetter(1), run))
        if len(group) > 1:
            ranges.append(f"{group[0]}-{group[-1]}")
        else:
            ranges.append(str(group[0]))

    return ", ".join(ranges)


def book_sort_key(label):
    """Sort key that puts B1,B9,B10 first, then WB, then anything else.

    The returned tuple is sorted lexicographically by Python's default
    comparison; the leading int (0/1/2) controls the major group.
    """
    match = re.fullmatch(r"B(\d+)", label)
    if match:
        return (0, int(match.group(1)))
    if label == "WB":
        return (1, 0)
    return (2, label)


# ---------------------------------------------------------------------------
# TERM CLASSIFICATION & COMPILATION
# ---------------------------------------------------------------------------

def classify_term(term):
    """Classify a term as 'regex', 'phrase', or 'word'.

    The leading "re:" prefix denotes a regex pattern (and is stripped from
    the value returned).  Any whitespace in the term denotes a phrase.
    Everything else is treated as a single word.
    """
    if term.startswith(REGEX_PREFIX):
        return ("regex", term[len(REGEX_PREFIX):])
    if " " in term:
        return ("phrase", term)
    return ("word", term)


def compile_term(term):
    """Pre-compile a term into the form needed by its matcher.

    Returns a (kind, payload) tuple where payload is:

      * word:    a lowercased string used for set-intersection matching
      * phrase:  a compiled regex tolerant of PDF extraction quirks
                 (line breaks, multi-space, tabs, NBSP, hyphens between
                 words)
      * regex:   the user-supplied compiled regex
      * invalid: payload is None; logged with a warning at compile time
    """
    kind, value = classify_term(term)

    if kind == "word":
        return ("word", value.lower())

    if kind == "phrase":
        # Between every pair of words allow one-or-more whitespace OR
        # hyphen characters.  \b on the outside enforces word boundaries
        # so "big endian" never matches inside "bigendianness".
        words = value.split()
        pattern = (
            r"\b"
            + r"[\s\-]+".join(re.escape(w) for w in words)
            + r"\b"
        )
        try:
            compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            print(f"  WARNING: phrase compile failed for "
                  f"{value!r}: {exc}")
            return ("invalid", None)
        return ("phrase", compiled)

    if kind == "regex":
        try:
            compiled = re.compile(value, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            print(f"  WARNING: invalid regex {value!r} - skipping ({exc})")
            return ("invalid", None)
        return ("regex", compiled)

    return ("invalid", None)


# ---------------------------------------------------------------------------
# PDF SCANNING
# ---------------------------------------------------------------------------

def extract_words_from_directory(directory_path, password):
    """Walk a directory of PDFs and collect page references per term.

    Returns a dict: ``{term: ["file.pdf:Page N", ...]}``.  Each PDF page
    is scanned three ways: token-set intersection for plain words,
    flexible regex for phrases, and full regex for "re:" entries.
    """
    term_pages = {}

    if not os.path.isdir(directory_path):
        print(f"Directory not found: {directory_path}")
        return term_pages

    # Pre-compile every term once so the per-page hot loop is fast.
    compiled_terms = {
        term: compile_term(term) for term in RELEVANT_TERMS
    }

    # Partition by kind for efficient scanning.
    word_terms = {
        term: payload
        for term, (kind, payload) in compiled_terms.items()
        if kind == "word"
    }
    phrase_terms = {
        term: payload
        for term, (kind, payload) in compiled_terms.items()
        if kind == "phrase"
    }
    regex_terms = {
        term: payload
        for term, (kind, payload) in compiled_terms.items()
        if kind == "regex"
    }

    print(
        f"Loaded {len(word_terms)} word terms, "
        f"{len(phrase_terms)} phrase terms, "
        f"{len(regex_terms)} regex terms.\n"
    )

    # The set is used for fast page-tokens vs vocabulary intersection.
    word_term_set = set(word_terms.values())

    for filename in sorted(os.listdir(directory_path)):
        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(directory_path, filename)
        print(f"Processing: {filename}")

        try:
            with open(pdf_path, "rb") as fh:
                reader = PyPDF2.PdfReader(fh)

                # Decrypt if needed.  An incorrect password makes the
                # rest of the file unreadable so we skip the file.
                if reader.is_encrypted and not reader.decrypt(password):
                    print(f"Incorrect password for {filename} - "
                          f"skipping")
                    continue

                for page_num, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue

                    matched_terms = set()

                    # 1. Single-word matching via tokenization (fast).
                    #    Build a set of lowercased \w+ tokens from the
                    #    page, then intersect with the word vocabulary.
                    page_tokens = {
                        token.lower()
                        for token in re.findall(r"\w+", text)
                    }
                    word_hits = page_tokens & word_term_set
                    for term, lowered in word_terms.items():
                        if lowered in word_hits:
                            matched_terms.add(term)

                    # 2. Phrase matching via the flexible regexes built
                    #    by compile_term() - tolerates whitespace,
                    #    hyphens, line breaks, NBSPs, etc., between
                    #    phrase words.
                    for term, compiled in phrase_terms.items():
                        if compiled.search(text):
                            matched_terms.add(term)

                    # 3. User-supplied regex patterns ("re:..." entries).
                    for term, compiled in regex_terms.items():
                        if compiled.search(text):
                            matched_terms.add(term)

                    # Record this page for every matched term.
                    entry = f"{filename}:Page {page_num}"
                    for term in matched_terms:
                        term_pages.setdefault(term, [])
                        if entry not in term_pages[term]:
                            term_pages[term].append(entry)

        except Exception as exc:
            # Log the failure and continue - one bad PDF shouldn't kill
            # the whole run.
            print(f"Error processing {filename}: {exc}")
            continue

    return term_pages


# ---------------------------------------------------------------------------
# CSV OUTPUT
# ---------------------------------------------------------------------------

def display_label(term):
    """Return the label used for ``term`` in the CSV's first column.

    The "re:" prefix is intentionally preserved on regex entries so the
    reader can distinguish pattern rows from literal rows at a glance.
    """
    if term.startswith(REGEX_PREFIX):
        return term
    return term


def write_index_to_csv(term_pages, output_file):
    """Write the term-to-pages map to a two-column CSV file.

    Each row's "Occurrences" cell contains one "BookLabel: pages" line per
    book, joined by newlines so the spreadsheet renders one book per row.
    """
    with open(output_file,
              mode="w",
              newline="",
              encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Term", "Occurrences"])

        for term in sorted(term_pages):
            # Group "filename.pdf:Page N" entries by their book label.
            pages_by_book = {}
            for ref in term_pages[term]:
                if ":Page " not in ref:
                    continue
                filename_part, page_part = ref.rsplit(":Page ", 1)
                book_label = filename_to_book_label(filename_part)
                pages_by_book.setdefault(book_label, []).append(page_part)

            # Render each book's pages as a compacted range string.
            occurrences = [
                f"{label}: {collapse_page_ranges(pages_by_book[label])}"
                for label in sorted(pages_by_book, key=book_sort_key)
            ]

            writer.writerow(
                [display_label(term), "\n".join(occurrences)]
            )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    """Parse CLI args, run extraction, write CSV."""
    if len(sys.argv) <= 2:
        print("Usage: python build_index.py "
              "<directory_path> <output_csv_file>")
        return

    directory_path = sys.argv[1]
    output_csv = sys.argv[2]
    password = input("What is your pdf password? ")

    term_pages = extract_words_from_directory(directory_path, password)
    write_index_to_csv(term_pages, output_csv)
    print(f"Index written to {output_csv}")


if __name__ == "__main__":
    main()