import os
from pypdf import PdfReader

def inspect_pdf_start(pdf_path: str, max_chars: int = 5000) -> str:
    reader = PdfReader(pdf_path)
    extracted_text = ""
    for idx in range(min(5, len(reader.pages))):
        text = reader.pages[idx].extract_text()
        if text:
            extracted_text += f"\n\n--- Page {idx+1} ---\n" + text
            
    return extracted_text[:max_chars]

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(project_root, "data")
    pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]

    output_log_path = os.path.join(project_root, "src", "inspected_structure.txt")
    print(f"Inspecting PDF files. Writing results to: {output_log_path}")
    
    with open(output_log_path, "w", encoding="utf-8") as out_file:
        for pdf_file in pdf_files:
            pdf_path = os.path.join(data_dir, pdf_file)
            out_file.write(f"\n==================================================\n")
            out_file.write(f"INSPECTING: {pdf_file}\n")
            out_file.write(f"==================================================\n")
            try:
                content = inspect_pdf_start(pdf_path)
                out_file.write(content)
            except Exception as e:
                out_file.write(f"Error inspecting {pdf_file}: {e}\n")
                
    print("Done! You can now open 'src/inspected_structure.txt' in your editor to see the layout.")

if __name__ == "__main__":
    main()
