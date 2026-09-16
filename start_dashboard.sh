#!/usr/bin/env bash
# Railway sadece ortam degiskeni sunar, dosya sunmaz; ama st.login() sirlari
# .streamlit/secrets.toml DOSYASINDAN okur, ortam degiskeninden degil. Bu
# betik container her baslarken o dosyayi Railway'in ortam degiskenlerinden
# uretir, sonra Streamlit'i baslatir. Dosya diske sadece calisirken yazilir,
# repoya hic girmez.
set -euo pipefail

mkdir -p .streamlit
cat > .streamlit/secrets.toml << SECRETS
[auth]
redirect_uri = "${REDIRECT_URI}"
cookie_secret = "${COOKIE_SECRET}"
client_id = "${AUTH0_CLIENT_ID}"
client_secret = "${AUTH0_CLIENT_SECRET}"
server_metadata_url = "https://${AUTH0_DOMAIN}/.well-known/openid-configuration"
SECRETS

exec streamlit run bist_screener/app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true
