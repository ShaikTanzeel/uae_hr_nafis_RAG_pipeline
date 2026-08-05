import os
from pypdf import PdfReader

def scan_pdf_for_articles(pdf_path: str) -> list:
    reader = PdfReader(pdf_path)
    matches = []
    
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text:
            continue
            
        lines = text.split("\n")
        for line_num, line in enumerate(lines):
            cleaned = line.strip()
            if "article" in cleaned.lower():
                matches.append({
                    "page": page_num + 1,
                    "line_num": line_num + 1,
                    "content": cleaned
                })
    return matches

def main():
    data_dir = "./data"
    pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]
    
    output_log_path = "./src/all_article_lines.txt"
    print(f"Scanning PDFs for references to 'Article'. Writing to: {output_log_path}")
    
    with open(output_log_path, "w", encoding="utf-8") as out_file:
        for pdf_file in pdf_files:
            pdf_path = os.path.join(data_dir, pdf_file)
            out_file.write(f"\n==================================================\n")
            out_file.write(f"FILE: {pdf_file}\n")
            out_file.write(f"==================================================\n")
            
            try:
                lines = scan_pdf_for_articles(pdf_path)
                for item in lines:
                    out_file.write(f"Page {item['page']}, Line {item['line_num']}: {item['content']}\n")
            except Exception as e:
                out_file.write(f"Error scanning {pdf_file}: {e}\n")
                
    print("Done! Open 'src/all_article_lines.txt' to see where every 'Article' is referenced.")

if __name__ == "__main__":
    main()
