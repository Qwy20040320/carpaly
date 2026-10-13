from __future__ import annotations

import unittest

from scripts.verify_ota_environment import EnvironmentGateError, validate_configuration


def environment(*, reviewers=None, prevent_self_review=True):
    return {
        "name": "ota-manifest-publisher",
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
        "protection_rules": [{
            "type": "required_reviewers",
            "reviewers": reviewers if reviewers is not None else [{"type": "User", "reviewer": {"id": 1}}],
            "prevent_self_review": prevent_self_review,
        }],
    }


class OtaEnvironmentGateTests(unittest.TestCase):
    def test_accepts_main_only_environment_with_non_self_approver(self):
        validate_configuration(
            environment(), {"branch_policies": [{"name": "main", "type": "branch"}]}, 1,
        )

    def test_missing_environment_or_reviewer_fails_closed(self):
        with self.assertRaises(EnvironmentGateError):
            validate_configuration({}, {"branch_policies": [{"name": "main", "type": "branch"}]}, 1)
        with self.assertRaisesRegex(EnvironmentGateError, "reviewers"):
            validate_configuration(
                environment(reviewers=[]), {"branch_policies": [{"name": "main", "type": "branch"}]}, 1,
            )

    def test_branch_scope_and_self_review_are_enforced(self):
        with self.assertRaisesRegex(EnvironmentGateError, "only the main branch"):
            validate_configuration(
                environment(), {"branch_policies": [
                    {"name": "main", "type": "branch"}, {"name": "v1.*.*", "type": "tag"},
                ]}, 1,
            )
        with self.assertRaisesRegex(EnvironmentGateError, "self-approving"):
            validate_configuration(
                environment(prevent_self_review=False),
                {"branch_policies": [{"name": "main", "type": "branch"}]}, 1,
            )

    def test_duplicate_or_missing_reviewer_rules_fail_closed(self):
        duplicate = environment()
        duplicate["protection_rules"].append(dict(duplicate["protection_rules"][0]))
        with self.assertRaisesRegex(EnvironmentGateError, "exactly one"):
            validate_configuration(
                duplicate, {"branch_policies": [{"name": "main", "type": "branch"}]}, 1,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
