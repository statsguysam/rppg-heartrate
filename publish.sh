#!/bin/bash
# Heart Rate Monitor — full Play Store publish script
# Run this once: bash publish.sh
# It handles EAS login, project init, build, and Play Store submission.

set -e  # stop on any error
export PATH="/opt/homebrew/bin:$PATH"

MOBILE_DIR="$(dirname "$0")/mobile"
cd "$MOBILE_DIR"

echo ""
echo "============================================"
echo "  Heart Rate Monitor — Play Store Publisher"
echo "============================================"
echo ""

# ── Step 1: Expo login ────────────────────────────────────────────────────────
echo "▶ Step 1/4: Check Expo login"
WHOAMI=$(eas whoami 2>&1) || true
if echo "$WHOAMI" | grep -q "Not logged in"; then
  echo "  → Opening browser to log in to expo.dev..."
  eas login --browser
else
  echo "  → Already logged in as: $WHOAMI"
fi

# ── Step 2: Init EAS project (gets projectId) ────────────────────────────────
echo ""
echo "▶ Step 2/4: Register EAS project"
# eas init will create the project on expo.dev and write the real projectId into app.json
eas init
# Push the updated app.json (now has real projectId)
cd ..
git add mobile/app.json
git diff --cached --quiet || git commit -m "Add EAS projectId to app.json

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin main
cd mobile

# ── Step 3: Build Android AAB in the cloud ───────────────────────────────────
echo ""
echo "▶ Step 3/4: Build Android App Bundle (runs in EAS cloud ~12 min)"
echo "  → You'll get a link to watch the build progress"
echo "  → A .aab file will be downloaded when done"
echo ""
eas build --platform android --profile production --non-interactive

# ── Step 4: Submit to Play Store ─────────────────────────────────────────────
echo ""
echo "▶ Step 4/4: Submit to Play Store"
echo ""

if [ -f "./google-play-service-account.json" ]; then
  echo "  → Service account found. Submitting automatically..."
  eas submit --platform android --latest --non-interactive
else
  echo "  ⚠ No google-play-service-account.json found."
  echo ""
  echo "  To submit automatically next time:"
  echo "  1. Go to: https://play.google.com/console"
  echo "  2. Setup → API access → Link to Google Cloud → Create service account"
  echo "  3. Download JSON key → save as: mobile/google-play-service-account.json"
  echo "  4. Run: eas submit --platform android --latest"
  echo ""
  echo "  For now, download the .aab from EAS and upload manually:"
  echo "  Play Console → Your app → Internal testing → Create release → Upload .aab"
  echo ""

  # Get the latest build artifact URL
  echo "  Your latest build:"
  eas build:list --platform android --limit 1 --json 2>/dev/null | \
    python3 -c "
import json,sys
builds = json.load(sys.stdin)
if builds:
    b = builds[0]
    print(f\"  Status:   {b.get('status')}\")
    print(f\"  Download: {b.get('artifacts',{}).get('buildUrl','(building...)')}\")
" 2>/dev/null || echo "  (Run 'eas build:list' to see your builds)"
fi

echo ""
echo "✓ Done! Your app is submitted (or ready to upload manually)."
echo ""
echo "  Privacy policy live at: https://statsguysam.github.io/rppg-heartrate"
echo "  Play Console:           https://play.google.com/console"
echo ""
