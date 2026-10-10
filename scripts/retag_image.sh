#!/usr/bin/env bash
# Add a tag to an image that is already in the registry, keeping its digest.
#
# Usage: scripts/retag_image.sh <registry>/<repo> <source tag or digest> <new tag>
# Prints the digest of the (unchanged) manifest.
#
# Fetches the manifest bytes and PUTs them unchanged under the new tag, so the
# new tag has exactly the source digest. `docker buildx imagetools create`
# cannot be used for this: it wraps a single-platform manifest in a new
# manifest list, which has a different digest.
#
# Auth: with REGISTRY_USER and REGISTRY_PASSWORD set, a pull/push bearer token
# is requested from the registry's /token endpoint (GHCR: the workflow's
# GITHUB_TOKEN). REGISTRY_SCHEME=http is for a local test registry only.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <registry>/<repo> <source tag or digest> <new tag>" >&2
  exit 2
fi
image="$1"
source_ref="$2"
new_tag="$3"
registry="${image%%/*}"
repo="${image#*/}"
base="${REGISTRY_SCHEME:-https}://${registry}/v2/${repo}/manifests"
accept="application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"

auth=()
if [ -n "${REGISTRY_PASSWORD:-}" ]; then
  token="$(curl -fsS -u "${REGISTRY_USER}:${REGISTRY_PASSWORD}" \
    "https://${registry}/token?service=${registry}&scope=repository:${repo}:pull,push" | jq -re .token)" \
    || { echo "error: could not get a registry token for ${repo}" >&2; exit 1; }
  auth=(-H "Authorization: Bearer ${token}")
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -fsS ${auth[@]+"${auth[@]}"} -H "Accept: ${accept}" \
  -D "$tmp/headers" -o "$tmp/manifest" "${base}/${source_ref}" \
  || { echo "error: could not fetch ${image}:${source_ref}" >&2; exit 1; }
content_type="$(grep -i '^content-type:' "$tmp/headers" | tail -n 1 | cut -d' ' -f2- | tr -d '\r')"

curl -fsS ${auth[@]+"${auth[@]}"} -X PUT -H "Content-Type: ${content_type}" \
  --data-binary @"$tmp/manifest" -o /dev/null "${base}/${new_tag}" \
  || { echo "error: could not tag ${image}:${new_tag}" >&2; exit 1; }

echo "sha256:$(sha256sum "$tmp/manifest" | cut -d' ' -f1)"
