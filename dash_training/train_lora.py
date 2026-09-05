#!/usr/bin/env python3
"""
DASH LoRA Fine-Tuning Script (CPU + GPU, Python 3.14 compatible)

Uses HuggingFace PEFT + transformers for LoRA training.
Does NOT use the datasets library (incompatible with Python 3.14).
Works on CPU (slow) or GPU (fast).

Requirements:
    pip install torch transformers peft accelerate

Usage:
    python train_lora.py --epochs 3 --batch_size 2
"""

import argparse
import json
import os
import sys
import torch
from torch.utils.data import Dataset, DataLoader


class AlpacaDataset(Dataset):
    """Simple dataset that loads Alpaca-format JSON directly."""
    def __init__(self, data_path, tokenizer, max_length=512):
        with open(data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        text = f"### Instruction:\n{item['instruction']}\n\n### Response:\n{item['output']}"
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": encoding["input_ids"].squeeze().clone(),
        }


def main():
    parser = argparse.ArgumentParser(description="DASH LoRA Fine-Tuning")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--base_model", default="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    parser.add_argument("--training_data", default=os.path.join("apps", "backend", "dash_training", "training_data.alpaca.json"))
    parser.add_argument("--output_dir", default=os.path.join("dash_training", "lora_output"))
    parser.add_argument("--max_seq_length", type=int, default=512)
    parser.add_argument("--use_4bit", action="store_true")
    args = parser.parse_args()

    # Check training data exists
    if not os.path.exists(args.training_data):
        print(f"ERROR: Training data not found at {args.training_data}")
        print("Run the backend first, then: POST /api/v1/fine-tuning/prepare-training")
        sys.exit(1)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install torch transformers peft accelerate trl")
        sys.exit(1)

    # Detect device
    if torch.cuda.is_available():
        device = "cuda"
        print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        device = "cpu"
        print("Using CPU (training is slow — use Google Colab for GPU)")

    # Load tokenizer
    print(f"Loading tokenizer: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load model
    print(f"Loading model: {args.base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float32 if device == "cpu" else torch.float16,
    )

    # Apply LoRA
    print(f"Applying LoRA (r={args.lora_r}, alpha={args.lora_alpha})")
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load dataset (no datasets library needed)
    print(f"Loading training data: {args.training_data}")
    dataset = AlpacaDataset(args.training_data, tokenizer, args.max_seq_length)
    print(f"Loaded {len(dataset)} training examples")

    # Training arguments
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        warmup_steps=5,
        logging_steps=1,
        save_strategy="epoch",
        fp16=(device == "cuda"),
        bf16=False,
        optim="adamw_torch",
        report_to="none",
        dataloader_pin_memory=False,
        remove_unused_columns=False,
    )

    # Train
    print(f"\nStarting training for {args.epochs} epochs...")
    print(f"  Device: {device}")
    print(f"  Examples: {len(dataset)}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  LoRA rank: {args.lora_r}")
    print(f"  Max seq length: {args.max_seq_length}")
    print()

    # Manual training loop (avoids SFTTrainer compatibility issues)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    model.train()
    total_steps = 0
    for epoch in range(args.epochs):
        epoch_loss = 0
        for batch_idx, batch in enumerate(dataloader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            loss.backward()

            if (batch_idx + 1) % 4 == 0:
                optimizer.step()
                optimizer.zero_grad()

            epoch_loss += loss.item()
            total_steps += 1

            if total_steps % 5 == 0:
                print(f"  Step {total_steps} | Epoch {epoch+1} | Loss: {loss.item():.4f}")

        avg_loss = epoch_loss / max(len(dataloader), 1)
        print(f"\nEpoch {epoch+1}/{args.epochs} — Avg Loss: {avg_loss:.4f}")

    # Save
    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"  LoRA adapter saved to: {args.output_dir}")
    print(f"  Files: {os.listdir(args.output_dir)}")

    # Generate Modelfile for Ollama
    modelfile_path = os.path.join(args.output_dir, "Modelfile")
    with open(modelfile_path, "w") as f:
        f.write(f"FROM {args.base_model}\n")
        f.write(f"ADAPTER {os.path.join(args.output_dir, 'adapter_model.bin')}\n\n")
        f.write("PARAMETER temperature 0.7\n")
        f.write("PARAMETER top_p 0.9\n")
        f.write('SYSTEM You are DASH, a JARVIS-like AI assistant running on the user\'s Windows PC. Be concise, helpful, slightly formal. Use technical language when appropriate.\n')
    print(f"  Ollama Modelfile: {modelfile_path}")
    print(f"\nTo import into Ollama:")
    print(f"  ollama create dash-finetuned -f {modelfile_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
