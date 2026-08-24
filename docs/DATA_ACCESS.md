# Data Lineage and Access Guide

## What EAPO-EmoPrefer Extends

EAPO-EmoPrefer is the controlled-error extension released with *Learning to Prefer Reliably: Error-Augmented Emotion Preference Optimization with Calibrated Fusion*. It starts from the human-annotated pairwise emotion descriptions in [EmoPrefer](https://github.com/zeroQiaoba/AffectGPT/tree/master/EmoPrefer). The original human preference identifies which description is used as the preferred anchor; EAPO then constructs up to four localized controlled negatives for that anchor.

The corresponding source clips are part of [MER2025](https://huggingface.co/datasets/MERChallenge/MER2025). They are not included in this repository.

```text
MER2025 audio/video clip
          ↑ join by sample_id
EmoPrefer: a1 + a2 + human preference
          ↓ select preferred anchor
EAPO: controlled negative + edit/verification metadata
```

## What Is Included

- Generated controlled negatives for Emotion Flip, Intensity Mismatch, Evidence Contradiction, and Modality Omission.
- The selected preferred text anchor and stable `sample_id` needed to interpret each edit relation.
- Structured edit plans, automatic validation metrics, and model-verification metadata.
- Preference-pair exports for the controlled-error portion of the experiments.

## What Is Not Included

- MER2025 video or audio files.
- A grant of access to MER2025.
- Permission to redistribute or modify upstream media or annotations.
- SFT/DPO checkpoints or the complete judge-training code.

## Access and Use Procedure

1. Clone this repository to obtain the controlled-error annotations and construction code.
2. Obtain the original EmoPrefer and EmoPrefer-Data-V2 annotations from the upstream EmoPrefer repository. These are needed to reconstruct the original-only baselines and the complete original-plus-augmented training set.
3. Log in to Hugging Face and request access to MER2025. Review and accept the current EULA, provide the requested contact information, and wait for approval from the dataset owner.
4. After approval, follow `README_AFTER_APPROVAL.md` in the MER2025 repository to download the source media.
5. Keep the media in an authorized local location. Match an EAPO record to its clip using `sample_id`; do not upload the joined corpus or source media back to this repository.
6. Review `DATA_LICENSE.md` and the current upstream terms before publishing derived data or redistributing any files.

## Count Relationship

After the paper's binary filtering and tie removal, the normal training and validation sets contain 1,618 EmoPrefer-Data-V2 pairs and 563 EmoPrefer-Data pairs. EAPO contributes a separate 2,908 generated training pairs and 944 generated validation pairs. Thus, the Error-Aug sets report only newly generated controlled-error pairs; they do not include the original EmoPrefer pairs.

## Text-Only Construction Versus Multimodal Use

The released Edit Planner and Verifier operate on the preferred and modified descriptions only. They do not load the corresponding audio/video clip. Consequently, regenerating controlled text edits does not require media paths once authorized source annotations have been prepared. Training or evaluating a multimodal preference judge does require the MER2025 clip associated with each `sample_id`.

## Citation

If EAPO controlled annotations are used, cite the EAPO paper. Because the source preference annotations are inherited from EmoPrefer, also cite *EmoPrefer: Can Large Language Models Understand Human Emotion Preferences?* Follow the MER2025 dataset card for the required dataset citation whenever its media are used.
