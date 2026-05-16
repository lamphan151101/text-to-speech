import shutil
import subprocess
import tempfile
import re
from pathlib import Path

import ffmpeg
import imageio_ffmpeg

from speechmaapp.models.subtitle import Segment
from speechmaapp.utils.logging_utils import log_info, log_error

# EBU R128 loudness target: -14 LUFS (YouTube/podcast standard), -1 dBTP true peak,
# LRA=11 keeps natural speech dynamics (no aggressive compression).
_LOUDNORM_AF = "loudnorm=I=-14:TP=-1:LRA=11"


def ffmpeg_cmd() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run_ffprobe_duration(file_path: str) -> float:
    cmd = [ffmpeg_cmd(), "-i", file_path, "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", output)
    if not match:
        log_error(f"Cannot parse duration file={file_path}")
        return 0.0
    hh = int(match.group(1))
    mm = int(match.group(2))
    ss = float(match.group(3))
    return hh * 3600 + mm * 60 + ss


def _atempo_chain(factor: float) -> str:
    parts: list[str] = []
    remaining = factor
    while remaining > 2.0:
        parts.append("2.0")
        remaining /= 2.0
    parts.append(f"{remaining:.6f}")
    return ",".join([f"atempo={item}" for item in parts])


def _normalize_segment_duration(input_path: str, output_path: str, target_duration: float) -> None:
    log_info(f"Normalize segment input={input_path} output={output_path} target_duration={target_duration:.3f}")
    actual = _run_ffprobe_duration(input_path)
    if actual <= 0:
        raise RuntimeError(f"Không đọc được duration của {input_path}")
    if target_duration <= 0:
        shutil.copy2(input_path, output_path)
        return

    if actual > target_duration + 0.05:
        speed = actual / target_duration
        try:
            ffmpeg.input(input_path).output(
                output_path,
                acodec="pcm_s16le",
                af=_atempo_chain(speed),
                ar=24000,
                ac=1,
            ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
            log_error(f"FFmpeg normalize(speed-up) failed input={input_path} detail={stderr}")
            raise RuntimeError(f"FFmpeg normalize(speed-up) failed for {input_path}") from exc
    elif actual < target_duration - 0.05:
        pad = max(target_duration - actual, 0.0)
        try:
            ffmpeg.input(input_path).filter_("apad", pad_dur=pad).output(
                output_path,
                acodec="pcm_s16le",
                ar=24000,
                ac=1,
                t=target_duration,
            ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
            log_error(f"FFmpeg normalize(pad) failed input={input_path} detail={stderr}")
            raise RuntimeError(f"FFmpeg normalize(pad) failed for {input_path}") from exc
    else:
        try:
            ffmpeg.input(input_path).output(
                output_path, acodec="pcm_s16le", ar=24000, ac=1
            ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
            log_error(f"FFmpeg normalize(copy-like) failed input={input_path} detail={stderr}")
            raise RuntimeError(f"FFmpeg normalize(copy-like) failed for {input_path}") from exc


def _encode_with_loudnorm(input_path: str, output_path: str) -> None:
    """Decode input, apply loudnorm to -14 LUFS, encode to 192k MP3."""
    try:
        ffmpeg.input(input_path).output(
            output_path,
            acodec="libmp3lame",
            audio_bitrate="192k",
            ar=24000,
            ac=1,
            af=_LOUDNORM_AF,
        ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
        log_error(f"encode+loudnorm failed input={input_path} detail={stderr}")
        raise RuntimeError(f"encode+loudnorm failed for {input_path}") from exc


def export_single_mp3(input_path: str, output_path: str) -> None:
    """Export to normalized MP3 (-14 LUFS). Accepts MP3 or WAV input."""
    _encode_with_loudnorm(input_path, output_path)
    log_info(f"export_single_mp3 done input={input_path}")


def concatenate_audio_files_to_mp3(input_paths: list[str], output_path: str) -> None:
    """Lossless-concat MP3 segments then normalize to -14 LUFS."""
    if not input_paths:
        raise RuntimeError("Không có file audio để concatenate")
    if len(input_paths) == 1:
        _encode_with_loudnorm(input_paths[0], output_path)
        log_info(f"concatenate_audio single encode output={output_path}")
        return

    # Step 1: lossless stream-copy concat to temp (no decode)
    concat_entries = "\n".join(
        f"file '{Path(p).resolve().as_posix()}'" for p in input_paths
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(concat_entries + "\n")
        list_file = tf.name
    temp_mp3 = list_file.replace(".txt", "_raw.mp3")
    try:
        result = subprocess.run(
            [
                ffmpeg_cmd(),
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                "-y", temp_mp3,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            log_error(f"FFmpeg concat copy failed detail={result.stderr[-400:]}")
            raise RuntimeError("FFmpeg concat copy failed")
        # Step 2: loudnorm encode from concatenated raw to final output
        _encode_with_loudnorm(temp_mp3, output_path)
        log_info(f"concatenate_audio files={len(input_paths)} output={output_path}")
    finally:
        Path(list_file).unlink(missing_ok=True)
        Path(temp_mp3).unlink(missing_ok=True)


def build_timeline_audio(
    segments: list[Segment],
    segment_audio_paths: list[str],
    out_mp3: str,
    temp_dir: Path,
) -> None:
    log_info(f"Build timeline start segments={len(segments)} out={out_mp3}")
    if len(segments) != len(segment_audio_paths):
        raise ValueError("Số segment và số file audio không khớp")

    adjusted_paths: list[tuple[str, int]] = []
    for idx, (seg, in_path) in enumerate(zip(segments, segment_audio_paths), start=1):
        start_sec = _parse_time(seg.start)
        end_sec = _parse_time(seg.end)
        target_duration = max(end_sec - start_sec, 0.01)
        adjusted_path = temp_dir / f"adjusted_{idx:04d}.wav"
        _normalize_segment_duration(in_path, str(adjusted_path), target_duration)
        adjusted_paths.append((str(adjusted_path), int(start_sec * 1000)))

    total_duration = max(_parse_time(seg.end) for seg in segments) + 0.2
    base_silence = temp_dir / "base_silence.wav"
    try:
        ffmpeg.input("anullsrc=r=24000:cl=mono", f="lavfi", t=total_duration).output(
            str(base_silence), acodec="pcm_s16le", ar=24000, ac=1
        ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
        log_error(f"FFmpeg create base silence failed detail={stderr}")
        raise RuntimeError("FFmpeg create base silence failed") from exc

    streams = [ffmpeg.input(str(base_silence)).audio]
    for path, delay_ms in adjusted_paths:
        delayed = ffmpeg.input(path).audio.filter_("adelay", f"{delay_ms}|{delay_ms}")
        streams.append(delayed)

    # normalize=0: don't divide by active input count — base_silence was halving speech level
    mixed = ffmpeg.filter(
        streams, "amix",
        inputs=len(streams),
        duration="longest",
        dropout_transition=0,
        normalize=0,
    )
    enhanced = mixed.filter_("loudnorm", I=-14, TP=-1, LRA=11)
    try:
        ffmpeg.output(
            enhanced, out_mp3,
            acodec="libmp3lame", audio_bitrate="192k", ar=24000, ac=1,
        ).global_args("-y").run(cmd=ffmpeg_cmd(), quiet=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else str(exc)
        log_error(f"FFmpeg mix timeline failed detail={stderr}")
        raise RuntimeError("FFmpeg mix timeline failed") from exc
    log_info(f"Build timeline done out={out_mp3}")


def _parse_time(value: str) -> float:
    hh, mm, sec_msec = value.split(":")
    sec, msec = sec_msec.split(",")
    return int(hh) * 3600 + int(mm) * 60 + int(sec) + int(msec) / 1000.0
