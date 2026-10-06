#!/usr/bin/env bash
# Installs a pinned trivy release into the runner's shared tool cache, verified against the
# release's published checksums, and puts it on the job's PATH. Idempotent; concurrent jobs
# each stage their own copy and rename it into place, so none sees a half-written binary.
set -euo pipefail

version=${TRIVY_VERSION:-0.74.0}
cache=${RUNNER_TOOL_CACHE:-/opt/hostedtoolcache}/trivy/$version
case $(uname -m) in
  x86_64) arch=64bit ;;
  aarch64 | arm64) arch=ARM64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

if [[ ! -x $cache/trivy ]]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  base=https://github.com/aquasecurity/trivy/releases/download/v$version
  tarball=trivy_${version}_Linux-$arch.tar.gz
  curl -fsSL -o "$tmp/$tarball" "$base/$tarball"
  curl -fsSL -o "$tmp/checksums.txt" "$base/trivy_${version}_checksums.txt"
  (cd "$tmp" && grep " $tarball\$" checksums.txt | sha256sum -c -)
  tar -xzf "$tmp/$tarball" -C "$tmp" trivy
  mkdir -p "$(dirname "$cache")"
  stage=$(mktemp -d "$(dirname "$cache")/.stage.XXXXXX")
  mv "$tmp/trivy" "$stage/trivy"
  mv -T "$stage" "$cache" 2>/dev/null || rm -rf "$stage"   # another job won the race
fi

"$cache/trivy" --version | head -1
[[ -n ${GITHUB_PATH:-} ]] && echo "$cache" >> "$GITHUB_PATH"
