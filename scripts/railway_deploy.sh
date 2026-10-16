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
# DEPLOY_TIMEOUT_S (default 600) bounds the wait; POLL_INTERVAL_S (default 5)
# is shortened by the tests only.
#
# Done means: Railway reports the new deployment as SUCCESS, then /health
# answers 200 and the landing page footer shows the expected version.
# Why both: the status tells this deployment from an older one of the same
# image (a re-run deploys the image staging already serves, so the footer
# alone would pass at once, while the swap is still pending); the footer
# proves the new image answers on the public domain.
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
poll_s="${POLL_INTERVAL_S:-5}"

# Runs one GraphQL request; fails on HTTP errors and on GraphQL "errors".
gql() {
  local response
  response="$(curl -fsS -m 30 "$api" -H 'Content-Type: application/json' \
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

# Poll instead of a fixed wait: go on as soon as the deployment is up.
# Every 5 s: a deploy (image pull, start, Railway's traffic switch) takes
# about a minute; the timeout catches a deploy that never comes up.
deadline=$((SECONDS + timeout_s))
while :; do
  status="$(gql "$(jq -nc --arg d "$deployment" '{variables: {d: $d}, query:
    "query($d: String!) { deployment(id: $d) { status } }"}')" | jq -re '.data.deployment.status')"
  case "$status" in
    SUCCESS) echo "Deployment ${deployment}: SUCCESS"; break ;;
    FAILED|CRASHED|REMOVED|REMOVING|SKIPPED)
      echo "error: deployment ${deployment} ended with status ${status}. Check it in Railway." >&2
      exit 1 ;;
  esac
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "error: deployment ${deployment} not successful within ${timeout_s} s (status ${status})." >&2
    exit 1
  fi
  sleep "$poll_s"
done

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
  sleep "$poll_s"
done
