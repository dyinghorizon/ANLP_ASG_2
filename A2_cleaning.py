"""
A2_cleaning.py
Julius Caesar ETL Pipeline - Data Extraction and Chunking
"""

import pdfplumber
import re
import json
import os
from pathlib import Path
from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import time

load_dotenv()


class JuliusCaesarETL:
    def __init__(self, pdf_path: str, output_dir: str = "Data"):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.1)

    def extract_raw_text_by_pages(self) -> List[str]:
        print("Extracting text from PDF...")
        pages = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text(layout=True)
                if text:
                    pages.append(text)
                if (i + 1) % 20 == 0:
                    print(f"Processed {i + 1}/{len(pdf.pages)} pages")
        print(f"Extracted {len(pages)} pages")
        return pages

    def find_act1_scene1_start(self, pages: List[str]) -> int:
        for i, page in enumerate(pages):
            if re.search(r'ACT\s+1.*?Scene\s+1', page, re.DOTALL):
                return i
        return 0

    def extract_clean_text_with_llm(self, raw_pages: List[str]) -> str:
        print("Extracting clean dialogue with Gemini AI...")
        start_idx = self.find_act1_scene1_start(raw_pages)
        print(f"Found ACT 1, Scene 1 starting at page {start_idx + 1}")

        batch_size = 5
        all_clean_text = []
        pages_to_process = raw_pages[start_idx:]
        num_batches = (len(pages_to_process) + batch_size - 1) // batch_size

        for batch_num in range(num_batches):
            start = batch_num * batch_size
            end = min(start + batch_size, len(pages_to_process))
            batch_pages = pages_to_process[start:end]
            batch_text = '\n'.join(batch_pages)

            print(f"Processing batch {batch_num + 1}/{num_batches} (pages {start_idx + start + 1}-{start_idx + end})...")

            prompt = f"""You are extracting the dialogue from Shakespeare's "Julius Caesar" play.

**Raw Text (may contain headers, footers, line numbers, page numbers):**
{batch_text}

**Your Task:**
Extract ONLY the actual play content (dialogues, stage directions, act/scene markers).

**What to REMOVE:**
- Page numbers
- Headers/footers like "Julius Caesar ACT 1. SC. 2"
- FTLN line numbers (e.g., "FTLN 0001")
- Table of contents
- Publishing information
- Anything that's not the actual play

**Format Rules:**
1. Keep ACT and Scene markers exactly as: "ACT 1" and "Scene 1"
2. Speaker names should be on their own line in UPPERCASE
3. Dialogue starts on the next line after the speaker
4. Stage directions in square brackets: [Enter Brutus]
5. Each dialogue should be separated by a blank line

**Example Output Format:**
ACT 1
Scene 1

[Enter Flavius, Marullus, and certain Commoners]

FLAVIUS
Hence! Home, you idle creatures, get you home!
Is this a holiday?

CARPENTER
Why, sir, a carpenter.

**Important:** Return ONLY the extracted play text, no explanations, no markdown formatting."""

            try:
                response = self.llm.invoke(prompt)
                clean_text = response.content.strip()
                clean_text = re.sub(r'```.*?\n', '', clean_text)
                clean_text = re.sub(r'\n```', '', clean_text)
                all_clean_text.append(clean_text)
                time.sleep(1)
            except Exception as e:
                print(f"Error processing batch {batch_num + 1}: {e}")
                continue

        full_clean_text = '\n\n'.join(all_clean_text)
        clean_txt_path = self.output_dir / "julius_caesar_clean.txt"
        with open(clean_txt_path, 'w', encoding='utf-8') as f:
            f.write(full_clean_text)
        print(f"Clean text saved to {clean_txt_path}")
        return full_clean_text

    def parse_clean_text_to_jsonl(self, clean_text: str) -> List[Dict]:
        print("Parsing clean text to structured JSONL...")
        lines = clean_text.split('\n')
        structured_data = []
        current_act = None
        current_scene = None
        current_speaker = None
        current_dialogue = []
        entry_id = 0

        for line in lines:
            line = line.strip()

            if not line:
                if current_speaker and current_dialogue:
                    dialogue_text = ' '.join(current_dialogue)
                    is_soliloquy = len(dialogue_text) > 300
                    structured_data.append({
                        "id": entry_id,
                        "type": "dialogue",
                        "speaker": current_speaker,
                        "text": dialogue_text,
                        "act": current_act,
                        "scene": current_scene,
                        "is_soliloquy": is_soliloquy
                    })
                    entry_id += 1
                    current_speaker = None
                    current_dialogue = []
                continue

            act_match = re.match(r'^ACT\s+(\d+)', line)
            if act_match:
                current_act = int(act_match.group(1))
                continue

            scene_match = re.match(r'^Scene\s+(\d+)', line)
            if scene_match:
                current_scene = int(scene_match.group(1))
                continue

            if line.startswith('[') and line.endswith(']'):
                structured_data.append({
                    "id": entry_id,
                    "type": "stage_direction",
                    "speaker": "STAGE_DIRECTION",
                    "text": line[1:-1],
                    "act": current_act,
                    "scene": current_scene,
                    "is_soliloquy": False
                })
                entry_id += 1
                continue

            if line.isupper() and len(line) < 50 and not any(char.isdigit() for char in line):
                if current_speaker and current_dialogue:
                    dialogue_text = ' '.join(current_dialogue)
                    is_soliloquy = len(dialogue_text) > 300
                    structured_data.append({
                        "id": entry_id,
                        "type": "dialogue",
                        "speaker": current_speaker,
                        "text": dialogue_text,
                        "act": current_act,
                        "scene": current_scene,
                        "is_soliloquy": is_soliloquy
                    })
                    entry_id += 1
                current_speaker = line
                current_dialogue = []
                continue

            if current_speaker:
                current_dialogue.append(line)

        if current_speaker and current_dialogue:
            dialogue_text = ' '.join(current_dialogue)
            is_soliloquy = len(dialogue_text) > 300
            structured_data.append({
                "id": entry_id,
                "type": "dialogue",
                "speaker": current_speaker,
                "text": dialogue_text,
                "act": current_act,
                "scene": current_scene,
                "is_soliloquy": is_soliloquy
            })

        print(f"Parsed {len(structured_data)} entries")
        return structured_data

    def create_chunks_from_structured_data(self, structured_data: List[Dict]) -> List[Dict]:
        print("Creating chunks for RAG...")
        chunks = []
        chunk_id = 0
        scenes = {}

        for entry in structured_data:
            if entry['act'] is None or entry['scene'] is None:
                continue
            key = (entry['act'], entry['scene'])
            if key not in scenes:
                scenes[key] = []
            scenes[key].append(entry)

        for (act, scene), entries in scenes.items():
            scene_lines = []
            speakers_in_scene = set()
            has_soliloquy = False

            for entry in entries:
                if entry['type'] == 'stage_direction':
                    scene_lines.append(f"[{entry['text']}]")
                else:
                    scene_lines.append(f"{entry['speaker']}: {entry['text']}")
                    speakers_in_scene.add(entry['speaker'])
                    if entry.get('is_soliloquy', False):
                        has_soliloquy = True

            scene_text = '\n\n'.join(scene_lines)
            chunks.append({
                "chunk_id": chunk_id,
                "chunk_type": "scene",
                "text": scene_text,
                "metadata": {
                    "act": act,
                    "scene": scene,
                    "speakers": list(speakers_in_scene),
                    "num_dialogues": len([e for e in entries if e['type'] == 'dialogue']),
                    "has_soliloquy": has_soliloquy
                }
            })
            chunk_id += 1

        for entry in structured_data:
            if entry.get('is_soliloquy', False) and entry.get('act') and entry.get('scene'):
                chunks.append({
                    "chunk_id": chunk_id,
                    "chunk_type": "soliloquy",
                    "text": f"{entry['speaker']}: {entry['text']}",
                    "metadata": {
                        "act": entry['act'],
                        "scene": entry['scene'],
                        "speaker": entry['speaker'],
                        "is_soliloquy": True
                    }
                })
                chunk_id += 1

        print(f"Created {len(chunks)} chunks")
        return chunks

    def remove_duplicate_chunks(self, chunks: List[Dict]) -> List[Dict]:
        print("Checking for duplicate chunks...")
        seen_texts = set()
        unique_chunks = []
        duplicates_removed = 0

        for chunk in chunks:
            text_hash = hash(chunk['text'])
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                chunk['chunk_id'] = len(unique_chunks)
                unique_chunks.append(chunk)
            else:
                duplicates_removed += 1

        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate chunks")
        else:
            print("No duplicates found")

        print(f"Retained {len(unique_chunks)} unique chunks")
        return unique_chunks

    def save_outputs(self, structured_data: List[Dict], chunks: List[Dict]):
        print("Saving outputs...")

        structured_jsonl_path = self.output_dir / "julius_caesar_structured.jsonl"
        with open(structured_jsonl_path, 'w', encoding='utf-8') as f:
            for item in structured_data:
                f.write(json.dumps(item) + '\n')
        print(f"Structured JSONL saved to {structured_jsonl_path}")

        structured_json_path = self.output_dir / "julius_caesar_structured.json"
        with open(structured_json_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2)
        print(f"Structured JSON saved to {structured_json_path}")

        chunks_jsonl_path = self.output_dir / "julius_caesar_chunks.jsonl"
        with open(chunks_jsonl_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk) + '\n')
        print(f"Chunks JSONL saved to {chunks_jsonl_path}")

        chunks_json_path = self.output_dir / "julius_caesar_chunks.json"
        with open(chunks_json_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2)
        print(f"Chunks JSON saved to {chunks_json_path}")

    def run_step1_extract_clean_text(self):
        print("\n" + "=" * 60)
        print("STEP 1: EXTRACT CLEAN TEXT WITH LLM")
        print("=" * 60)

        raw_pages = self.extract_raw_text_by_pages()
        clean_text = self.extract_clean_text_with_llm(raw_pages)

        print("\n" + "=" * 60)
        print("STEP 1 COMPLETE")
        print("=" * 60)
        print("\nCheck 'Data/julius_caesar_clean.txt' and verify it looks good")
        print("If satisfied, run: etl.run_step2_convert_to_jsonl()")

    def run_step2_convert_to_jsonl(self):
        print("\n" + "=" * 60)
        print("STEP 2: CONVERT CLEAN TEXT TO JSONL")
        print("=" * 60)

        clean_txt_path = self.output_dir / "julius_caesar_clean.txt"
        if not clean_txt_path.exists():
            print("Error: julius_caesar_clean.txt not found")
            print("Run step 1 first: etl.run_step1_extract_clean_text()")
            return

        with open(clean_txt_path, 'r', encoding='utf-8') as f:
            clean_text = f.read()

        structured_data = self.parse_clean_text_to_jsonl(clean_text)
        chunks = self.create_chunks_from_structured_data(structured_data)
        chunks = self.remove_duplicate_chunks(chunks)
        self.save_outputs(structured_data, chunks)

        print("\n" + "=" * 60)
        print("STEP 2 COMPLETE")
        print("=" * 60)
        print(f"\nSummary:")
        print(f"   - Total entries: {len(structured_data)}")
        print(f"   - Total chunks: {len(chunks)}")


def main():
    pdf_path = "julius-caesar_PDF_FolgerShakespeare.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not found")
        print("Create a .env file with: GOOGLE_API_KEY=your_key")
        return

    etl = JuliusCaesarETL(pdf_path=pdf_path)

    print("\nChoose an option:")
    print("1. Run Step 1: Extract clean text (LLM-based)")
    print("2. Run Step 2: Convert clean text to JSONL")
    print("3. Run both steps automatically")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == '1':
        etl.run_step1_extract_clean_text()
    elif choice == '2':
        etl.run_step2_convert_to_jsonl()
    elif choice == '3':
        etl.run_step1_extract_clean_text()
        print("\n" + "=" * 60)
        input("Press Enter to continue to Step 2 (or Ctrl+C to stop)...")
        etl.run_step2_convert_to_jsonl()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()