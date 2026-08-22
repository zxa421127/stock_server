from pathlib import Path


def test_nginx_uses_separate_admin_host_and_forwards_validated_certificate():
    text = Path("deploy/nginx/stock-server.conf").read_text(encoding="utf-8")
    assert "server_name api.example.com" in text
    assert "server_name admin-api.example.com" in text
    assert "ssl_verify_client on;" in text
    assert "ssl_client_certificate /etc/stock-server/pki/admin-client-ca.crt.pem;" in text
    assert "proxy_set_header X-Admin-Client-Cert $ssl_client_escaped_cert;" in text
    assert "proxy_set_header X-Admin-Proxy-Auth \"REPLACE_WITH_ADMIN_CLIENT_CERT_PROXY_SECRET\";" in text
    assert "location ^~ /admin/" in text
    assert "return 404;" in text


def test_public_virtual_host_clears_spoofable_certificate_headers():
    text = Path("deploy/nginx/stock-server.conf").read_text(encoding="utf-8")
    public = text.split("# Dedicated administrator host", 1)[0]
    assert 'proxy_set_header X-Admin-Proxy-Auth "";' in public
    assert 'proxy_set_header X-Admin-Client-Cert "";' in public
    assert 'proxy_set_header X-Admin-Client-Cert-Verify "";' in public
