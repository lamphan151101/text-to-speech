# SPEECHMA.COM API Research Report
*Date: 2026-05-14*

## Executive Summary
**SPEECHMA does NOT currently offer a public, documented API.** The official API is in development with no launch timeline. However, an unofficial Python wrapper exists on GitHub that reverse-engineers the web interface.

---

## 1. API Availability

| Aspect | Status |
|--------|--------|
| **Public API** | NOT AVAILABLE (in development, may take months) |
| **Official Endpoints** | None documented |
| **Authentication** | Not applicable (no API) |
| **Unofficial Wrapper** | [GitHub: fairy-root/Speechma-API](https://github.com/fairy-root/Speechma-API) |

---

## 2. Web Interface (Current)

### Access
- **URL**: https://www.speechma.com
- **Registration**: Not required
- **Authentication**: CAPTCHA security (5-digit code, expires every minute)
- **Cost**: 100% FREE, no subscription or credit card needed

### Voice Parameters Available
- **Pitch adjustment** (variable slider)
- **Speed adjustment** (variable slider)
- **Volume adjustment** (default 100%)
- **Custom pauses** via punctuation:
  - Comma: ~0.5 sec
  - Semicolon: ~1 sec
  - Exclamation mark: ~1.5 sec

---

## 3. Voice Options & Languages

| Feature | Details |
|---------|---------|
| **Total Voices** | 580+ premium AI voices |
| **Languages** | 75+ languages (English, Spanish, French, German, Chinese, Japanese, Korean, Arabic, etc.) |
| **Accents/Gender** | Multiple accent & gender variants available |

---

## 4. Audio Format & Output

| Aspect | Details |
|--------|---------|
| **Format** | MP3 (high-quality) |
| **Character Limit** | 2,000 chars per generation |
| **Download** | Direct MP3 download available |
| **Retry Logic** | Unofficial wrapper implements up to 3 retry attempts |

---

## 5. Commercial Use

- **Allowed**: YES - full commercial licensing included
- **Accepted Use Cases**: YouTube, Instagram, TikTok, podcasts, audiobooks, business presentations
- **No Copyright Restrictions**: All content is free to use commercially

---

## 6. Unofficial Implementation Details

The GitHub wrapper (fairy-root/Speechma-API) demonstrates:
- Text chunking to bypass 2,000-char limit
- Voice ID mapping (`voices.json` file)
- MP3 output with automatic retry logic (3 attempts)

**CRITICAL LIMITATION**: Exact endpoint URLs and request/response payload structures are not publicly documented.

---

## 7. Rate Limits & Usage

| Metric | Details |
|--------|---------|
| **Rate Limiting** | Not specified |
| **Quota** | Appears unlimited (free tier) |
| **Concurrent Requests** | Not documented |

---

## 8. Comparison: Speechmatics (Different Service)

⚠️ **Note**: Search results frequently confuse "SPEECHMA" with "Speechmatics" (speechmatics.com), a different enterprise platform with:
- Official REST APIs: `https://asr.api.speechmatics.com/v2/jobs`
- Authentication: Bearer token required
- Paid plans with documented endpoints
- **Not recommended** for this project (different service entirely)

---

## Unresolved Questions

1. What is the exact HTTP endpoint URL for the SPEECHMA TTS service?
2. What is the request payload structure (JSON schema)?
3. How is the CAPTCHA bypass handled in the unofficial wrapper?
4. What are exact voice ID formats (e.g., "voice-35")?
5. When will the official API launch?
6. Are there SRT file upload/processing capabilities?
7. What is the actual rate limit if any?
8. Does the unofficial wrapper work reliably with current SPEECHMA infrastructure?
9. Are there any Terms of Service restrictions on reverse-engineered API usage?

---

## Recommendation for Desktop App

**Option A (Recommended)**: Use Puppeteer/Selenium to automate the web interface
- Captures Pitch, Speed, Volume, and pause controls
- Handles CAPTCHA programmatically
- Avoids reverse-engineering risks
- Slower but reliable

**Option B (Higher Risk)**: Use the unofficial GitHub wrapper + reverse-engineer actual endpoints
- Requires network sniffing to capture real HTTP requests
- Fast but fragile (breaks if SPEECHMA changes infrastructure)
- Potential ToS violations

**Option C (Best Long-term)**: Monitor SPEECHMA API announcements, implement fallback to Options A/B

---

## Sources

- [SPEECHMA Official Website](https://www.speechma.com/)
- [SPEECHMA English Landing Page](https://www.speechma.com/english)
- [GitHub: Unofficial SPEECHMA API Wrapper](https://github.com/fairy-root/Speechma-API)
- [SPEECHMA Google Play App](https://play.google.com/store/apps/details?id=com.speechma.app&hl=en_US)
