import tempfile
import unittest
from pathlib import Path

from env_doctor import audit, update_example


class EnvDoctorTests(unittest.TestCase):
    def test_audit_finds_missing_and_unused_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                'url = os.getenv("DATABASE_URL")\nkey = os.environ["API_KEY"]\n', encoding="utf-8"
            )
            (root / ".env.example").write_text("API_KEY=\nOLD_TOKEN=\n", encoding="utf-8")
            (root / ".env").write_text("DATABASE_URL=postgres://local\n", encoding="utf-8")
            report = audit(root)
            self.assertEqual(report.referenced, ["API_KEY", "DATABASE_URL"])
            self.assertEqual(report.missing_from_example, ["DATABASE_URL"])
            self.assertEqual(report.missing_from_env, ["API_KEY"])
            self.assertEqual(report.unused_in_example, ["OLD_TOKEN"])

    def test_update_example_never_copies_a_local_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("SECRET_TOKEN=do-not-copy\n", encoding="utf-8")
            self.assertTrue(update_example(root, ["SECRET_TOKEN"]))
            self.assertEqual((root / ".env.example").read_text(encoding="utf-8"), "# Added by Env Doctor\nSECRET_TOKEN=\n")


if __name__ == "__main__":
    unittest.main()
