import sys
import PyPDF2
import os
import re

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
    "repr", "request", "Response", "return", "reversed", "round", "search", 
    "send", "sendp", "Session", "set", "setattr", "slice", "sniff", "sorted", 
    "split", "sr", "sr1", "srp", "srp1", "staticmethod", "str", "sub", "sum", 
    "super", "TCP", "Timeout", "TooManyRedirects", "True", "try", "tuple", 
    "type", "UDP", "vars", "while", "with", "wrpcap", "yield", "zip", 
    "DOTALL", "IGNORECASE", "MULTILINE", "VERBOSE", "UNICODE", "ConnectionError", 
    "Match", "RegexObject", "RequestException", "codes", "escape", "findall", 
    "finditer", "fullmatch", "purge", "status_codes", "subn"
]
relevant_word = [word.lower() for word in relevant_words] 


def extract_words_from_directory(directory_path, password):
    word_pages = {}  # Dictionary to store word and list of page numbers
    try:
        # Iterate through all files in the directory
        for filename in os.listdir(directory_path):
            if filename.lower().endswith('.pdf'):  # Check if file is a PDF
                pdf_path = os.path.join(directory_path, filename)
                print(f"Processing: {filename}")
                
                try:
                    # Open the PDF file
                    with open(pdf_path, 'rb') as file:
                        # Create a PDF reader object
                        pdf_reader = PyPDF2.PdfReader(file)
                        
                        # Check if the PDF is encrypted
                        if pdf_reader.is_encrypted:
                            # Attempt to decrypt with the provided password
                            if not pdf_reader.decrypt(password):
                                print(f"Incorrect password for {filename}!")
                                continue
                        
                        # Iterate through each page
                        for page_num, page in enumerate(pdf_reader.pages, start=1):
                            # Extract text from the page
                            text = page.extract_text()
                            if text:
                                # Split text into words
                                words = re.findall(r"\w+", text)
                                for word in words:
                                    # Clean word by removing punctuation
                                    cleaned_word = word.strip('''.,!?()[]{}":;'|*&^!@#$%(\)''').lower()
                                    if cleaned_word:
                                        # Add word to dictionary with page number
                                        if cleaned_word in word_pages:
                                            if page_num not in word_pages[cleaned_word]:
                                                word_pages[cleaned_word].append(f"{filename}:Page {page_num}")
                                        else:
                                            word_pages[cleaned_word] = [f"{filename}:Page {page_num}"]
                
                except Exception as e:
                    print(f"Error processing {filename}: {str(e)}")
                    continue
                            
    except FileNotFoundError:
        print("Directory not found!")
    except Exception as e:
        print(f"An error occurred: {str(e)}")    
    return word_pages

if len(sys.argv)<=1:
    print("Pass the path to the directory containing pdfs.")
else:
    password = input("What is your pdf password? ")             
    word_pages = extract_words_from_directory(sys.argv[1], password)
    # Print the dictionary
    for word, pages in word_pages.items():
        if not word in relevant_words:
            print(f"{word}: {pages}")