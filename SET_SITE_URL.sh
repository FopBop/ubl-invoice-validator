#!/usr/bin/env bash
# SET_SITE_URL.sh — replace the placeholder site URL everywhere with your real domain.
#
# The shipped pages use the IANA-reserved placeholder "https://invoice-validator.example".
# A placeholder canonical/OG/sitemap URL is correct for a template, but BEFORE you
# put this in front of customers set the real origin once, here, so that:
#   - <link rel="canonical">, og:url, og:image, twitter:image point at real URLs
#   - robots.txt "Sitemap:" and sitemap.xml <loc> resolve
#   - search + answer engines (GEO) can actually fetch and cite the pages
#
# Optionally set the contact/inbound address at the same time (recommended:
# a printed placeholder contact is as bad as a placeholder domain):
#   ./SET_SITE_URL.sh https://your-real-domain.tld you@your-domain.tld
#
# Usage:
#   ./SET_SITE_URL.sh https://your-real-domain.tld [contact@email]
#
set -euo pipefail

PLACEHOLDER="https://invoice-validator.example"
CONTACT_PLACEHOLDER="hello@example.com"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { echo "usage: $0 https://your-real-domain.tld [contact@email]   (no trailing slash)" >&2; exit 2; }

[ "${1:-}" ] || usage
NEW="$1"

case "$NEW" in
  http://*|https://*) ;;
  *) echo "error: URL must start with http:// or https://" >&2; usage ;;
esac
case "$NEW" in
  */) echo "error: drop the trailing slash from '$NEW'" >&2; usage ;;
esac
if [ "$NEW" = "$PLACEHOLDER" ]; then
  echo "error: '$NEW' is the placeholder; pass a real domain." >&2
  exit 2
fi

FILES=(index.html golive/index.html 404.html robots.txt sitemap.xml)

echo "Replacing '$PLACEHOLDER' -> '$NEW'"
for f in "${FILES[@]}"; do
  path="$HERE/$f"
  [ -f "$path" ] || { echo "  skip (missing): $f"; continue; }
  before=$(grep -c "$PLACEHOLDER" "$path" || true)
  tmp="$(mktemp)"
  sed "s|$PLACEHOLDER|$NEW|g" "$path" > "$tmp" && mv "$tmp" "$path"
  echo "  $f: $before occurrence(s) updated"
done

# Optional: replace the printed contact placeholder in one shot.
CONTACT="${2:-}"
if [ -n "$CONTACT" ]; then
  case "$CONTACT" in
    *@*.*) ;;
    *) echo "error: '$CONTACT' does not look like an email address" >&2; usage ;;
  esac
  echo "Replacing contact '$CONTACT_PLACEHOLDER' -> '$CONTACT'"
  for f in "${FILES[@]}"; do
    path="$HERE/$f"
    [ -f "$path" ] || continue
    before=$(grep -c "$CONTACT_PLACEHOLDER" "$path" || true)
    [ "$before" -gt 0 ] || continue
    tmp="$(mktemp)"
    sed "s|$CONTACT_PLACEHOLDER|$CONTACT|g" "$path" > "$tmp" && mv "$tmp" "$path"
    echo "  $f: $before occurrence(s) updated"
  done
fi

leftover=$(grep -rl "$PLACEHOLDER" "$HERE" --include='*.html' --include='*.xml' --include='*.txt' 2>/dev/null || true)
if [ -n "$leftover" ]; then
  echo "warning: placeholder still present in:" >&2
  echo "$leftover" >&2
  exit 1
fi

echo "Done. Canonical, Open Graph, Twitter, robots.txt and sitemap.xml now use $NEW."
echo "Next: point DNS for the domain at your host, then re-deploy."
