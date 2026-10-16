#!/usr/bin/env bash
# Point a Railway service at an image and deploy it, then wait until the
# public URL serves that build.
#
# Usage: scripts/railway_deploy.sh <image> <public URL> <expected app version>
#   e.g. scripts/railway_deploy.sh ghcr.io/abti247/iron_verdict:sha-1a2b3c4 \
#          https://ironverdict-staging.up.railway.app sha-1a2b3c4
#
# Env: RAILWAY_TOKEN (project token of the target environment, sent as
# Project-Access-Token), RAILWAY_SERVICE_ID, RAILWAY_ENVIRONMENT_ID.
# DEPLOY_TIMEOUT_S (default 600) bounds the wait.
#
# Done means: /health answers 200 and the landing page footer shows the
# expected version. The footer is the only proof that the new image (not the
# previous deployment) answers on the public domain, so the script does not
# rely on Railway's deployment status.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <image> <public URL> <expected app version>" >&2
  exit 2
fi
image="$1"
url="${2%/}"
expected_version="$3"
: "${RAILWAY_TOKEN:?}" "${RAILWAY_SERVICE_ID:?}" "${RAILWAY_ENVIRONMENT_ID:?}"
api="${RAILWAY_API:-https://backboard.railway.com/graphql/v2}"
timeout_s="${DEPLOY_TIMEOUT_S:-600}"

# Runs one GraphQL request; fails on HTTP errors and on GraphQL "errors".
gql() {
  local response
  response="$(curl -fsS "$api" -H 'Content-Type: application/json' \
    -H "Project-Access-Token: ${RAILWAY_TOKEN}" -d "$1")"
  if jq -e '.errors' > /dev/null <<< "$response"; then
    echo "error: Railway API: $(jq -c '.errors' <<< "$response")" >&2
    return 1
  fi
  printf '%s' "$response"
}

vars="$(jq -nc --arg e "$RAILWAY_ENVIRONMENT_ID" --arg s "$RAILWAY_SERVICE_ID" --arg i "$image" \
  '{e: $e, s: $s, i: $i}')"

gql "$(jq -nc --argjson v "$vars" '{variables: $v, query:
  "mutation($e: String!, $s: String!, $i: String!) { serviceInstanceUpdate(environmentId: $e, serviceId: $s, input: {source: {image: $i}}) }"}')" > /dev/null
echo "Source image set to ${image}"

deployment="$(gql "$(jq -nc --argjson v "$vars" '{variables: ($v | del(.i)), query:
  "mutation($e: String!, $s: String!) { serviceInstanceDeployV2(environmentId: $e, serviceId: $s) }"}')" \
  | jq -re '.data.serviceInstanceDeployV2')"
echo "Deployment ${deployment} started"

# Poll instead of a fixed wait: go on as soon as the new build answers.
# Every 5 s: a deploy (image pull, start, Railway's traffic switch) takes
# about a minute; the timeout catches a deploy that never comes up.
deadline=$((SECONDS + timeout_s))
while :; do
  version=""
  if curl -fsS -m 10 "${url}/health" > /dev/null 2>&1; then
    version="$(curl -fsS -m 10 "${url}/" 2>/dev/null \
      | python3 -c 'import re, sys; m = re.search(r"<div class=\"app-version\">\s*(.*?)\s*</div>", sys.stdin.read(), re.S); print(m.group(1) if m else "")' \
      || true)"
  fi
  if [ "$version" = "$expected_version" ]; then
    echo "${url} serves ${expected_version}"
    exit 0
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "error: ${url} did not serve ${expected_version} within ${timeout_s} s (last seen: '${version:-no answer}'). Check deployment ${deployment} in Railway." >&2
    exit 1
  fi
  sleep 5
done
