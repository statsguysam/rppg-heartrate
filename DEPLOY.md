# Deploy to Play Store — 4 Commands

Everything is built and committed. Run these in order.

## Step 1 — Push to GitHub (1 min)

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/salimshaikh/rppg-heartrate

gh auth login          # opens browser → log in with statsguysalim@gmail.com
gh repo create rppg-heartrate --public --source=. --push
```

After this, go to:
  GitHub repo → Settings → Pages → Source: "Deploy from branch" → Branch: main → Folder: /docs
  
Your privacy policy will be live at: https://statsguysam.github.io/rppg-heartrate

---

## Step 2 — Register your Expo project (2 min)

```bash
cd /Users/salimshaikh/rppg-heartrate/mobile
npx expo login           # create free account at expo.dev if needed
eas init                 # auto-fills projectId in app.json
git add app.json && git commit -m "Add EAS project ID"
git push
```

---

## Step 3 — Build the Android AAB (10–15 min, runs in cloud)

```bash
cd /Users/salimshaikh/rppg-heartrate/mobile
eas build --platform android --profile production
# When done, download the .aab file from the link EAS prints
```

---

## Step 4 — Submit to Play Store

### First-time Play Console setup (one-time, 10 min)
1. Go to https://play.google.com/console (account 6248773114835935867)
2. Create app → "Heart Rate Monitor" → Free → App
3. App content → Privacy policy URL: https://statsguysam.github.io/rppg-heartrate
4. Store listing → fill details below

### Play Store listing copy (copy-paste ready)

**App name:** Heart Rate Monitor — rPPG AI

**Short description (80 chars):**
Measure your heart rate from your face using AI — no wearable needed.

**Full description:**
Heart Rate Monitor uses remote photoplethysmography (rPPG) — the same
technology used in medical research — to estimate your heart rate from
a 60-second video of your face.

No wearable. No contact sensor. Just your phone's front camera.

HOW IT WORKS
• Record a 1-minute video of your face in good lighting
• Our AI model (PhysMamba) detects the subtle color changes in your
  skin caused by blood pulsing through your capillaries
• Get your heart rate in BPM with a confidence score
• View the full blood volume pulse (rPPG) waveform

FEATURES
✓ Instant heart rate estimation (results in ~20 seconds)
✓ Waveform visualization of your blood volume pulse
✓ History tracking — all readings saved locally on your device
✓ Works on any Android phone — no special hardware needed
✓ No account required, no data uploaded, complete privacy

PRIVACY
Your face video is sent over encrypted HTTPS, analyzed, and immediately
deleted. We never store your video or biometric data. Heart rate readings
are kept only on your device and can be deleted anytime.

DISCLAIMER
This app is not a medical device. Results are estimates and may vary.
Consult a healthcare professional for medical advice.

**Category:** Health & Fitness
**Tags:** heart rate, rPPG, health, fitness, pulse, heart monitor

### Upload and release
```bash
# Download AAB from EAS, then upload manually in Play Console:
# Internal testing → Create new release → Upload .aab → Review → Start rollout

# OR use EAS submit (requires Google Play service account key):
# https://docs.expo.dev/submit/android/
eas submit --platform android --path ./your-build.aab
```

---

## Step 5 — Backend in production

Update mobile/.env before building:
```
EXPO_PUBLIC_BACKEND_URL=https://your-server.com
```

Cheapest hosting: DigitalOcean $12/month droplet
```bash
# On the droplet:
git clone https://github.com/salimshaikh/rppg-heartrate
cd rppg-heartrate/backend
pip install -r requirements.txt
# Set up nginx with SSL (see nginx.conf)
gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 --timeout 180 --daemon
```
