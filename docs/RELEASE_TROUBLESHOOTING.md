# Release troubleshooting

| Status / symptom | Meaning | Safe next step |
| --- | --- | --- |
| `BLOCKED` signer inputs | One or more authorized local signer names are unavailable | Have the key owner restore the existing key and passwords through the approved secret manager; never guess or create a replacement. |
| signer fingerprint mismatch | The keystore does not match the immutable version epoch | Stop. Recover the original identity or investigate the alias/keystore with the authorized owner; never edit the pin to match. |
| version high-water failure | Candidate code is not higher than every verified/observed version | Reconcile the ledger and reserve a fresh code through a reviewed change; do not rewrite delivered records. |
| source baseline failure | Candidate does not descend from the latest verified release source | Recover the correct source ancestry; do not tag an unrelated main commit. |
| authentication asset failure | The explicitly authorized runtime asset pair is absent, malformed or mismatched | Restore the authorized local inputs via their existing protected path; do not package a source-only APK as complete. |
| output already exists | APK/report/checksum path is immutable | Choose a new eligible version/output path; do not overwrite. |
| GitHub auto-merge blocked | Auto-merge setting, branch proof, author, checks, review policy, or risk classification did not satisfy all gates | Review the reported category; leave high-risk PRs for human review and do not weaken rules. |
| Draft verification blocked | Intent, tag/source, CI, APK proof or metadata-only Draft is absent/mismatched | Use only the authenticated protected-main publisher after its gates pass. The local tool does not create a Release. |

Local detail logs are redacted and confined to ignored `.private/release-logs/`. Never paste a raw Gradle/GitHub diagnostic that may contain environment values. GitHub Actions logs must be checked for secret masking and only the failure category/public certificate fingerprint reported.
