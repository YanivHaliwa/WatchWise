#!/bin/bash

CLIENT_ID="${TRAKT_CLIENT_ID:-}"
CLIENT_SECRET="${TRAKT_CLIENT_SECRET:-}"

if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "❌ Error: Please set TRAKT_CLIENT_ID and TRAKT_CLIENT_SECRET environment variables."
  exit 1
fi

echo "📡 Requesting device code from Trakt..."

response=$(curl -s -X POST https://api.trakt.tv/oauth/device/code \
  -H "Content-Type: application/json" \
  -d "{\"client_id\": \"$CLIENT_ID\"}")

user_code=$(echo "$response" | jq -r .user_code)
device_code=$(echo "$response" | jq -r .device_code)
verification_url=$(echo "$response" | jq -r .verification_url)
interval=$(echo "$response" | jq -r .interval)

echo "🟢 Go to: $verification_url"
echo "🔑 Enter code: $user_code"
read -p "Press Enter when you've authorized the app..."

echo "⏳ Polling Trakt for access token..."
while true; do
  token_response=$(curl -s -X POST https://api.trakt.tv/oauth/device/token \
    -H "Content-Type: application/json" \
    -d "{
      \"code\": \"$device_code\",
      \"client_id\": \"$CLIENT_ID\",
      \"client_secret\": \"$CLIENT_SECRET\"
    }")

  if echo "$token_response" | grep -q access_token; then
    access_token=$(echo "$token_response" | jq -r .access_token)
    refresh_token=$(echo "$token_response" | jq -r .refresh_token)

    ZSHRC="$HOME/.zshrc"
    sed -i "s|^export TRAKT_ACCESS_TOKEN=.*|export TRAKT_ACCESS_TOKEN=\"$access_token\"|" "$ZSHRC"
    sed -i "s|^export TRAKT_REFRESH_TOKEN=.*|export TRAKT_REFRESH_TOKEN=\"$refresh_token\"|" "$ZSHRC"

    export TRAKT_ACCESS_TOKEN="$access_token"
    export TRAKT_REFRESH_TOKEN="$refresh_token"

    echo "✅ Tokens updated in $ZSHRC and exported to current shell"
    break
  elif echo "$token_response" | grep -q "authorization_pending"; then
    sleep "$interval"
  else
    echo "❌ Error:"
    echo "$token_response"
    break
  fi
done
