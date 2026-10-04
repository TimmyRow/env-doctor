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
            self.assertFalse(update_example(root, []))

    def test_javascript_and_compose_ignore_comments_and_example_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.ts").write_text(
                '// process.env.COMMENTED\n'
                'const example = "process.env.STRING_ONLY";\n'
                'const url = process.env.API_URL;\n'
                'const secret = process.env["SECRET_KEY"];\n'
                'const mode = import.meta.env.MODE;\n', encoding="utf-8"
            )
            (root / "compose.yaml").write_text(
                '# ${COMMENTED_COMPOSE}\n'
                'services:\n  api:\n    image: "${IMAGE_NAME:-my-app}"\n', encoding="utf-8"
            )
            report = audit(root)
            self.assertEqual(report.referenced, ["API_URL", "IMAGE_NAME", "SECRET_KEY"])
            self.assertEqual(report.references["API_URL"], ["app.ts:3"])
            self.assertEqual(report.references["IMAGE_NAME"], ["compose.yaml:4"])

    def test_generated_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "node_modules" / "package"
            generated.mkdir(parents=True)
            (generated / "index.js").write_text("process.env.WRONG", encoding="utf-8")
            (root / "run.sh").write_text('echo "$REAL_VALUE"\n', encoding="utf-8")
            self.assertEqual(audit(root).referenced, ["REAL_VALUE"])


if __name__ == "__main__":
    unittest.main()
