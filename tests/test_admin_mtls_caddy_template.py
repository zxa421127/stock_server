from pathlib import Path


TEMPLATE = Path("deploy/windows/caddy/templates/stock-server-four-hosts.Caddyfile")
PRODUCTION_TEMPLATE = Path("deploy/windows/caddy/templates/Caddyfile.production.template")


def _text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _site_block(text: str, host: str) -> str:
    marker = f"\n{host} {{"
    start = text.index(marker) + 1
    next_starts = [
        text.find(f"\n{candidate} {{", start + 1)
        for candidate in (
            "api.lifesupermarket.cn",
            "admin-api.lifesupermarket.cn",
            "test-api.lifesupermarket.cn",
            "test-admin-api.lifesupermarket.cn",
        )
    ]
    next_starts = [value + 1 for value in next_starts if value >= 0]
    end = min(next_starts) if next_starts else len(text)
    return text[start:end]


def test_caddy_template_has_four_isolated_stock_server_hosts():
    text = _text()
    for host in (
        "api.lifesupermarket.cn",
        "admin-api.lifesupermarket.cn",
        "test-api.lifesupermarket.cn",
        "test-admin-api.lifesupermarket.cn",
    ):
        assert f"{host} {{" in text
    assert "lifesupermarket.cn, www.lifesupermarket.cn" not in text


def test_caddy_public_hosts_block_admin_and_strip_trusted_headers():
    text = _text()
    for host, upstream in (
        ("api.lifesupermarket.cn", "127.0.0.1:8899"),
        ("test-api.lifesupermarket.cn", "127.0.0.1:8898"),
    ):
        block = _site_block(text, host)
        assert "path /admin /admin/*" in block
        assert "respond @admin_paths 404" in block
        assert f"reverse_proxy {upstream}" in block
        assert "header_up -X-Admin-*" in block
        assert "X-Admin-Proxy-Auth" not in block.replace("header_up -X-Admin-*", "")


def test_caddy_admin_hosts_require_separate_client_ca_and_forward_der():
    text = _text()
    expectations = (
        (
            "admin-api.lifesupermarket.cn",
            "127.0.0.1:8899",
            "REPLACE_PROD_ADMIN_CA_FILE",
            "REPLACE_PROD_ADMIN_PROXY_SECRET",
        ),
        (
            "test-admin-api.lifesupermarket.cn",
            "127.0.0.1:8898",
            "REPLACE_TEST_ADMIN_CA_FILE",
            "REPLACE_TEST_ADMIN_PROXY_SECRET",
        ),
    )
    for host, upstream, ca_placeholder, secret_placeholder in expectations:
        block = _site_block(text, host)
        assert "mode require_and_verify" in block
        assert f"trust_pool file {ca_placeholder}" in block
        assert "path /admin /admin/* /static /static/*" in block
        assert f"reverse_proxy @admin_allowed {upstream}" in block
        # Admin hosts must not use a broad X-Admin-* deletion in the same
        # reverse_proxy block where trusted X-Admin-* values are injected.
        # The broad deletion is retained only on public API hosts.
        assert "header_up -X-Admin-*" not in block
        assert "header_up -X-Admin-Client-Cert" in block
        assert f'header_up X-Admin-Proxy-Auth "{secret_placeholder}"' in block
        assert 'header_up X-Admin-Client-Cert-Verify "SUCCESS"' in block
        assert 'header_up X-Admin-Client-Cert-DER "{tls_client_certificate_der_base64}"' in block
        assert 'header_up X-Admin-Client-Cert-Fingerprint "{tls_client_fingerprint}"' in block
        assert 'header_up X-Admin-Client-Cert-Serial "{tls_client_serial}"' in block
        assert 'header_up X-Admin-Client-Cert-Subject "{tls_client_subject}"' in block
        assert "respond 404" in block


def test_caddy_admin_hosts_do_not_reintroduce_broad_trusted_header_deletion():
    text = _text()
    for host in ("admin-api.lifesupermarket.cn", "test-admin-api.lifesupermarket.cn"):
        block = _site_block(text, host)
        assert "header_up -X-Admin-*" not in block
        assert "header_up -X-Admin-Client-Cert" in block


def test_caddy_template_keeps_test_and_production_placeholders_distinct():
    text = _text()
    assert text.count("REPLACE_PROD_ADMIN_CA_FILE") == 1
    assert text.count("REPLACE_TEST_ADMIN_CA_FILE") == 1
    assert text.count("REPLACE_PROD_ADMIN_PROXY_SECRET") == 1
    assert text.count("REPLACE_TEST_ADMIN_PROXY_SECRET") == 1

def test_production_template_admin_hosts_follow_trusted_header_contract():
    text = PRODUCTION_TEMPLATE.read_text(encoding="utf-8-sig")
    assert "lifesupermarket.cn, www.lifesupermarket.cn" in text
    expectations = (
        (
            "admin-api.lifesupermarket.cn",
            "127.0.0.1:8899",
            "{{PROD_ADMIN_PROXY_AUTH}}",
        ),
        (
            "test-admin-api.lifesupermarket.cn",
            "127.0.0.1:8898",
            "{{TEST_ADMIN_PROXY_AUTH}}",
        ),
    )
    for host, upstream, secret_placeholder in expectations:
        block = _site_block(text, host)
        assert "mode require_and_verify" in block
        assert f"reverse_proxy @admin_allowed {upstream}" in block
        assert "request_header @admin_allowed -X-Admin-*" not in block
        assert "header_up -X-Admin-*" not in block
        assert "header_up -X-Admin-Client-Cert" in block
        assert f'header_up X-Admin-Proxy-Auth "{secret_placeholder}"' in block
        assert 'header_up X-Admin-Client-Cert-Verify "SUCCESS"' in block
        assert 'header_up X-Admin-Client-Cert-DER "{tls_client_certificate_der_base64}"' in block
        assert 'header_up X-Admin-Client-Cert-Fingerprint "{tls_client_fingerprint}"' in block
        assert 'header_up X-Admin-Client-Cert-Serial "{tls_client_serial}"' in block
        assert 'header_up X-Admin-Client-Cert-Subject "{tls_client_subject}"' in block
