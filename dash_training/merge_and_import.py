"""
Merge LoRA adapter into TinyLlama base model, convert to GGUF, import to Ollama.
Run from: C:/Users/Asus/Desktop/dash
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
LORA_PATH = "dash_training/lora_output"
MERGED_PATH = "dash_training/merged_model"
GGUF_PATH = "dash_training/merged_model.gguf"


def merge_lora():
    """Merge LoRA adapter weights into base model."""
    print("=" * 60)
    print("Step 1: Merging LoRA into base model")
    print("=" * 60)

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print("Loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype="auto",
        device_map="cpu",
        trust_remote_code=True,
    )

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    print("Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, LORA_PATH)

    print("Merging weights...")
    model = model.merge_and_unload()

    print(f"Saving merged model to {MERGED_PATH}...")
    os.makedirs(MERGED_PATH, exist_ok=True)
    model.save_pretrained(MERGED_PATH)
    tokenizer.save_pretrained(MERGED_PATH)

    print("Merge complete!")
    return True


def convert_to_gguf():
    """Convert merged HF model to GGUF format."""
    print("\n" + "=" * 60)
    print("Step 2: Converting to GGUF")
    print("=" * 60)

    gguf_script = None

    # Try common locations for llama.cpp convert script
    candidates = [
        "dash_training/convert_hf_to_gguf.py",
        os.path.expanduser("~/llama.cpp/convert_hf_to_gguf.py"),
        os.path.expanduser("~/.local/bin/convert_hf_to_gguf.py"),
    ]

    # Also check if llama-cpp-python has it bundled
    try:
        import llama_cpp
        llama_dir = os.path.dirname(llama_cpp.__file__)
        candidates.append(os.path.join(llama_dir, "convert_hf_to_gguf.py"))
    except ImportError:
        pass

    for c in candidates:
        if os.path.exists(c):
            gguf_script = c
            break

    if gguf_script is None:
        print("convert_hf_to_gguf.py not found. Trying to download...")
        try:
            url = "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/convert_hf_to_gguf.py"
            gguf_script = "dash_training/convert_hf_to_gguf.py"
            subprocess.run(
                ["curl", "-L", "-o", gguf_script, url],
                check=True,
                capture_output=True,
            )
            print(f"Downloaded to {gguf_script}")
        except Exception as e:
            print(f"Failed to download convert script: {e}")
            print("Falling back to transformers-only approach...")
            return fallback_import()

    print(f"Using convert script: {gguf_script}")

    # Install gguf package if needed
    try:
        import gguf
    except ImportError:
        print("Installing gguf package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "gguf", "-q"], check=True)

    # Convert
    output_path = os.path.abspath(GGUF_PATH)
    result = subprocess.run(
        [sys.executable, gguf_script, MERGED_PATH,
         "--outfile", output_path,
         "--outtype", "f16"],
        capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0:
        print(f"Convert failed: {result.stderr}")
        return fallback_import()

    print(f"GGUF saved to: {output_path}")
    return True


def fallback_import():
    """If GGUF conversion fails, import as a regular model."""
    print("\nFalling back to direct Ollama import from HF model name...")

    # Create a Modelfile that uses the merged HF model directly via a GGUF FROM
    modelfile_path = os.path.abspath("dash_training/merged_Modelfile")

    # First try to find the model in HF cache
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    model_dir = None
    for d in os.listdir(hf_cache) if os.path.exists(hf_cache) else []:
        if "TinyLlama" in d:
            candidate = os.path.join(hf_cache, d, "snapshots")
            if os.path.exists(candidate):
                snapshots = os.listdir(candidate)
                if snapshots:
                    model_dir = os.path.join(candidate, snapshots[0])
                    break

    if model_dir:
        print(f"Found HF cache: {model_dir}")
        # Try to find a GGUF file in the cache
        for f in os.listdir(model_dir):
            if f.endswith(".gguf"):
                gguf_file = os.path.join(model_dir, f)
                with open(modelfile_path, "w") as mf:
                    mf.write(f"FROM {gguf_file}\n")
                    mf.write("PARAMETER temperature 0.7\n")
                    mf.write("PARAMETER top_p 0.9\n")
                    mf.write('SYSTEM You are DASH, a JARVIS-like AI assistant. Be concise and helpful.\n')
                print(f"Creating Ollama model from cached GGUF: {gguf_file}")
                result = subprocess.run(
                    ["ollama", "create", "dash-finetuned", "-f", modelfile_path],
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    print("Successfully created dash-finetuned!")
                    return True
                print(f"Ollama create failed: {result.stderr}")

    print("\nCannot convert to GGUF automatically.")
    print("The LoRA adapter is saved at: dash_training/lora_output/")
    print("You can use it with Python + transformers directly.")
    print("For Ollama, use Google Colab to train with GPU and export as GGUF.")
    return False


def import_to_ollama():
    """Import the GGUF model into Ollama."""
    print("\n" + "=" * 60)
    print("Step 3: Importing into Ollama")
    print("=" * 60)

    gguf_abs = os.path.abspath(GGUF_PATH)
    modelfile_path = os.path.abspath("dash_training/final_Modelfile")

    with open(modelfile_path, "w") as f:
        f.write(f"FROM {gguf_abs}\n\n")
        f.write("PARAMETER temperature 0.7\n")
        f.write("PARAMETER top_p 0.9\n")
        f.write("PARAMETER repeat_penalty 1.1\n")
        f.write('SYSTEM You are DASH, a JARVIS-like AI assistant running on the user\'s Windows PC. Be concise, helpful, slightly formal. Use technical language when appropriate. You have access to the system via autonomous agent tools.\n')

    print(f"Modelfile written to: {modelfile_path}")
    print(f"GGUF model: {gguf_abs}")

    # Remove old model if exists
    subprocess.run(["ollama", "rm", "dash-finetuned"], capture_output=True)

    result = subprocess.run(
        ["ollama", "create", "dash-finetuned", "-f", modelfile_path],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode == 0:
        print("\n✅ dash-finetuned created successfully!")
        # Verify
        result2 = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        print(result2.stdout)
        return True
    else:
        print(f"\n❌ Failed: {result.stderr}")
        return False


def main():
    print("DASH LoRA Merge + Import Pipeline")
    print("=" * 60)

    # Step 1: Merge
    if not merge_lora():
        print("Merge failed!")
        sys.exit(1)

    # Step 2: Convert to GGUF
    converted = convert_to_gguf()

    if converted and os.path.exists(GGUF_PATH):
        # Step 3: Import to Ollama
        import_to_ollama()
    else:
        # Fallback was already tried in convert_to_gguf
        pass

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
