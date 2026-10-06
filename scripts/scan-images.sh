#!/usr/bin/env bash
# Release gate: scans pushed images for fixable HIGH/CRITICAL vulnerabilities and secrets, and
# fails if any image has one. CI (.gitea/workflows/build.yaml) runs it on the commit-tagged
# images and only moves `latest` to them when it passes.
#
# Usage: scripts/scan-images.sh [--insecure] [--platform linux/arm64] <registry/prefix> <tag> <repo>...
#   scripts/scan-images.sh --insecure 192.168.1.11:5000 "$SHA" brewgraph-api brewgraph-web
#
# Unfixed findings are not counted: a gate that fails on something no rebuild can fix only
# teaches people to bypass it. Registry credentials come from the Docker config (docker login)
# or TRIVY_USERNAME/TRIVY_PASSWORD.
set -euo pipefail

insecure=() platform=()
while [[ ${1:-} == --* ]]; do
  case $1 in
    --insecure) insecure=(--insecure); shift ;;
    --platform) platform=(--platform "$2"); shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
(( $# >= 3 )) || { sed -n '6,7p' "$0" >&2; exit 2; }
prefix=$1 tag=$2; shift 2

command -v trivy >/dev/null || { echo "trivy not found on PATH" >&2; exit 2; }
trivy image --download-db-only --no-progress -q

failed=() unscanned=()
for repo in "$@"; do
  ref="$prefix/$repo:$tag"
  echo "==> $ref"
  # Findings exit 3; any other non-zero exit is trivy failing to scan (missing image, auth).
  # ${a[@]+...}: an empty array is "unbound" under set -u in bash 3.2 (macOS).
  rc=0
  trivy image --no-progress -q ${insecure[@]+"${insecure[@]}"} ${platform[@]+"${platform[@]}"} \
    --scanners vuln,secret --severity HIGH,CRITICAL --ignore-unfixed \
    --skip-db-update --exit-code 3 --format table "$ref" || rc=$?
  case $rc in
    0) ;;
    3) failed+=("$repo") ;;
    *) unscanned+=("$repo") ;;
  esac
done

if (( ${#unscanned[@]} )); then
  echo "FAILED: could not scan (image missing or registry error): ${unscanned[*]}" >&2
fi
if (( ${#failed[@]} )); then
  echo "FAILED: fixable HIGH/CRITICAL vulnerabilities or secrets in: ${failed[*]}" >&2
fi
(( ${#unscanned[@]} + ${#failed[@]} == 0 )) || exit 1
echo "OK: no fixable HIGH/CRITICAL vulnerabilities or secrets in $# images"
