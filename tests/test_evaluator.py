import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from evaluator import baseline, csv_report, finalize, word_error_rate
from provider import Evaluation, evaluate_live, transcribe


class EvaluationTests(unittest.TestCase):
    def test_synthetic_regressions(self):
        calls = json.loads((Path(__file__).parents[1] / "data/calls.json").read_text())
        for call in calls:
            with self.subTest(call=call["id"]):
                result = baseline(call["transcript"])
                self.assertEqual(result["outcome"], call["expected_outcome"])
                self.assertEqual(result["intent"], call["expected_intent"])

    def test_missing_speakers_stays_unknown(self):
        result = baseline("The call recording was inaudible.")
        self.assertIsNone(result["quality_percent"])
        self.assertEqual(result["coverage"], 0)
        self.assertEqual(result["outcome"], "unknown")

    def test_blank_and_oversize(self):
        for text in [" ", "x" * 30001]:
            with self.assertRaises(ValueError):
                baseline(text)

    def test_wer(self):
        self.assertEqual(word_error_rate("Customer: HELLO, world!", "hello world")["word_error_rate"], 0)
        self.assertEqual(word_error_rate("one two three", "one three")["word_edits"], 1)
        self.assertEqual(word_error_rate("one two", "one four")["word_error_rate"], .5)
        self.assertEqual(word_error_rate("one", "one two three")["word_error_rate"], 2)
        self.assertEqual(word_error_rate("one", "")["word_error_rate"], 1)
        with self.assertRaises(ValueError):
            word_error_rate("!", "hello")

    def test_fabricated_quotes_downgraded(self):
        result = baseline("Customer: Hello\nAgent: Hello")
        result["rubric"][0].update(score=2, evidence="Fabricated")
        result.update(outcome="resolved", outcome_evidence="Fabricated")
        checked = finalize(result, result["transcript"])
        self.assertIsNone(checked["rubric"][0]["score"])
        self.assertEqual(checked["outcome"], "unknown")

    def test_csv_formula_injection(self):
        result = baseline("Customer: Hello\nAgent: Hello")
        result["rubric"][0]["reason"] = " =1+1"
        self.assertIn("' =1+1", csv_report(result))

    def test_provider_contract_and_refusal(self):
        text = "Customer: Hello\nAgent: Hello"
        raw = baseline(text)
        parsed = Evaluation.model_validate(raw)
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed, usage=None)
        result = evaluate_live(text, "unused", "test-model", client)
        self.assertEqual(result["model"], "test-model")
        self.assertFalse(client.responses.parse.call_args.kwargs["store"])
        client.responses.parse.return_value.output_parsed = None
        with self.assertRaises(ValueError):
            evaluate_live(text, "unused", "test-model", client)

    def test_duplicate_rubric_rejected(self):
        raw = baseline("Customer: Hello\nAgent: Hello")
        raw["rubric"][1] = raw["rubric"][0]
        with self.assertRaises(ValueError):
            Evaluation.model_validate(raw)

    def test_audio_validation_and_adapter(self):
        client = Mock()
        client.audio.transcriptions.create.return_value = SimpleNamespace(text="Hello world")
        self.assertEqual(transcribe(b"mock audio", "call.wav", "unused", "test", client), "Hello world")
        for data, name in [(b"", "call.wav"), (b"test", "call.exe"), (b"x" * (20 * 1024 * 1024 + 1), "call.mp3")]:
            with self.assertRaises(ValueError):
                transcribe(data, name, "unused", "test", client)


if __name__ == "__main__":
    unittest.main()
