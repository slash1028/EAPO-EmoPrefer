from __future__ import annotations

import unittest

from eapo_emoprefer import generate


PREFERRED = (
    'In the text, the subtitle says, "Look at yourself now." '
    "This sentence may be a comment or reaction to the individual's current state. "
    "Based on the description of the individual's tense and anxious voice characteristics in the audio clues, "
    "as well as the serious expression and body language of the woman in the video clues, we can infer that this "
    "sentence may carry a tone of criticism or concern. Therefore, this sentence may be pointing out the "
    "individual's current negative state or expressing concern about their emotions."
)


class ControlledRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {"name": "sample", "a1": "rejected", "a2": PREFERRED, "preference": "a2"}
        self.plan = {
            "type": "emotion_flip",
            "sentence_id": "S3",
            "source_phrase": "we can infer that this sentence may carry a tone of criticism or concern",
            "replacement_phrase": "we can infer that this sentence may carry a tone of empathy or reassurance",
            "target_modality": "global",
            "emotion_before": "criticism or concern",
            "emotion_after": "empathy or reassurance",
            "intensity_preserved": True,
            "evidence_preserved": True,
            "rationale": "Local emotion inference flip.",
        }

    def test_valid_emotion_flip(self) -> None:
        errors, candidate, metrics = generate.validate_plan(
            self.row, "emotion_flip", self.plan, 60, 60, 0.45, 1
        )
        self.assertEqual(errors, [])
        self.assertIn("empathy or reassurance", candidate)
        self.assertIn("tense and anxious voice", candidate)
        self.assertEqual(metrics["length_delta"], 0)

    def test_emotion_flip_rejects_non_global_target(self) -> None:
        invalid = dict(self.plan, target_modality="audio")
        errors, _, _ = generate.validate_plan(
            self.row, "emotion_flip", invalid, 60, 60, 0.45, 1
        )
        self.assertIn("target_modality must be global for emotion_flip", errors)

    def test_verifier_gate(self) -> None:
        response = """{
          "assessments": [{
            "requested_type": "emotion_flip",
            "observed_type": "emotion_flip",
            "targeted_error_present": true,
            "non_target_preserved": true,
            "fluent": true,
            "quality_score": 5,
            "notes": "Clean local flip."
          }]
        }"""
        errors, assessments = generate.parse_corrected_verification(response, ["emotion_flip"])
        self.assertEqual(errors, [])
        self.assertTrue(assessments["emotion_flip"]["pass"])


if __name__ == "__main__":
    unittest.main()
