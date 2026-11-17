# 🎮 AutoClip: GTA 6 Live Stream → Instagram Reels (Auto)

## இது எப்படி வேலை செய்யும்?

```
Streamer live ஆகிறார் 🔴
   ↓  (PC தானா கண்டுபிடிக்கும், 2 நிமிஷத்துக்கு ஒரு முறை check)
Stream record ஆகும் 📼
   ↓  (ஒவ்வொரு 20 நிமிஷமும்)
Claude best viral moment-ஐ கண்டுபிடிச்சு 9:16 Reel ஆக்கும் ✂️
   (captions + hook + #ad + streamer credit)
   ↓
உங்க phone-க்கு notification 📱  →  [✅ Approve]  [❌ Skip]
   ↓  (நீங்க 1 tap)
Instagram-ல post ஆகும் ✅
   ↓
Post link phone-க்கு வரும் → Whop-ல 30 நிமிஷத்துக்குள் submit பண்ணுங்க 💰
```

**உங்க வேலை:** phone-ல 1 tap + Whop-ல link submit. மீதி எல்லாம் auto.

---

## ✅ Nov 19-க்கு முன்னாடி பண்ண வேண்டியவை (ஒரே ஒரு முறை)

### Step 1: Clipping campaigns-ல join பண்ணுங்க (10 நிமிஷம்)
1. **whop.com**-ல account create பண்ணுங்க → "Content Rewards" / "Clipping" campaigns தேடுங்க
2. அல்லது **contentrewards.com**-ல sign up பண்ணுங்க
3. **GTA 6 / gaming streamer campaigns** 2–3 தேர்ந்தெடுத்து **Join** பண்ணுங்க
4. ஒவ்வொரு campaign-லயும் இருக்கும் **brief** (rules) முழுசா copy பண்ணுங்க
5. அதை இந்த files-ல paste பண்ணுங்க:
   - `autoclip/campaigns/streamer1/brief.txt`
   - `autoclip/campaigns/streamer2/brief.txt`
   - `autoclip/campaigns/streamer3/brief.txt`
6. உங்க Instagram account-ஐ campaign-ல verify பண்ணுங்க (Whop சொல்லும்படி)

### Step 2: Instagram-ஐ WoopSocial-ல connect பண்ணுங்க (5 நிமிஷம்)
1. Instagram-ஐ **Professional (Creator) account**-ஆ மாத்துங்க (Settings → Account type)
2. **app.woopsocial.com/signup**-ல sign up பண்ணுங்க (2 accounts free)
3. உங்க Instagram account-ஐ connect பண்ணுங்க

### Step 3: Phone-ல ntfy app install பண்ணுங்க (2 நிமிஷம்)
1. Play Store / App Store-ல **"ntfy"** app install பண்ணுங்க
2. Step 4 முடிஞ்சதும் வரும் **topic name**-ஐ app-ல **Subscribe** பண்ணுங்க

### Step 4: Windows PC setup (15 நிமிஷம்)
1. இந்த repo-வை PC-ல download பண்ணுங்க:
   `git clone https://github.com/rknagilan/skills.git` (branch: `ccr-21cbc605-g8n41d`)
2. `autoclip` folder-ல **`install-windows.ps1`** → right-click → **Run with PowerShell**
3. கடைசியில வரும் **topic name**-ஐ ntfy app-ல subscribe பண்ணுங்க
4. PowerShell-ல `claude` type பண்ணி ஒரு முறை **login** பண்ணுங்க
5. `claude` உள்ளே இதை type பண்ணுங்க: *"connect WoopSocial for the ai-clipping-skill"* → சொல்றத follow பண்ணுங்க

### Step 5: உங்க details நிரப்புங்க
**`autoclip/config.json`**:
- `instagram_handle` → உங்க Instagram பேர் (எ.கா. `@gta6clips_tamil`)

**`autoclip/streamers.json`**: ஒவ்வொரு streamer-க்கும்:
- `channel` → Twitch / Kick / YouTube channel பேர்
- `platform` → `twitch` அல்லது `kick` அல்லது `youtube`
- `credit_handle` → streamer-ஓட Instagram பேர்
- `campaign_name` → Whop campaign பேர்
- `enabled` → `true`

### Step 6: Test பண்ணுங்க
PowerShell-ல:
```
cd autoclip
py -3.12 autoclip.py --check
```
**"ALL GOOD"** வந்தா ready ✅

### Step 7: Auto-start ON பண்ணுங்க
`register-autostart.ps1` → right-click → **Run with PowerShell**.
இனிமே PC on ஆனதும் AutoClip தானா start ஆகும்.

---

## 📅 Nov 19 அன்னைக்கு

1. PC-ஐ **ON** பண்ணி, **charger-ல** வைங்க, **internet** connect பண்ணுங்க
2. அவ்வளவு தான்! Streamer live ஆனதும் phone-க்கு "🔴 is live" notification வரும்
3. Clip ready ஆனதும் → **✅ Approve** tap பண்ணுங்க
4. "Posted ✅" வந்ததும் → link-ஐ **Whop-ல submit** பண்ணுங்க (30 நிமிஷத்துக்குள்)

---

## ⚠️ முக்கியமான rules
- **#ad disclosure** எல்லா clip-லயும் இருக்கும். அதை எடுக்கச் சொல்லாதீங்க (law + Whop rule)
- ஒரு நாளைக்கு **max 6 posts** (`max_posts_per_day`). அதிகமா போட்டா Instagram spam-ஆ நினைக்கும்
- Campaign இல்லாத streamer clips-ஐ **post பண்ணாதீங்க** (copyright strike)
- PC **sleep ஆகக்கூடாது** (register-autostart.ps1 sleep-ஐ off பண்ணும்)
- Income guarantee இல்லை. Views-ஐ பொறுத்து தான் pay

## 🛠️ பிரச்சனை வந்தா
- Log: `autoclip/work/autoclip.log`
- Clip files: `autoclip/work/<streamer>/<date>/clip-xxxx/`
- Notification வரலைனா: ntfy app-ல topic சரியான்னு பாருங்க (`config.json`-ல `ntfy_topic`)
