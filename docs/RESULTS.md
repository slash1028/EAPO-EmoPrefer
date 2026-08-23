# Paper-Aligned Experimental Results

This page reproduces the controlled-error validation results reported in the EAPO paper. All values are weighted F1 (WAF, %) unless stated otherwise.

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
| S1 Error-Aug SFT | 61.53 | 88.88 | 90.20 | 94.31 | 94.93 | 92.08 | 87.14 |
| **S1 Error-Aug SFT+DPO** | **63.27** | **89.29** | **90.38** | **95.10** | **94.84** | **92.40** | **87.46** |

## Qwen2.5-Omni-7B

| Setting | Orig. Val | Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg | Swap Cons |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 Zero-shot | 65.53 | 75.41 | 76.57 | 82.79 | 81.11 | 78.97 | 70.42 |
| S2 Normal SFT | 75.84 | 86.45 | 89.21 | 93.06 | 92.61 | 90.33 | 84.91 |
| S2 Normal SFT+DPO | 77.96 | 89.15 | 92.08 | 94.04 | 93.24 | 92.13 | 89.86 |
| **S2 Error-Aug SFT** | **79.93** | 88.59 | **90.46** | 94.04 | **94.13** | **91.80** | **86.97** |
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

| Model | Strategy | Orig. Val | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|
| GPT-5.5 | S1 Zero-shot | 66.34 | - | - |
| GPT-5.5 Pro | S1 Zero-shot | 66.56 | - | - |
| MiMo-V2.5 | S1 Zero-shot | 68.03 | - | - |
| MiMo-V2.5 | S2 Zero-shot | 67.18 | - | - |
| Qwen3-Omni-30B-A3B-Thinking | S2 Zero-shot | 72.37 | 90.52 | 84.21 |
| Qwen3-Omni-30B-A3B-Instruct | S2 Zero-shot | 73.18 | 93.82 | 91.55 |

## Multi-Judge Fusion

| Selected judge(s) | Method | Orig. Val | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|
| Judge 11 | Best MiniCPM judge | 63.27 | 92.40 | 87.46 |
| Judge 15 | Best Qwen2.5 judge | 79.93 | 91.80 | 86.97 |
| Judge 21 | Best Qwen3 judge | 79.04 | **95.82** | **94.13** |
| Judges 16+19+21 | Hard voting | 79.22 | 94.50 | 91.59 |
| **Judges 16+19+21** | **Margin-calibrated fusion (EAPO)** | **80.82** | 94.35 | 91.41 |

The central paper result is that error-augmented SFT+DPO substantially improves controlled-error robustness for Qwen3 and MiniCPM. The independently adapted judges exhibit complementary strengths, and margin-calibrated fusion gives the strongest Original Val result while retaining high controlled-error performance.
