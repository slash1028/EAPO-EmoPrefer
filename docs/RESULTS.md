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
| S1 Zero-shot | 61.53 | 83.97 | 47.27 | 66.26 | 80.34 | 69.46 | 53.50 |
| S1 Normal SFT | 60.79 | 84.31 | 47.04 | 66.00 | 81.17 | 69.63 | 53.92 |
| S1 Normal SFT+DPO | 60.74 | 84.31 | 45.34 | 65.69 | 81.16 | 69.12 | 53.28 |
| S1 Error-Aug SFT | 71.90 | 93.22 | 70.67 | **79.07** | **92.74** | 83.92 | 75.32 |
| **S1 Error-Aug SFT+DPO** | **73.89** | **94.95** | **79.63** | 78.65 | 91.11 | **86.09** | **76.27** |

## Qwen2.5-Omni-7B

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 Zero-shot | 68.17 | 83.32 | 49.30 | 51.82 | 47.59 | 58.01 | 34.96 |
| S2 Normal SFT | 77.08 | 86.44 | 51.35 | 62.57 | **80.48** | 70.21 | 53.18 |
| S2 Normal SFT+DPO | 77.25 | 90.49 | 59.45 | 65.90 | 74.33 | 72.54 | 57.10 |
| S2 Error-Aug SFT | 77.15 | 94.32 | **67.13** | 68.58 | 78.49 | **77.13** | 64.41 |
| **S2 Error-Aug SFT+DPO** | **78.29** | **94.79** | 65.77 | **72.03** | 74.96 | 76.89 | **65.36** |

## Qwen3-Omni-30B-A3B-Instruct

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 Zero-shot | 73.43 | 87.06 | 52.29 | 63.49 | 77.75 | 70.15 | 54.13 |
| S2 Normal SFT | 75.65 | 86.25 | 40.66 | 67.73 | 78.48 | 68.28 | 56.46 |
| S2 Normal SFT+DPO | 77.78 | 92.59 | 53.76 | 68.85 | 84.92 | 75.03 | 66.21 |
| S2 Error-Aug SFT | 76.56 | 92.74 | 61.64 | 71.48 | 76.79 | 75.66 | 65.47 |
| **S2 Error-Aug SFT+DPO** | **79.04** | **95.74** | **71.48** | **75.70** | **92.73** | **83.91** | **75.74** |

## Additional Zero-Shot Judges

| Model | Strategy | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.5 | S1 Zero-shot | 66.34 | - | - | - | - | - | - |
| GPT-5.5 Pro | S1 Zero-shot | 66.56 | - | - | - | - | - | - |
| MiMo-V2.5 | S1 Zero-shot | 68.03 | - | - | - | - | - | - |
| MiMo-V2.5 | S2 Zero-shot | 67.18 | - | - | - | - | - | - |
| Qwen3-Omni-30B-A3B-Thinking | S2 Zero-shot | 73.36 | 92.27 | 54.51 | 71.20 | 65.95 | 70.98 | 62.29 |
| Qwen3-Omni-30B-A3B-Instruct | S2 Zero-shot | 73.43 | 87.06 | 52.29 | 63.49 | 77.75 | 70.15 | 54.13 |

## Multi-Judge Fusion

| Selected judge(s) | Method | Orig. Val | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|
| Judge 11 | Best MiniCPM judge | 73.89 | **86.09** | 76.27 |
| Judge 16 | Best Qwen2.5 judge | 78.29 | 76.89 | 65.36 |
| Judge 21 | Best Qwen3-Omni judge | 79.04 | 83.91 | 75.74 |
| Judges 11+14+21 | Hard voting | 78.96 | 84.44 | 74.79 |
| **Judges 11+14+21** | **Margin-calibrated fusion (EAPO)** | **80.31** | 85.35 | **76.38** |

The updated controlled-error set is substantially more difficult than the earlier diagnostic version. Error-augmented SFT+DPO improves controlled-error robustness for Qwen3 and MiniCPM, while the independently adapted judges retain complementary strengths. Margin-calibrated fusion gives the strongest Original Val result and improves over hard voting on both 4-Error Avg and Swap Cons.

## Official Test Results

The official Stage 1 and Stage 2 results use WAF (%). **Macro** is their arithmetic mean. The official test fusion combines Judges 11, 16, and 21; this differs from the Judges 11, 14, and 21 combination selected for the validation fusion above.

| System | Model / Judge(s) | Configuration | Stage 1 | Stage 2 | Macro |
|---|---|---|---:|---:|---:|
| Official baseline | Qwen2-Audio | Zero-shot | 36.08 | - | - |
| Official baseline | Video-LLaVA | Zero-shot | 36.76 | - | - |
| Official baseline | LLaMA-VID | Zero-shot | 36.76 | - | - |
| Official baseline | LLaVA-Next-Video | Zero-shot | 41.31 | - | - |
| Official baseline | Qwen2.5-VL | Zero-shot | 76.77 | - | - |
| Official baseline | Qwen2.5-Omni | Zero-shot | 78.74 | - | - |
| Single judge | MiniCPM-o-2.6-8B | S1 Zero-shot | 87.34 | 66.13 | 76.73 |
| Single judge | MiniCPM-o-2.6-8B | S1 Normal SFT+DPO | 86.81 | 65.92 | 76.36 |
| Single judge | MiniCPM-o-2.6-8B | S1 Error-Aug SFT+DPO | 85.97 | 65.88 | 75.92 |
| Single judge | Qwen2.5-Omni-7B | S2 Zero-shot | 83.44 | 66.97 | 75.20 |
| Single judge | Qwen2.5-Omni-7B | S2 Normal SFT+DPO | 86.55 | 66.43 | 76.49 |
| Single judge | Qwen2.5-Omni-7B | S2 Error-Aug SFT+DPO | 87.18 | 66.37 | 76.77 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Zero-shot | 88.57 | 66.94 | 77.76 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Normal SFT+DPO | 88.93 | 67.43 | 78.18 |
| Single judge | Qwen3-Omni-30B-A3B | S2 Error-Aug SFT+DPO | 90.25 | 68.56 | 79.40 |
| Hard Voting | Judges 11+16+21 | Majority votes | 88.93 | 68.02 | 78.47 |
| Raw Fusion | Judges 11+16+21 | Raw-margin mean | 89.98 | 68.63 | 79.31 |
| **EAPO (Ours)** | **Judges 11+16+21** | **Normalized mean** | **91.30** | **69.17** | **80.23** |

The best single-judge Macro WAF is 79.40 from Qwen3 Error-Aug SFT+DPO. Raw-margin fusion reaches 79.31, while per-judge scale normalization improves the Macro result to 80.23.
