# Research Report: PySide6 Desktop TTS Application Architecture

**Date**: 2026-05-14 | **Status**: Complete | **Sources**: 12+ authoritative sources

---

## Executive Summary

Building a PySide6 desktop app to call speechma.com API requires balancing thread safety, HTTP client selection, and file handling. **Recommendation: Use Worker + moveToThread pattern with `requests.Session` for simplicity, or `httpx.AsyncClient` with `qasync` for high-concurrency scenarios.** Use `pysrt` for SRT parsing and `pydub` for audio. Browser DevTools Network tab is the most reliable method for reverse-engineering API calls.

---

## 1. Async HTTP Patterns in PySide6

### Best Pattern: Worker + moveToThread
- **Why**: Separates logic (Worker) from threading (QThread). Flexible, non-blocking, memory-safe.
- **How**: Create QObject subclass with signal/slots, move it to QThread, never subclass QThread.
- **Data flow**: GUI thread → Worker (via signal) → QThread → Worker emits results signal → GUI thread updates UI

```python
class HTTPWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(bytes)
    
    def __init__(self, url, session):
        super().__init__()
        self.url = url
        self.session = session
    
    def run(self):
        try:
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            self.result.emit(response.content)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

# Main window
worker = HTTPWorker(url, session)
thread = QThread()
worker.moveToThread(thread)
worker.finished.connect(thread.quit)
thread.finished.connect(worker.deleteLater)
worker.result.connect(self.on_audio_received)
thread.start()
```

### HTTP Client Comparison

| Aspect | requests | httpx | aiohttp |
|--------|----------|-------|---------|
| **Model** | Sync only | Sync + Async | Async only |
| **Speed** | ~6.5 req/s | ~74 req/s (async) | ~121 req/s |
| **Break-even** | N/A | 50-100 concurrent reqs | 50-100 concurrent reqs |
| **Best for** | Simple calls, sessions | Migration path from requests | High concurrency |
| **Learning curve** | Easiest | Medium | Steeper (requires asyncio) |
| **PySide6 use** | Direct in QThread | Async worker + qasync | Requires qasync or custom loop |

**Decision Tree**:
- Single TTS request at a time? → `requests` + Worker pattern
- Multiple concurrent TTS requests? → `httpx.AsyncClient` + `qasync`
- Heavy async architecture? → `aiohttp` + custom event loop

### Session Management (Cookies & Auth)
```python
session = requests.Session()
session.headers.update({'User-Agent': 'SpeechMA-Desktop/1.0'})
session.cookies.update({'token': auth_token})  # For persistent auth

# Session persists cookies across requests automatically
response1 = session.get('https://api.speechma.com/tts')
response2 = session.get('https://api.speechma.com/status')  # Reuses cookies
```

---

## 2. SRT Subtitle File Parsing

### Format Overview
```
1
00:00:00,000 --> 00:00:02,500
First subtitle

2
00:00:02,500 --> 00:00:05,000
Second subtitle with
multiple lines
```

### Top Libraries

**pysrt** (Recommended)
- Most mature, handles malformed files well
- Installation: `pip install pysrt`
- Usage:
```python
import pysrt

subs = pysrt.SubRipFile.from_string(srt_content)
for sub in subs:
    print(f"{sub.start} --> {sub.end}: {sub.text}")

# Modify timings (for sync adjustments)
subs.shift(ms=1000)  # Shift all by 1 second
subs.save('output.srt')
```

**srt** (Lightweight alternative)
- Pure Python, no dependencies
- Better error handling for malformed SRT
- Installation: `pip install srt`
```python
import srt

subs = srt.parse(srt_content)
for sub in subs:
    print(f"{sub.start} --> {sub.end}: {sub.content}")
```

---

## 3. Audio File Handling in Desktop Apps

### PyDub Best Practices
```python
from pydub import AudioSegment

# Requires FFmpeg installed & in PATH
audio = AudioSegment.from_mp3("response.mp3")
audio = AudioSegment.from_file("audio.wav", format="wav")

# Format conversion
audio.export("output.wav", format="wav")
audio.export("output.mp3", format="mp3", bitrate="192k")

# Concatenate TTS chunks
combined = audio1 + audio2 + audio3
combined.export("full_audio.mp3", format="mp3")

# Play (if UI supports)
os.system(f"ffplay {audio_file}")  # Cross-platform
```

### Dependencies
- **PyDub**: `pip install pydub`
- **FFmpeg**: Required system package
  - Windows: `choco install ffmpeg` or manual download
  - Linux: `apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`

### Avoid Blocking Audio Playback
Spawn playback in separate process:
```python
import subprocess
subprocess.Popen(['ffplay', '-nodisp', '-autoexit', audio_file])
```

---

## 4. Authentication & Session Cookies

### Best Practice Pattern
```python
class APISession:
    def __init__(self, base_url, token=None):
        self.session = requests.Session()
        self.session.base_url = base_url
        
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'
        
        # Custom headers
        self.session.headers['User-Agent'] = 'SpeechMA-Desktop/1.0'
    
    def request_tts(self, text, voice='default'):
        """Cookies auto-persist across calls"""
        return self.session.post(
            f'{self.session.base_url}/tts',
            json={'text': text, 'voice': voice},
            timeout=30
        )
```

### Cookie Management
- Session object auto-persists cookies across requests
- No manual cookie handling needed in most cases
- For explicit cookie handling:
```python
session.cookies.set('sessionid', 'abc123')
session.cookies.clear()  # Clear all
response.cookies.get_dict()  # View cookies
```

---

## 5. PyInstaller Packaging for HTTP Apps

### Core Requirements
```bash
pyinstaller --onefile \
  --hidden-import=requests \
  --hidden-import=urllib3 \
  --hidden-import=certifi \
  --hidden-import=charset_normalizer \
  --collect-all=requests \
  --recursive-copy-metadata=requests \
  app.py
```

### Known Issues & Solutions
| Issue | Solution |
|-------|----------|
| SSL certificate not found | `--collect-all=certifi` for SSL certs bundle |
| `urllib3` not found | `--hidden-import=urllib3` |
| Dynamic imports in requests | `--recursive-copy-metadata=requests` |
| HTTPS connection fails in .exe | Ensure certifi included & bundled properly |

### Best Practices
- Test `.exe` on clean Windows machine (no Python installed)
- Bundle FFmpeg separately if using PyDub
- Use `--onedir` for faster builds during development
- Sign executable on release

---

## 6. Reverse-Engineering API Calls via DevTools

### Step-by-Step Process

1. **Open Network Tab**
   - Press `F12` or `Ctrl+Shift+I` in browser
   - Click Network tab, ensure recording (●) is active
   - Filter: XHR/Fetch to see only API calls

2. **Trigger the Action**
   - Perform TTS request in web UI (type text, click "Speak")
   - Watch for POST request to API endpoint

3. **Analyze Request**
   ```
   POST /api/tts HTTP/1.1
   Host: api.speechma.com
   Content-Type: application/json
   Authorization: Bearer <token>
   User-Agent: Mozilla/5.0...
   
   {"text": "Hello world", "voice": "en-US-Neural2-A"}
   ```

4. **Copy as cURL/Python**
   - Right-click request → Copy as cURL
   - Paste into Python `requests` call:
   ```python
   response = requests.post(
       'https://api.speechma.com/api/tts',
       headers={
           'Authorization': 'Bearer YOUR_TOKEN',
           'Content-Type': 'application/json'
       },
       json={'text': 'Hello', 'voice': 'en-US-Neural2-A'},
       timeout=30
   )
   ```

5. **Check Response**
   - Click Response tab to see audio binary or JSON error
   - Check Status Code (200 = success, 401 = auth failed, 429 = rate limited)

### Tools to Streamline
- **OpenAPI DevTools** extension: Auto-generates OpenAPI spec from traffic
- **API Reverse Engineer** extension: Records all fetch/XHR calls automatically
- **Burp Suite Community**: Advanced request inspection & modification

---

## Implementation Checklist

- [ ] Set up Worker + moveToThread pattern for HTTP calls
- [ ] Choose HTTP client: `requests` (simplicity) or `httpx` (future async)
- [ ] Create APISession wrapper with auth/headers
- [ ] Install & test FFmpeg on dev machine
- [ ] Add pysrt for SRT parsing
- [ ] Reverse-engineer speechma.com API endpoints via DevTools
- [ ] Create requests.Session with proper headers/auth
- [ ] Test PyInstaller build with `--hidden-import` flags
- [ ] Bundle FFmpeg in installer or document requirement

---

## Unresolved Questions

1. **speechma.com API authentication**: Is token-based (Bearer) or session-based (cookies)? Requires DevTools inspection.
2. **Audio format preference**: Does speechma.com return MP3, WAV, or other? Check response headers.
3. **Rate limiting**: Any per-request delays or concurrent request limits? Test with multiple requests.
4. **SRT sync requirements**: Does app need to adjust subtitle timings based on API response? Depends on feature scope.
5. **FFmpeg bundling**: Will users have FFmpeg installed, or should installer include it?

---

## Sources

### PySide6 & Threading
- [PySide6 QThread Documentation](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html)
- [Multithreading PySide6 with QThreadPool](https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/)
- [Qt Async Threads Library](https://pypi.org/project/qt-async-threads/)
- [Async Minimal Example - Qt for Python](https://doc.qt.io/qtforpython-6/examples/example_async_minimal.html)

### HTTP Clients
- [Mastering Sessions with Requests](https://proxiesapi.com/articles/mastering-sessions-cookies-with-python-requests)
- [HTTPX vs Requests vs AIOHTTP Comparison](https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp)
- [Requests Advanced Usage Documentation](https://docs.python-requests.org/en/latest/user/advanced/)

### SRT Parsing
- [pysrt - SubRip Parser](https://pypi.org/project/pysrt/)
- [srt Library Documentation](https://srt.readthedocs.io/en/latest/api.html)

### Audio Handling
- [PyDub GitHub Repository](https://github.com/jiaaro/pydub)
- [Playing MP3 with PyDub and PyAudio](https://dev.to/mathewthe2/playing-mp3-files-in-python-with-pydub-and-pyaudio-579i)
- [Real Python: Playing and Recording Sound](https://realpython.com/playing-and-recording-sound-python/)

### PyInstaller
- [PyInstaller HTTP Requests Issues](https://github.com/psf/requests/issues/2465)
- [Real Python: PyInstaller Tutorial](https://realpython.com/pyinstaller-python/)
- [PyInstaller Documentation](https://pyinstaller.org/en/stable/when-things-go-wrong.html)

### API Reverse Engineering
- [Reverse Engineering APIs with Chrome DevTools](https://posts.oztamir.com/reverse-engineering-apis-with-chrome-devtools-mcp/)
- [Chrome DevTools Network Tab Guide](https://willschenk.com/howto/2019/reverse_engineering_apis_using_chrome/)
- [How to Scrape Hidden APIs](https://scrapfly.io/blog/posts/how-to-scrape-hidden-apis)
