import unittest
from pathlib import Path

from scripts.android_versioning import (
    check_project,
    next_test_name,
    parse_gradle_version,
    parse_version_tuple,
)


class AndroidVersioningTests(unittest.TestCase):
    def test_reads_one_base_application_and_version(self):
        parsed = parse_gradle_version(
            'defaultConfig {\n'
            '    applicationId = "com.shihab.diplay.hudtest"\n'
            '    versionCode = 39\n'
            '    versionName = "1.1.51"\n'
            '}\n'
        )
        self.assertEqual("com.shihab.diplay.hudtest", parsed.application_id)
        self.assertEqual("1.1.51", parsed.version_name)
        self.assertEqual(39, parsed.version_code)

    def test_test_versions_increment_without_reusing_the_previous_name(self):
        self.assertEqual("1.1.52", next_test_name("1.1.51"))
        self.assertEqual("1.1.100", next_test_name("1.1.99"))

    def test_next_test_requires_the_test_sequence(self):
        for version in ("1.1.5", "1.1.6", "1.2.51", "not-a-version"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                next_test_name(version)

    def test_numeric_version_parser(self):
        self.assertEqual((1, 1, 51), parse_version_tuple("1.1.51"))
        self.assertIsNone(parse_version_tuple("v1.1.51"))

    def test_repository_reservation_matches_monotonic_project_version(self):
        root = Path(__file__).resolve().parents[1]
        version = check_project(root)
        self.assertEqual("1.1.51", version.version_name)
        self.assertEqual(39, version.version_code)


if __name__ == "__main__":
    unittest.main()
