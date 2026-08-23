# Paper-Aligned Experimental Results

This page reproduces the validation and official test results reported in the EAPO camera-ready manuscript. All values are weighted F1 (WAF, %) unless stated otherwise. The manuscript is the source of truth for every number below.

## Evaluation Protocol

- **Orig. Val:** WAF on the 563 original human-annotated validation pairs.
- **Emotion Flip, Intensity Mismatch, Evidence Contradiction, Modality Omission:** WAF on the corresponding swap-balanced controlled-error subset.
- **4-Error Avg:** macro-average WAF over the four controlled-error subsets.
- **Swap Cons:** consistency of the selected description identity after reversing candidate order, averaged over the four subsets.
- **S1:** direct multimodal preference judging.
- **S2:** preference judging with a Qwen3-generated multimodal description as auxiliary evidence.

## MiniCPM-o-2.6-8B

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 Zero-shot | 59.48 | 86.92 | 82.03 | 92.70 | 92.17 | 88.46 | 81.94 |
| S1 Normal SFT | 61.77 | 87.01 | 81.93 | 92.53 | 92.53 | 88.50 | 81.67 |
| S1 Normal SFT+DPO | 61.43 | 86.83 | 81.94 | 92.44 | 92.44 | 88.41 | 81.81 |
| S1 Error-Aug SFT | 61.53 | 88.88 | 90.20 | 94.31 | **94.93** | 92.08 | 87.14 |
| S1 Error-Aug SFT+DPO | **63.27** | **89.29** | **90.38** | **95.10** | 94.84 | **92.40** | **87.46** |

## Qwen2.5-Omni-7B

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 Zero-shot | 65.53 | 75.41 | 76.57 | 82.79 | 81.11 | 78.97 | 70.42 |
| S2 Normal SFT | 75.84 | 86.45 | 89.21 | 93.06 | 92.61 | 90.33 | 84.91 |
| S2 Normal SFT+DPO | 77.96 | **89.15** | **92.08** | **94.04** | 93.24 | **92.13** | **89.86** |
| S2 Error-Aug SFT | **79.93** | 88.59 | 90.46 | **94.04** | **94.13** | 91.80 | 86.97 |
| S2 Error-Aug SFT+DPO | 79.75 | 88.10 | 88.35 | 93.94 | 93.49 | 90.97 | 84.21 |

## Qwen3-Omni-30B-A3B-Instruct

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 Zero-shot | 73.18 | 92.08 | 90.92 | 96.17 | 96.09 | 93.82 | 91.55 |
| S2 Normal SFT | 75.80 | 90.29 | 90.20 | 94.57 | 93.68 | 92.19 | 88.21 |
| S2 Normal SFT+DPO | 77.80 | 89.95 | 87.46 | 93.86 | 92.35 | 90.90 | 86.83 |
| S2 Error-Aug SFT | 75.46 | 87.22 | 87.56 | 93.23 | 92.34 | 90.09 | 83.90 |
| **S2 Error-Aug SFT+DPO** | **79.04** | **94.22** | **94.57** | **98.04** | **96.44** | **95.82** | **94.13** |

## Additional Zero-Shot Judges

| Model | Strategy | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.5 | S1 Zero-shot | 66.34 | - | - | - | - | - | - |
| GPT-5.5 Pro | S1 Zero-shot | 66.56 | - | - | - | - | - | - |
| MiMo-V2.5 | S1 Zero-shot | 68.03 | - | - | - | - | - | - |
| MiMo-V2.5 | S2 Zero-shot | 67.18 | - | - | - | - | - | - |
| Qwen3-Omni-30B-A3B-Thinking | S2 Zero-shot | 72.37 | 88.73 | 87.09 | 93.31 | 92.96 | 90.52 | 84.21 |
| Qwen3-Omni-30B-A3B-Instruct | S2 Zero-shot | 73.18 | 92.08 | 90.92 | 96.17 | 96.09 | 93.82 | 91.55 |

## Multi-Judge Fusion

| Selected judge(s) | Method | Orig. Val | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|
| Judge 11 | Best MiniCPM judge | 63.27 | 92.40 | 87.46 |
| Judge 15 | Best Qwen2.5 judge | 79.93 | 91.80 | 86.97 |
| Judge 21 | Best Qwen3 judge | 79.04 | **95.82** | **94.13** |
| Judges 16+19+21 | Hard voting | 79.22 | 94.50 | 91.59 |
| **Judges 16+19+21** | **Margin-calibrated fusion (EAPO)** | **80.82** | 94.35 | 91.41 |

The central validation result is that error-augmented SFT+DPO substantially improves controlled-error robustness for Qwen3 and MiniCPM. The independently adapted judges exhibit complementary strengths, and margin-calibrated fusion gives the strongest Original Val result while retaining high controlled-error performance.

## Official Test Results

The official Stage 1 and Stage 2 results use WAF (%). **Macro** is their arithmetic mean. The official test fusion combines Judges 11, 16, and 21; this differs from the Judges 16, 19, and 21 combination selected for the validation fusion above.

| System | Model / Judge(s) | Configuration | Stage 1 | Stage 2 | Macro |
|---|---|---|---:|---:|---:|
| Official baseline | Qwen2-Audio | Zero-shot | 36.08 | - | - |
| Official baseline | Video-LLaVA | Zero-shot | 36.76 | - | - |
| Official baseline | LLaMA-VID | Zero-shot | 36.76 | - | - |
| Official baseline | LLaVA-Next-Video | Zero-shot | 41.31 | - | - |
| Official baseline | Qwen2.5-VL | Zero-shot | 76.77 | - | - |
| Official baseline | Qwen2.5-Omni | Zero-shot | 78.74 | - | - |
| Single judge | MiniCPM-o-2.6-8B | S1 Zero-shot | 88.84 | 67.63 | 78.23 |
| Single judge | MiniCPM-o-2.6-8B | S1 Error-Aug SFT+DPO | 88.31 | 67.42 | 77.86 |
| Single judge | MiniCPM-o-2.6-8B | S1 Normal SFT+DPO | 88.81 | 68.60 | 78.70 |
| Single judge | Qwen2.5-Omni-7B | S2 Zero-shot | 84.94 | 68.47 | 76.70 |
| Single judge | Qwen2.5-Omni-7B | S2 Error-Aug SFT+DPO | 88.05 | 67.93 | 77.99 |
| Single judge | Qwen2.5-Omni-7B | S2 Normal SFT+DPO | 87.79 | 69.11 | 78.45 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Zero-shot | 90.07 | 68.44 | 79.26 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Error-Aug SFT+DPO | 90.43 | 66.93 | 78.68 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Normal SFT+DPO | 89.37 | 67.50 | 78.44 |
| Hard Voting | Judges 11+16+21 | Majority votes | 88.85 | 68.88 | 78.86 |
| Raw Fusion | Judges 11+16+21 | Raw-margin mean | 90.42 | 69.07 | 79.75 |
| **EAPO (Ours)** | **Judges 11+16+21** | **Normalized mean** | **91.56** | **69.51** | **80.54** |

The best single-judge Macro WAF is 79.26 from zero-shot Qwen3. Raw-margin fusion raises this to 79.75, while per-judge scale normalization further improves the Macro result to 80.54.
