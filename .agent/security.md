# Security standard (security-first, shift-left)

Full ref behind router §5. Read before threat-modeling, touching auth/crypto/secrets, or a security
review. Frameworks: OWASP Top 10, NIST SSDF, SSDLC. Policy note — not drift-checked.

## Core directives
- Least privilege — min perms; never root/admin when restricted works.
- Input validation — assume malicious; allow-list; output-encode (XSS); parameterized queries / ORM,
  never string-concat SQL.
- Secrets — never hardcode; pull from vault / env (AWS Secrets Mgr, Azure Key Vault, HashiCorp Vault).
- Crypto — no homemade; passwords = Argon2id / bcrypt / PBKDF2; transit = TLS 1.3 + HSTS.
- Logging/errors — never leak stack traces, paths, raw SQL, PII to users; log security events
  (login fail, privilege change) but scrub secrets.

## High-risk seams (look here first)
- Auth/authz + sanitization at every trust boundary, esp. user input → service / query / deserializer.
- Missing CORS/CSRF, rate-limiting, security headers.
- Insecure deserialization; unvalidated redirects; client-side direct DB access.
- Credential/secret handling at integration points (SDKs, queues, APIs).

## SSDLC
- Design = STRIDE before complex features → file as decision record / howto note:
  Spoofing→strong authn · Tampering→integrity/signatures · Repudiation→audit logs ·
  Info disclosure→access control + encryption · DoS→rate-limit/redundancy · Elevation→strict authz.
- Impl = SAST mindset: self-review vs OWASP Top 10 before presenting.
- Deps = SCA mindset: reputable libs; monitor CVEs; record notable dep choices in integrations.md.

## Enforcement
- Asked to violate → clear Security Warning (risk + secure alt), then proceed per my call.
- Review = security flaws at top severity w/ critical bugs. Focused non-review task → flag adjacent
  flaws, don't fix out of scope (router §5).

## This repo — known posture (see gaps.md for live items)
- DEMO INTENT: deliberately ingests/moderates malicious prompts (is_malicious demo corpus, RAG
  injection content). That is the PRODUCT. Lakera Guard moderates input + output + tool results.
- No auth on backend API at all (single-user local demo). Admin console = anyone on localhost.
- API keys (openai/lakera/litellm) stored PLAINTEXT in SQLite. Export can include them (opt-in, off
  by default via SAFE_DEFAULT_INCLUDE). Acceptable for local demo, NOT for shared deploy.
- Real (non-demo) holes to respect: zip-slip in /api/config/import, weak upload content-type
  allow-list, module-global cross-session state. Flag don't fix unless in scope.
