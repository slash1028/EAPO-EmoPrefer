"""Minimal deterministic text-generation backend for Qwen3 edit planning and verification."""

from __future__ import annotations

from typing import Any


class Qwen3TextAgent:
    def __init__(self, model_path: str, max_new_tokens: int, attn_implementation: str = "sdpa"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        kwargs: dict[str, Any] = {
            "device_map": "auto",
            "torch_dtype": "auto",
            "trust_remote_code": True,
        }
        if attn_implementation:
            kwargs["attn_implementation"] = attn_implementation
        self.model = AutoModelForCausalLM.from_pretrained(model_path, **kwargs)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.max_new_tokens = max_new_tokens

    def generate_batch(self, prompts: list[str]) -> list[str]:
        texts = [
            self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for prompt in prompts
        ]
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True).to(self.model.device)
        with self.torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        trimmed = output[:, inputs.input_ids.shape[1] :]
        return [
            text.strip()
            for text in self.tokenizer.batch_decode(
                trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
        ]
