# Hướng dẫn sử dụng SpeechMa Desktop

## Giới thiệu

SpeechMa Desktop là ứng dụng chuyển văn bản thành giọng nói (TTS) chạy trên máy tính Windows, kết nối trực tiếp đến dịch vụ speechma.com. Hỗ trợ đọc file phụ đề SRT và file văn bản TXT, xuất ra file MP3 chuẩn âm lượng -14 LUFS (tiêu chuẩn YouTube/Podcast).

---

## Yêu cầu hệ thống

- Windows 10/11 (64-bit)
- Python 3.11+ (nếu chạy từ source)
- Kết nối Internet đến speechma.com

---

## Cài đặt và khởi động

### Lần đầu cài đặt

Chạy file `setup.bat` để tạo môi trường ảo và cài đặt các thư viện cần thiết:

```
setup.bat
```

### Khởi động ứng dụng

```
run.bat
```

---

## Sử dụng cơ bản

### Bước 1 — Mở file

- Nhấn nút **Mở file SRT** để tải file phụ đề (định dạng `.srt`)
- Hoặc nhấn **Mở file TXT** để tải văn bản thuần (định dạng `.txt`)

### Bước 2 — Chọn giọng đọc

1. Trong tab **Voice Setup**, chọn nhóm ngôn ngữ từ danh sách thả xuống (Language Group)
2. Chọn giọng đọc từ danh sách Voice
3. Điều chỉnh **Pitch** (âm điệu, từ -100 đến +100) và **Rate** (tốc độ, từ -100 đến +100) nếu cần
4. Nhấn **Preview** để nghe thử giọng trước khi xuất

> **Tip — Giọng HD chất lượng cao:**  
> Chọn nhóm ngôn ngữ **Multilingual** để truy cập 11 giọng HD gồm Andrew, Ava, Brian, Emma, Jenny, Steffan, Aria, Guy, Davis, Jane, Jason.  
> Các giọng này được đánh dấu `[HD]` trong danh sách và có chất lượng cao nhất.

### Bước 3 — Phân công giọng (SRT mode)

Với file SRT nhiều nhân vật:

1. Nhập **Tên nhân vật** vào ô Name
2. Nhập **dải segment** vào ô Segments, ví dụ `1-50` hoặc `1,3,5-20`
3. Chọn giọng cho nhân vật đó
4. Nhấn **Add** để lưu
5. Lặp lại cho các nhân vật khác

> **Lưu ý:** Mỗi segment chỉ được gán cho một nhân vật. Nếu có segment chưa được gán, ứng dụng sẽ cảnh báo trước khi xuất.

### Bước 4 — Chọn thư mục lưu

Nhấn **Chọn thư mục lưu** và chọn nơi lưu file MP3 đầu ra.

### Bước 5 — Xuất MP3

Nhấn nút **Xuất MP3**. Thanh tiến độ sẽ hiển thị quá trình:

- **0–80%** — Gọi API tổng hợp giọng từng segment
- **80–100%** — Ghép audio và chuẩn hoá âm lượng

---

## Tính năng nâng cao

### CAPTCHA

Khi phiên đăng nhập vào speechma.com hết hạn, ứng dụng sẽ hiện hộp thoại nhập CAPTCHA. Nhập đúng mã trong ảnh để tiếp tục.

### Retry segment lỗi

Nếu một số segment tổng hợp thất bại (thường do lỗi mạng hoặc rate limit), ứng dụng sẽ:

1. Hiện thông báo danh sách segment lỗi
2. Cho phép nhấn **Retry** để thử lại chỉ các segment đó (các segment thành công được lưu cache và không gọi API lại)

### Cache segment

Mỗi lần tổng hợp thành công, file MP3 từng segment được lưu vào thư mục `temp/export_sessions/`. Lần export tiếp theo với cùng file và cài đặt sẽ tự động bỏ qua các segment đã có, tiết kiệm thời gian đáng kể.

---

## Cấu hình Proxy Failover

Khi mạng kết nối đến speechma.com không ổn định (timeout, lỗi kết nối, 502/503/504), bạn có thể cấu hình proxy để ứng dụng tự động chuyển sang kết nối dự phòng.

### Nguyên tắc hoạt động

| Trường hợp | Hành động |
|---|---|
| Timeout / lỗi kết nối | Đổi proxy cho request tiếp theo |
| HTTP 502 / 503 / 504 | Đổi proxy cho request tiếp theo |
| Response quá chậm (> `slow_response_seconds`) | Đổi proxy cho request tiếp theo |
| HTTP 429 (Rate limit) | **Không đổi proxy** — chờ theo `Retry-After` |
| HTTP 401 / 403 (Session hết hạn) | **Không đổi proxy** — cần nhập lại CAPTCHA |

### Cách bật proxy failover

Mở file `config/settings.json` và chỉnh sửa:

```json
{
  "output_dir": "D:\\project\\Audio",
  "save_original_audio": false,
  "last_language_group": "Multilingual",
  "language": "vi",
  "tts_concurrency": 1,
  "proxy_failover_enabled": true,
  "slow_response_seconds": 20,
  "proxy_cooldown_seconds": 300,
  "proxy_profiles": [
    {
      "name": "proxy-1",
      "http": "http://username:password@host1:port",
      "https": "http://username:password@host1:port"
    },
    {
      "name": "proxy-2",
      "http": "http://username:password@host2:port",
      "https": "http://username:password@host2:port"
    }
  ]
}
```

### Ý nghĩa các tham số

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `proxy_failover_enabled` | `false` | Bật/tắt proxy failover |
| `slow_response_seconds` | `20` | Ngưỡng (giây) để coi proxy là chậm (min: 5, max: 120) |
| `proxy_cooldown_seconds` | `300` | Thời gian (giây) không dùng lại proxy bị lỗi (min: 30, max: 3600) |
| `proxy_profiles` | `[]` | Danh sách proxy. Bỏ qua nếu cả `http` và `https` đều rỗng |

### Định dạng proxy URL

```
http://username:password@hostname:port
```

Ví dụ:

```
http://myuser:mypass@proxy.example.com:3128
```

Nếu proxy không cần xác thực:

```
http://proxy.example.com:3128
```

### Lưu ý bảo mật

- **Không commit** `config/settings.json` lên git nếu chứa thông tin đăng nhập proxy thật
- Thông tin đăng nhập trong log sẽ được ẩn tự động thành `***:***@host:port`
- Ứng dụng sẽ tự fallback về kết nối trực tiếp nếu tất cả proxy đang trong cooldown

---

## Đọc log

Log được lưu tại `logs/speechma.log`. Các thông điệp quan trọng:

```
[INFO]  ProxyManager loaded profiles count=2
[INFO]  ProxyManager using proxy=proxy-1 addr=http://***:***@host1:3128
[ERROR] ProxyManager slow response proxy=proxy-1 elapsed=24.3s threshold=20s
[INFO]  ProxyManager cooldown proxy=proxy-1 seconds=300 reason=slow_response
[INFO]  ProxyManager switched proxy proxy-1 -> proxy-2 reason=slow_response
[ERROR] ProxyManager failure proxy=proxy-2 reason=network_error
[ERROR] ProxyManager all proxies unavailable, falling back to direct connection
[ERROR] SpeechmaEngine 429 rate-limited; proxy switch disabled for 429
```

---

## Cấu hình nâng cao

### Số luồng đồng thời (`tts_concurrency`)

Mặc định là `1`. Có thể tăng lên `2` để thử tăng tốc. Không nên vượt quá `2` vì giới hạn tốc độ API.

> **Lưu ý:** Tốc độ thực tế bị giới hạn bởi API speechma.com ở mức ~30–50 request/phút. Với 518 segment, ước tính mất khoảng 10–18 phút.

### Lưu bản audio gốc (`save_original_audio`)

Khi bật (`true`), bản MP3 từng segment sẽ được sao chép vào thư mục `Audio/<tên_file>/` trước khi ghép, hữu ích để kiểm tra từng đoạn riêng lẻ.

---

## Xử lý sự cố

| Triệu chứng | Nguyên nhân | Giải pháp |
|---|---|---|
| Nhiều segment lỗi 429 | Rate limit API speechma.com | Đợi 5–15 phút, dùng Retry |
| Segment lỗi "Session expired" | Cookie hết hạn | Nhập lại CAPTCHA khi được hỏi |
| Âm thanh quá nhỏ | Hiếm gặp sau v2.0 | Kiểm tra file output bằng audio player |
| App đóng khi bấm Preview | Đã sửa ở v1.1 | Cập nhật lên bản mới nhất |
| Proxy không kết nối được | Sai host/port/credential | Kiểm tra lại `proxy_profiles` trong settings.json |

---

## Thư mục dữ liệu

```
SpeechMaProject/
├── Audio/               ← File MP3 đầu ra
├── config/
│   ├── settings.json    ← Cấu hình ứng dụng (bao gồm proxy)
│   └── voices.json      ← Danh sách giọng (583 giọng)
├── logs/
│   └── speechma.log     ← Log hoạt động
└── temp/
    └── export_sessions/ ← Cache segment MP3 trung gian
```

---

## Phiên bản

| Phiên bản | Thay đổi |
|---|---|
| v1.0 | Phát hành ban đầu |
| v1.1 | Sửa crash khi Preview nhanh liên tiếp |
| v1.2 | Sửa âm lượng quá nhỏ, thêm loudnorm -14 LUFS |
| v1.3 | Sửa 429 rate limit với token bucket + retry thông minh |
| v2.0 | Proxy failover, cache-aware synthesis, adaptive rate limiter |
