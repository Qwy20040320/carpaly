# V1.1.57 Release signer policy audit

## Result

`SIGNER_POLICY_REVIEW_REQUIRED` — no Release signer was selected and no V1.1.57
APK was built. The conflicting policy sources have not been edited to make the
checks pass.

## Evidence

- The supplied/current `AGENTS.md` and `docs/RELEASE_SIGNING_POLICY.md` pin
  user-installable APKs to certificate SHA-256
  `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`.
- The V1.1.56 version ledger and merged Release build configuration record
  `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` for
  version codes 41 onward. The local V1.1.56 APK was previously verified as
  package `com.shihab.diplay.hudtest`, version 1.1.56/code 44, non-debuggable,
  signed with this `d9b329…` certificate.
- The ledger records versions 1.1.53–1.1.56 in the newer signer epoch, while
  the checked-in permanent policy still requires the legacy signer. No Android
  proof-of-rotation/signing lineage authorizing a transition between these
  signers is present.
- `scripts/android_versioning.py check` fails closed because the ledger does
  not match the permanent Release APK delivery policy. The same mismatch causes
  repository-level versioning tests to stop before checking allocation
  behavior.
- Target version 1.1.57/code 45 is not allocated in the current ledger. The
  release intent remains disabled.

## Safety decision

Do not sign with either certificate until the project owner reconciles the
policy with evidence for the actual installed/released upgrade chain. A 4d
signature cannot be represented as an in-place upgrade over a d9-signed
V1.1.56 installation without a valid Android signing lineage. Do not uninstall
the installed app, clear its data, create a replacement key, or edit the
certificate pin to silence the check.

No keystore, password, private key, DPAPI content, or production Secret was
read, decrypted, changed, or printed in this audit.

## Required resolution

The maintainer must explicitly choose and document the intended signer/upgrade
path, backed by the original authorized signing material and, if applicable,
Android-verifiable signing-lineage evidence. After that policy is approved,
update the policy, ledger, verifier tests, and version allocation together; then
run the version checks and signer preflight before any Release build.
