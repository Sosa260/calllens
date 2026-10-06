import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app.py")


class DashboardTests(unittest.TestCase):
    def test_demo_and_benchmark(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        next(b for b in app.button if b.label == "Evaluate call").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "Resolved")
        next(b for b in app.button if b.label == "Run offline benchmark").click().run()
        self.assertEqual(len(app.exception), 0)

    def test_changed_input_hides_old_report(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        next(b for b in app.button if b.label == "Evaluate call").click().run()
        app.text_area[0].set_value("Customer: Hello\nAgent: Hello").run()
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("Inputs have changed" in i.value for i in app.info))


if __name__ == "__main__":
    unittest.main()
