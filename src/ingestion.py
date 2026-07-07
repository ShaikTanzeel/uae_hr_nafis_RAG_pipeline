import os
import re
from pypdf import PdfReader
from src.logging_config import get_logger

# Module-level logger — all logs from this file will be tagged 'src.ingestion'
logger = get_logger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Reads a PDF file and extracts all text page-by-page, preserving UTF-8 formatting.
    """
    reader = PdfReader(pdf_path)
    full_text = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            # Clean trailing/leading spaces on lines, but preserve newlines
            cleaned_lines = [line.strip() for line in text.split("\n")]
            # Join with single newline for page continuity
            full_text.append("\n".join(cleaned_lines))
            
    return "\n\n".join(full_text)

def split_article_into_subclauses(article_text: str, article_metadata: dict, min_chunk_chars: int = 500, max_chunk_chars: int = 1500) -> list:
    """
    Splits a large article into sub-clauses based on numbering (1., 2., a., b.).
    Groups them so they stay roughly between min_chunk_chars and max_chunk_chars.
    Prepends the article title to each sub-chunk for context.
    """
    if len(article_text) <= min_chunk_chars:
        return [{
            "text": article_text,
            "metadata": {**article_metadata, "sub_chunk_index": 0, "parent_article_id": str(article_metadata.get("article_number")), "chunk_type": "full_article"}
        }]

    # Regex to find clause boundaries: "1. ", "1)", "a. ", "a)" or "1 " followed by Capital letter
    clause_pattern = re.compile(r'^\s*(?:(?:[0-9]{1,2}|[a-z])[\.\)\-]\s+|([1-9][0-9]?)\s+(?=[A-Z]))', re.MULTILINE)
    
    matches = list(clause_pattern.finditer(article_text))
    
    # If no clauses found, just return the whole thing
    if not matches:
        return [{
            "text": article_text,
            "metadata": {**article_metadata, "sub_chunk_index": 0, "parent_article_id": str(article_metadata.get("article_number")), "chunk_type": "full_article"}
        }]

    # The text before the first clause is usually the preamble or title of the article
    header_text = article_text[:matches[0].start()].strip()
    
    article_title = article_metadata.get("article_title", "Unknown Title")
    article_num = article_metadata.get("article_number", "X")
    
    # Build a context string to prepend to every sub-chunk
    context_prefix = f"Article ({article_num}) — {article_title}\n"
    if header_text and len(header_text) < 300: # If preamble is short, include it
        context_prefix += f"{header_text}\n---\n"
    else:
        context_prefix += "---\n"

    chunks = []
    current_chunk_text = ""
    sub_chunk_idx = 1
    
    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(article_text)
        
        clause_text = article_text[start_pos:end_pos].strip()
        
        # If adding this clause exceeds max, and we already have some text, save current chunk
        if current_chunk_text and (len(current_chunk_text) + len(clause_text) > max_chunk_chars):
            chunks.append({
                "text": context_prefix + current_chunk_text.strip(),
                "metadata": {
                    **article_metadata, 
                    "sub_chunk_index": sub_chunk_idx, 
                    "parent_article_id": str(article_num),
                    "chunk_type": "sub_chunk"
                }
            })
            sub_chunk_idx += 1
            current_chunk_text = clause_text
        else:
            if current_chunk_text:
                current_chunk_text += "\n\n" + clause_text
            else:
                current_chunk_text = clause_text
                
    # Add the last chunk
    if current_chunk_text:
        chunks.append({
            "text": context_prefix + current_chunk_text.strip(),
            "metadata": {
                **article_metadata, 
                "sub_chunk_index": sub_chunk_idx, 
                "parent_article_id": str(article_num),
                "chunk_type": "sub_chunk"
            }
        })
        
    return chunks

def split_by_articles(text: str, filename: str) -> list:
    """
    Uses regular expressions to split text cleanly by individual articles.
    Handles reversed parentheses glitches (e.g. 'Article )2 (') and ignores line-starting 
    citations by ensuring the article identifier occupies the entire line.
    """
    # Match lines containing ONLY "Article (X)" or "Article )X (" or "Article X" (plus optional spaces)
    # ^ - start of line
    # \s* - optional leading spaces
    # Article - literal word
    # \s* - optional spaces
    # [\(\)]? - optional parenthesis (normal or flipped)
    # \s* - optional spaces
    # (\d+) - Group 1: the digits
    # \s* - optional spaces
    # [\(\)]? - optional parenthesis (normal or flipped)
    # \s* - optional trailing spaces
    # $ - end of line
    article_pattern = re.compile(r'^\s*Article\s*[\(\)]?\s*(\d+)\s*[\(\)]?\s*$', re.IGNORECASE | re.MULTILINE)
    
    # Find all matches and their character positions in the document
    matches = list(article_pattern.finditer(text))
    
    chunks = []
    
    if not matches:
        # Fallback: if no articles found, return the entire document as a single chunk
        return [{
            "text": text,
            "metadata": {
                "source": filename,
                "article_number": "Full Document",
                "article_title": "All Sections",
                "sub_chunk_index": 0,
                "parent_article_id": "Full Document",
                "chunk_type": "full_article"
            }
        }]
    
    # 1. Capture the Preamble (everything before Article (1))
    first_match_start = matches[0].start()
    preamble_text = text[:first_match_start].strip()
    if preamble_text:
        chunks.append({
            "text": preamble_text,
            "metadata": {
                "source": filename,
                "article_number": "Preamble",
                "article_title": "Preamble and Decree Preamble",
                "sub_chunk_index": 0,
                "parent_article_id": "Preamble",
                "chunk_type": "full_article"
            }
        })
        
    # 2. Iterate through matches to slice the text between each Article
    for idx, match in enumerate(matches):
        start_pos = match.start()
        article_num = match.group(1) # The digits representing article number
        
        # End position is the start of the next article, or the end of the text
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        
        article_body = text[start_pos:end_pos].strip()
        
        # Determine the Article Title:
        # Typically the line right after "Article (X)" is the title (e.g., "Definitions")
        lines = [l.strip() for l in article_body.split("\n") if l.strip()]
        article_title = "Unknown"
        if len(lines) > 1:
            # If the first line is the match header, the second line is the title
            if article_pattern.match(lines[0]):
                article_title = lines[1]
            else:
                article_title = lines[0]
                
        metadata = {
            "source": filename,
            "article_number": article_num,
            "article_title": article_title
        }
        
        sub_chunks = split_article_into_subclauses(article_body, metadata)
        chunks.extend(sub_chunks)
        
    return chunks

def main():
    data_dir = "./data"
    
    if not os.path.exists(data_dir):
        logger.error(f"Error: Data directory '{data_dir}' not found.")
        return
        
    pdf_files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]
    if not pdf_files:
        logger.error(f"No PDF files found in '{data_dir}'.")
        return
        
    logger.info(f"Parsing {len(pdf_files)} PDF files using structure-aware parser...")
    
    all_chunks = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(data_dir, pdf_file)
        try:
            # 1. Extract raw text
            raw_text = extract_text_from_pdf(pdf_path)
            
            # 2. Split into structure-aware article chunks
            chunks = split_by_articles(raw_text, pdf_file)
            logger.info(f"-> {pdf_file}: Split into {len(chunks)} chunks.")
            all_chunks.extend(chunks)
            
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {e}")
            
    logger.info(f"Parsing complete! Total structured chunks: {len(all_chunks)}")
    
    # Print sample article info
    if len(all_chunks) > 1:
        sample = all_chunks[1] # Let's show Article (1)
        logger.info("--- STRUCTURE-AWARE SAMPLE CHUNK ---")
        logger.info(f"Source: {sample['metadata']['source']}")
        logger.info(f"Article Number: {sample['metadata']['article_number']}")
        logger.info(f"Article Title: {sample['metadata']['article_title']}")
        logger.info("Content Preview:\n" + "\n".join(sample['text'].split("\n")[:8]))

if __name__ == "__main__":
    main()
