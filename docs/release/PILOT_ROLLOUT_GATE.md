# KaushalWatch — real-centre pilot acceptance gate

This milestone follows the four completed officer OS/CRM sprints. The new gate combines current configuration, HTTPS staging, database and field-dossier checks. It generates a bounded, non-sensitive JSON readiness receipt. It never starts or certifies a real deployment.

## One private, repeatable operator workflow

1. Provision one or more approved real centres in the private versioned KW_CENTRE_REGISTRY_V1 setting. Provision centre-scoped OIDC grants, PostgreSQL with schema v3, private S3/KMS evidence custody, protected Next.js sessions, and the separate private Camera Trust worker with its SHA-pinned Drive manifest and centre-source grants. None of the files, recordings, credentials or subjects belong in Git.
2. Use the approved secret manager to supply environment variables to a secured operator runtime; do not paste full production .env values into chat or public CI.
3. Run the offline status command: python scripts/check_pilot_rollout.py --status. This does not access any service or inspect private files.
4. Once an actual deployment and independently signed field evidence exist, run the following command using real HTTPS origins, not localhost or placeholder endpoints:

    python scripts/migrate_postgres.py --check

    python scripts/check_pilot_rollout.py --api https://api.example.org --web https://officers.example.org --probe-database --field-bundle /secure/field/review.json --trusted-public-keys /secure/field/trusted-keys.json --output /secure/receipts/pilot.json

5. A signed field dossier must use KW_CAMERA_FIELD_REVIEW_V1 and three distinct, separately trusted Ed25519 public keys. The frozen measurement and policy validator is the existing evaluation/camera_trust_field_review.py. Raw videos are never read by this gate.
6. The output is created with exclusive-create mode and private user permissions (0600); it refuses a path anywhere inside the repository. It contains checks and blockers only. No camera source names, Drive IDs, URLs, access tokens, DB credentials, field images or individual trainee data are included.

## What a PASS means

The acceptance receipt uses the exact schema KW_PILOT_ACCEPTANCE_V1. A full technical PASS requires configured approved source grants and worker credentials, a live PostgreSQL schema probe, a real HTTPS API and browser check, and independently signed field evidence meeting a pre-registered policy. Even if these pass, pilot_activation remains BLOCKED_PENDING_EXTERNAL_AUTHORIZATION, autonomous_enforcement_authorized remains false, and physical_camera_health remains UNKNOWN.

External authorization must be recorded and verified outside this script, including real SSO MFA and subject revocation, S3/KMS IAM inspection, disaster recovery, source custody, false-alert burden, operator latency and independent field truth. The software cannot certify these from a runtime environment variable or CI simulation.

## CI and rollout boundaries

The CI suite exercises unsafe transport, missing signed evidence, fake signatures, withheld grants, non-secret receipts, and versioned source-registry isolation. Passing synthetic CI cannot claim real pilot readiness. The prior private worker and dashboard still run in shadow/officer-review mode, with no automatic sanction or compliance incident mutation.

No additional UI modules were added. Officer navigation remains KaushalAI, Centres, Insights, Actions. Real centre pilot setup is a controlled deployment operation, not a demo-video re-upload workflow. Research drafts remain unmerged.
