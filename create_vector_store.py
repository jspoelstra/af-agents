# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os
from pathlib import Path
from urllib.parse import unquote_plus

from azure.ai.agents.aio import AgentsClient
from azure.ai.agents.models import FileInfo, VectorStore
from azure.identity.aio import AzureCliCredential

from dotenv import load_dotenv
"""
The following sample demonstrates how to create a file-based vector store in Azure AI
by uploading local files. It handles file name conflicts based on an environment variable
or user input, and creates a vector store from the uploaded files.
"""

def file_paths_from_patterns(patterns: list[str]) -> list[Path]:
    """Returns a list of file paths matching the given patterns."""
    file_paths = []
    for pattern in patterns:
        print(f"Searching for files matching pattern: {pattern}")
        file_paths.extend(Path().glob(pattern))
    return file_paths


async def _list_all_files(agents_client: AgentsClient, purpose: str) -> list[FileInfo]:
    """Lists all files for a given 'purpose'."""

    all_items: list[FileInfo] = []
    count = 1
    after: str | None = None
    while True:
        # The API matches the structure of OpenAI's Files API response for listing files, 
        # which uses cursor-based pagination.
        params = {"after": after} if after else {}
        response = await agents_client.files.list(purpose=purpose, params=params)
        items = list(response.data)
        if not items:
            break
        all_items.extend(items)

        # print(f"Fetched page {count} of {len(items)} files")
        count += 1
        if count > 10:
            print("Too many pages; aborting.")
            break

        has_more = response["has_more"]
        if not has_more:
            break

        after = response["last_id"]

    return all_items


def _env_file_conflict_action() -> str:
    # Controls behavior when a file with the same filename already exists.
    # - ask (default): prompt per file
    # - reuse: use existing file id (no upload)
    # - upload: upload new file (keeps existing; creates duplicate filename)
    # - overwrite: delete existing matching file(s) then upload new
    action = os.environ.get("FILE_CONFLICT_ACTION", "ask").strip().lower()
    if action not in {"ask", "reuse", "upload", "overwrite"}:
        raise ValueError(
            "Invalid FILE_CONFLICT_ACTION. Use one of: ask, reuse, upload, overwrite"
        )
    return action


def _prompt_file_conflict_action(file_path: Path, existing: list[FileInfo]) -> str:
    print(f"File name conflict for '{file_path.name}'.")
    for f in existing:
        created_at = getattr(f, "created_at", None)
        print(f"- Existing: id={f.id}, bytes={getattr(f, 'bytes', 'n/a')}, created_at={created_at}")

    prompt = (
        "Choose action: [r]euse existing (default), "
        "[u]pload new (keep both), "
        "[o]verwrite (delete existing then upload new): "
    )
    choice = input(prompt).strip().lower()
    if choice in {"", "r", "reuse"}:
        return "reuse"
    if choice in {"u", "upload"}:
        return "upload"
    if choice in {"o", "overwrite"}:
        return "overwrite"

    print("Unrecognized choice; defaulting to reuse.")
    return "reuse"


def _pick_existing_file_id(existing: list[FileInfo]) -> str:
    # Prefer the most recent if timestamps exist; otherwise first.
    def sort_key(f: FileInfo):
        created_at = getattr(f, "created_at", None)
        return (created_at is not None, created_at)

    best = sorted(existing, key=sort_key, reverse=True)[0]
    return best.id


async def upload_files_and_create_vector_store(agents_client: AgentsClient, name: str, file_paths: list[Path]) -> VectorStore:
    """Uploads files and creates a vector store from them."""
    uploaded_file_ids = []

    existing_files = await _list_all_files(agents_client, purpose="assistants")
    existing_by_filename: dict[str, list[FileInfo]] = {}
    for f in existing_files:
        normalized = unquote_plus(f.filename)
        existing_by_filename.setdefault(normalized, []).append(f)
    print(f"Found {len(existing_files)} existing files for purpose 'assistants'.")
    default_action = _env_file_conflict_action()
    for file_path in file_paths:
        local_name = file_path.name
        conflicts = existing_by_filename.get(local_name, [])
        action = default_action
        if conflicts:
            if default_action == "ask":
                action = _prompt_file_conflict_action(file_path, conflicts)
            else:
                print(
                    f"File name conflict for '{file_path.name}'. "
                    f"Using FILE_CONFLICT_ACTION={default_action}."
                )

        if conflicts and action == "reuse":
            file_id = _pick_existing_file_id(conflicts)
            print(f"Reusing existing file id={file_id} for '{file_path.name}'")
            uploaded_file_ids.append(file_id)
            continue

        if conflicts and action == "overwrite":
            print(f"Deleting {len(conflicts)} existing file(s) named '{local_name}'...")
            for f in conflicts:
                await agents_client.files.delete(f.id)
            existing_by_filename[local_name] = []

        print(f"Uploading file from: {file_path}")
        file = await agents_client.files.upload_and_poll(file_path=str(file_path), purpose="assistants")
        print(f"Uploaded file, file ID: {file.id}")
        uploaded_file_ids.append(file.id)

        # The service may store a URL-encoded filename (e.g. spaces as %20)
        existing_by_filename.setdefault(local_name, []).append(file)

    vector_store = await agents_client.vector_stores.create_and_poll(file_ids=uploaded_file_ids, name=name)
    return vector_store

async def main() -> None:
    """Main function orchestration the creation of a vector store from files."""
    load_dotenv()

    file: FileInfo | None = None
    vector_store: VectorStore | None = None

    async with (
        AzureCliCredential() as credential,
        AgentsClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as agents_client,
    ):
        # Get list of files to upload from env variable
        file_patterns = os.environ.get("FILE_PATTERNS", "resources/*.pdf").split(",")
        file_paths = file_paths_from_patterns(file_patterns)
        print(f"Found {len(file_paths)} files to upload")
        # Upload file and create vector store
        if file_paths:
            vector_store_name = os.environ.get("VECTOR_STORE_NAME", "my_vectorstore")
            print(f"Creating vector store '{vector_store_name}' from uploaded files...")
            vector_store = await upload_files_and_create_vector_store(agents_client, vector_store_name, file_paths)
            if vector_store:
                print(f"Created vector store {vector_store_name}, vector store ID: {vector_store.id}")
        else:
            print("No files found to upload. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
