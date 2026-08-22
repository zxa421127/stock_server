# Security remediation and deployment runbook

## Mandatory external credential rotation

Before deploying this version, revoke and replace every credential that appeared in any prior source archive: Flask `SECRET_KEY`, administrator password/hash, API-token HMAC secret, audit HMAC secret, contact-verification HMAC secret, administrator proxy secret, Tushare token, Kaipanla token/device credentials, Feishu app secret, SMTP password and SMS webhook secret. Rotating `SECRET_KEY` intentionally invalidates all existing browser sessions.

Run the legacy-token tool against a backup copy first, then the production database:

```bash
python -m tools.security.revoke_legacy_api_tokens --db /path/to/tokens.db --dry-run
python -m tools.security.revoke_legacy_api_tokens --db /path/to/tokens.db --confirm REVOKE-LEGACY
```

## Database and configuration deployment

1. Back up the SQLite database and stop web/worker processes.
2. Run the project database migration tool once under the service account.
3. Configure production secrets outside the source directory.
4. Enable Redis and contact verification. SMTP is required when SMS is disabled.
5. For a custom Tushare relay, use HTTPS and list its exact hostname in `TUSHARE_ALLOWED_RELAY_HOSTS`.
6. Run `python -m tools.production_preflight` before starting web or workers.
7. Start the web service only on loopback behind the supplied Nginx HTTPS/mTLS configuration.

## Release process

```bash
python -m tools.release.build_production_package --output dist/stock-server-production.zip
python -m tools.security.scan_release_secrets dist/stock-server-production.zip
```

The builder is allow-list based and excludes runtime databases, `.env`, virtual environments, logs, IDE metadata, private keys and certificates. It writes `RELEASE_MANIFEST.json` and `SHA256SUMS.txt` into the archive.

The included `requirements.lock` pins direct dependencies. In a connected trusted build environment, regenerate a full transitive hash lock and review the diff:

```bash
uv pip compile requirements.txt --generate-hashes -o requirements.lock
python -m pip_audit -r requirements.lock --strict
```
