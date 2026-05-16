from __future__ import annotations

from PySide6.QtCore import QObject, Signal

LANG_VI = "vi"
LANG_EN = "en"

STRINGS: dict[str, dict[str, str]] = {
    LANG_VI: {
        "language.all": "Tất cả",
        "top.open_file": "Mở file...",
        "top.help": "Trợ giúp",
        "top.lang_toggle_to_en": "EN",
        "top.lang_toggle_to_vi": "VIE",
        "top.captcha": "Xác thực",
        "status.no_file": "Chưa chọn file. Bấm 'Mở file...' để bắt đầu.",
        "status.file_info": "Tệp: {file}  •  {mode}  •  Đoạn: {count}",
        "status.mode_txt": "Chế độ TXT",
        "status.mode_srt": "Chế độ SRT",
        "status.mode_unknown": "Chưa xác định",
        "section.content": "Nội dung",
        "section.voice": "Chọn giọng đọc",
        "section.voice_setup": "Thiết lập giọng",
        "section.speaker_list": "Danh sách người nói",
        "table.idx": "#",
        "table.time": "Thời gian",
        "table.content": "Nội dung",
        "table.speaker": "Người nói",
        "table.voice": "Giọng",
        "speaker.name_label": "Tên người nói",
        "speaker.range_label": "Danh sách đoạn",
        "speaker.language_label": "Ngôn ngữ",
        "speaker.voice_label": "Giọng đọc",
        "speaker.pitch_label": "Cao độ",
        "speaker.rate_label": "Tốc độ",
        "speaker.add_btn": "Thêm/Cập nhật",
        "speaker.remove_btn": "Xóa",
        "speaker.preview_btn": "Nghe thử giọng",
        "speaker.preview_sample_text": "Xin chào, đây là giọng đọc mẫu từ SpeechMa.",
        "speaker.txt_mode_hint": "Chế độ TXT: chỉ cần chọn giọng, áp dụng cho toàn bộ đoạn.",
        "speaker.warn_title": "Cảnh báo",
        "speaker.warn_empty_name": "Tên người nói không được để trống",
        "speaker.warn_no_voice": "Chưa chọn giọng đọc",
        "speaker.overlap_title": "Cảnh báo trùng đoạn",
        "speaker.overlap_msg": "Đoạn bị gán nhiều người nói: {items}",
        "speaker.pitch_tip": "Cao độ giọng (-100 đến +100). Mặc định: 0",
        "speaker.rate_tip": "Tốc độ đọc (-100 đến +100). Mặc định: 0",
        "output.dir_label": "Thư mục xuất",
        "output.browse": "Chọn...",
        "output.save_original": "Lưu âm thanh gốc",
        "output.export": "Xuất MP3",
        "output.export_retry": "Xuất lại MP3",
        "output.choose_dialog_title": "Chọn thư mục xuất",
        "player.play": "Phát",
        "player.pause": "Tạm dừng",
        "player.stop": "Dừng",
        "player.status_idle": "Trình phát: Chưa phát",
        "player.status_playing": "Phát: {name}",
        "subtitle.preview_btn": "Nghe thử dòng đã chọn",
        "subtitle.warn_select_row": "Hãy chọn 1 dòng để nghe thử",
        "subtitle.warn_no_voice": "Dòng này chưa có giọng đọc",
        "dlg.error_title": "Lỗi",
        "dlg.warn_title": "Cảnh báo",
        "dlg.done_title": "Hoàn tất",
        "dlg.export_done": "Đã xuất audio: {path}",
        "dlg.export_incomplete_title": "Tạo audio chưa hoàn tất",
        "dlg.export_incomplete_msg": "Các segment sau bị lỗi:\n{items}\n\nBấm 'Xuất lại MP3' để tạo lại segment lỗi.",
        "dlg.missing_voice_title": "Thiếu voice",
        "dlg.missing_voice_msg": "Các đoạn chưa có voice: {items}",
        "dlg.preview_error_title": "Lỗi preview",
        "dlg.no_input": "Chưa có dữ liệu đầu vào",
        "dlg.no_output_dir": "Vui lòng chọn thư mục xuất",
        "dlg.open_input_title": "Chọn file phụ đề hoặc văn bản",
        "dlg.open_input_filter": "Subtitle/Text (*.srt *.txt)",
        "captcha.title": "Xác thực CAPTCHA",
        "captcha.label": "Nhập mã captcha (5 chữ số):",
        "captcha.refresh": "Làm mới",
        "captcha.ok": "Xác nhận",
        "captcha.cancel": "Hủy",
        "captcha.error": "Mã captcha không đúng. Vui lòng thử lại.",
        "captcha.network_error": "Không thể tải captcha. Kiểm tra kết nối mạng.",
        "tip.export": "Xuất file âm thanh MP3.",
        "tip.export_retry": "Tạo lại segment bị lỗi.",
        "tip.preview_row": "Nghe thử dòng đang chọn.",
        "help.dialog_title": "Hướng dẫn sử dụng",
        "help.html_body": "<h3>SpeechMa Desktop</h3><p>Ứng dụng tổng hợp giọng nói sử dụng dịch vụ <b>speechma.com</b>.</p><ol><li>Bấm <b>Mở file...</b> để nạp file .srt hoặc .txt.</li><li>SRT: Gán giọng cho từng người nói.</li><li>TXT: Chọn một giọng cho toàn bộ nội dung.</li><li>Bấm <b>Nghe thử</b> để kiểm tra.</li><li>Chọn thư mục xuất và bấm <b>Xuất MP3</b>.</li><li>Lần đầu sử dụng cần xác thực CAPTCHA.</li></ol><h4>Lưu ý</h4><ul><li>Cần kết nối Internet để tổng hợp giọng.</li><li>Giới hạn 2000 ký tự mỗi đoạn.</li><li>Phiên bản: <b>{version}</b></li><li>Thư mục xuất: {output_dir}</li></ul>",
    },
    LANG_EN: {
        "language.all": "All Languages",
        "top.open_file": "Open file...",
        "top.help": "Help",
        "top.lang_toggle_to_en": "EN",
        "top.lang_toggle_to_vi": "VIE",
        "top.captcha": "Verify",
        "status.no_file": "No file selected. Click 'Open file...' to start.",
        "status.file_info": "File: {file}  •  {mode}  •  Segments: {count}",
        "status.mode_txt": "TXT mode",
        "status.mode_srt": "SRT mode",
        "status.mode_unknown": "Unknown mode",
        "section.content": "Content",
        "section.voice": "Voice selection",
        "section.voice_setup": "Voice setup",
        "section.speaker_list": "Speaker list",
        "table.idx": "#",
        "table.time": "Time",
        "table.content": "Content",
        "table.speaker": "Speaker",
        "table.voice": "Voice",
        "speaker.name_label": "Speaker name",
        "speaker.range_label": "Segment ranges",
        "speaker.language_label": "Language",
        "speaker.voice_label": "Voice",
        "speaker.pitch_label": "Pitch",
        "speaker.rate_label": "Rate",
        "speaker.add_btn": "Add/Update",
        "speaker.remove_btn": "Delete",
        "speaker.preview_btn": "Preview voice",
        "speaker.preview_sample_text": "Hello, this is a sample voice from SpeechMa.",
        "speaker.txt_mode_hint": "TXT mode: choose one voice for all segments.",
        "speaker.warn_title": "Warning",
        "speaker.warn_empty_name": "Speaker name must not be empty",
        "speaker.warn_no_voice": "Please select a voice",
        "speaker.overlap_title": "Overlap warning",
        "speaker.overlap_msg": "Segments assigned to multiple speakers: {items}",
        "speaker.pitch_tip": "Pitch adjustment (-100 to +100). Default: 0",
        "speaker.rate_tip": "Rate adjustment (-100 to +100). Default: 0",
        "output.dir_label": "Output folder",
        "output.browse": "Browse...",
        "output.save_original": "Save original audio",
        "output.export": "Export MP3",
        "output.export_retry": "Retry MP3 Export",
        "output.choose_dialog_title": "Select output folder",
        "player.play": "Play",
        "player.pause": "Pause",
        "player.stop": "Stop",
        "player.status_idle": "Player: Idle",
        "player.status_playing": "Playing: {name}",
        "subtitle.preview_btn": "Preview selected line",
        "subtitle.warn_select_row": "Please select a subtitle line to preview",
        "subtitle.warn_no_voice": "No voice assigned for this line",
        "dlg.error_title": "Error",
        "dlg.warn_title": "Warning",
        "dlg.done_title": "Done",
        "dlg.export_done": "Audio exported: {path}",
        "dlg.export_incomplete_title": "Incomplete",
        "dlg.export_incomplete_msg": "Failed segments:\n{items}\n\nClick 'Retry MP3 Export' to regenerate.",
        "dlg.missing_voice_title": "Missing voice",
        "dlg.missing_voice_msg": "Segments without voice: {items}",
        "dlg.preview_error_title": "Preview error",
        "dlg.no_input": "No input data yet",
        "dlg.no_output_dir": "Please choose an output folder",
        "dlg.open_input_title": "Select subtitle or text file",
        "dlg.open_input_filter": "Subtitle/Text (*.srt *.txt)",
        "captcha.title": "CAPTCHA Verification",
        "captcha.label": "Enter the 5-digit code:",
        "captcha.refresh": "Refresh",
        "captcha.ok": "Confirm",
        "captcha.cancel": "Cancel",
        "captcha.error": "Incorrect captcha code. Please try again.",
        "captcha.network_error": "Cannot load captcha. Check your internet connection.",
        "tip.export": "Export MP3 audio file.",
        "tip.export_retry": "Retry failed segments only.",
        "tip.preview_row": "Preview selected subtitle line.",
        "help.dialog_title": "User Guide",
        "help.html_body": "<h3>SpeechMa Desktop</h3><p>Text-to-speech app powered by <b>speechma.com</b>.</p><ol><li>Click <b>Open file...</b> to load .srt or .txt.</li><li>SRT: Assign voice to each speaker.</li><li>TXT: Choose one voice for all content.</li><li>Use <b>Preview</b> to test.</li><li>Select output folder and click <b>Export MP3</b>.</li><li>First use requires CAPTCHA verification.</li></ol><h4>Notes</h4><ul><li>Internet connection required.</li><li>2000 character limit per segment.</li><li>Version: <b>{version}</b></li><li>Output folder: {output_dir}</li></ul>",
    },
}


class Translator(QObject):
    language_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._language = LANG_VI

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        target = language if language in (LANG_VI, LANG_EN) else LANG_VI
        if target == self._language:
            return
        self._language = target
        self.language_changed.emit(self._language)

    def tr(self, key: str, **kwargs: object) -> str:
        text = STRINGS.get(self._language, {}).get(key) or STRINGS[LANG_VI].get(key) or key
        if kwargs:
            return text.format(**kwargs)
        return text


translator = Translator()


def tr(key: str, **kwargs: object) -> str:
    return translator.tr(key, **kwargs)
