import argparse
import os
import sys
import json
import urllib.request
import urllib.error
from typing import List

def ingest_file(file_path: str, base_url: str, project_id: str, user_id: str):
    """
    Reads a text file, splits it by empty lines, and uploads chunks to the API.
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by double newlines (paragraphs)
    chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]

    filename = os.path.basename(file_path)
    print(f"Ingesting '{filename}' into project '{project_id}' ({len(chunks)} chunks)...")

    success_count = 0
    fail_count = 0

    url = f"{base_url}/ai-api/editor/save"
    headers = {
        "Content-Type": "application/json"
    }

    for index, chunk_content in enumerate(chunks):
        chunk_uuid = f"{filename}-chunk-{index+1:03d}"

        payload = {
            "chunk_uuid": chunk_uuid,
            "content": chunk_content,
            "project_id": project_id,
            "user_id": user_id
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"  [OK] {chunk_uuid}")
                    success_count += 1
                else:
                    print(f"  [FAIL] {chunk_uuid}: {response.status}")
                    fail_count += 1

        except urllib.error.HTTPError as e:
             print(f"  [FAIL] {chunk_uuid}: {e.code} - {e.reason}")
             print(e.read().decode('utf-8'))
             fail_count += 1
        except Exception as e:
            print(f"  [ERROR] {chunk_uuid}: {e}")
            fail_count += 1

    print("\nSummary:")
    print(f"  Total: {len(chunks)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")

def main():
    parser = argparse.ArgumentParser(description="Ingest a text file into StoLink Chat.")
    parser.add_argument("file", help="Path to the .txt file")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API (default: http://localhost:8000)")
    parser.add_argument("--project-id", default="test-project", help="Project ID (default: test-project)")
    parser.add_argument("--user-id", default="test-user", help="User ID (default: test-user)")

    args = parser.parse_args()

    ingest_file(args.file, args.url, args.project_id, args.user_id)

if __name__ == "__main__":
    main()
