"""Test RAG ingestion and LoRA training data collection."""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps", "backend"))

from dash_backend.llm.fine_tuner import get_fine_tuning_manager


async def main():
    ftm = get_fine_tuning_manager()
    await ftm.rag_engine.initialize()
    print(f"RAG: {len(ftm.rag_engine._chunks)} chunks from Obsidian")

    # Ingest backend codebase
    repo = os.path.join(os.path.dirname(__file__), "apps", "backend")
    count2 = await ftm.ingest_code_repo(repo)
    print(f"Ingested {count2} chunks from backend codebase")
    print(f"Total RAG chunks: {len(ftm.rag_engine._chunks)}")

    # Test search
    for query in [
        "how to configure ollama model",
        "websocket authentication token",
        "system prompt for coder mode",
    ]:
        results = await ftm.rag_engine.search(query, top_k=2)
        print(f'\nSearch: "{query}"')
        for r in results:
            src = os.path.basename(r.source)
            print(f"  [{src}] {r.content[:120]}...")

    # Prepare training data
    count3 = await ftm.prepare_training_data()
    print(f"\nTraining data: {count3} conversation examples collected")

    # Show training data location
    training_path = os.path.join(ftm.lora_trainer.data_dir, "training_data.alpaca.json")
    if os.path.exists(training_path):
        import json
        with open(training_path) as f:
            data = json.load(f)
        print(f"Training file: {training_path}")
        print(f"Examples: {len(data)}")
        if data:
            print(f"Sample: {json.dumps(data[0], indent=2)[:300]}")

    # Generate training script
    script_path = ftm.lora_trainer.generate_training_script()
    print(f"\nTraining script: {script_path}")

    # Status
    status = ftm.get_status()
    print(f"\nStatus: {json.dumps(status, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
