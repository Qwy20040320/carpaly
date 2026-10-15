# GitHub Auto-merge policy

The local orchestrator may request only GitHub-native `gh pr merge --auto --merge`. It does not merge directly, enable Auto-merge in repository settings, approve a PR, dismiss reviews, or bypass a ruleset.

Eligibility is fail-closed and requires the configured repository/account, an open non-Draft same-repository PR to `main`, exact unchanged head/check SHA, mergeability, resolved review threads, trusted PR author and authenticated requester, successful live required checks, active main protection with PR/status rules, no bypass actors or force-push/deletion allowance, and the selected maintainer policy. Any high-risk workflow, signer, version-ledger, Release, or Gradle change requires human review and remains Draft. Multi-maintainer mode additionally requires independent approval(s) on the current PR head and a ruleset at least as strict as the policy.

The repository currently reports Auto-merge disabled; the local tool will report `BLOCKED` and will not alter Settings. If maintainers later choose native Auto-merge, an administrator must enable it in **Settings → General → Pull Requests → Allow auto-merge**, after reviewing branch protection and the maintainer policy. This is a manual security decision. Required CI and protections stay authoritative; do not enable bypass actors or auto-approve automation.
