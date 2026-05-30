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


def _parse_duration_from_output(output: str) -> float:
    match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", output)
    if not match:
        return 0.0
    hh = int(match.group(1))
    mm = int(match.group(2))
    ss = float(match.group(3))
    return hh * 3600 + mm * 60 + ss


def _run_ffprobe_duration(file_path: str) -> float:
    cmd = [ffmpeg_cmd(), "-i", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration = _parse_duration_from_output(f"{result.stdout}\n{result.stderr}")
    if duration <= 0:
        log_error(f"Cannot parse duration file={file_path}")
    return duration


def _run_ffprobe_durations(file_paths: list[str]) -> list[float]:
    if not file_paths:
        return []

    # Use cwd + relative filenames when all files share a directory.
    # Avoids Windows CreateProcess limit (32,767 chars) with many absolute paths:
    # 518 paths × 130 chars ≈ 67K > limit; relative names are only ~16 chars each.
    resolved = [Path(fp).resolve() for fp in file_paths]
    common_dir = resolved[0].parent
    if all(p.parent == common_dir for p in resolved):
        inputs = [p.name for p in resolved]
        cwd: str | None = str(common_dir)
    else:
        inputs = [str(p) for p in resolved]
        cwd = None

    cmd = [ffmpeg_cmd()]
    for fp in inputs:
        cmd.extend(["-i", fp])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)
    output = f"{result.stdout}\n{result.stderr}"
    durations = [
        _parse_duration_from_output(match.group(0))
        for match in re.finditer(r"Duration:\s*\d{2}:\d{2}:\d{2}\.\d+", output)
    ]
    if len(durations) != len(file_paths):
        log_error(
            f"Batch duration probe mismatch files={len(file_paths)} parsed={len(durations)}; "
            "falling back to per-file probe"
        )
        return [_run_ffprobe_duration(file_path) for file_path in file_paths]
    return durations


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
        ).global_args("-y", "-threads", "0").run(cmd=ffmpeg_cmd(), quiet=True)
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

    # Build amix filter via _run_timeline_filter so cwd+relative paths are used.
    # ffmpeg-python.run() with 519 absolute inputs exceeds Windows 32,767-char limit.
    # input[0] = base_silence, input[1..N] = adjusted WAVs (all in temp_dir)
    filter_parts: list[str] = []
    mix_labels: list[str] = ["[0:a]"]
    for i, (path, delay_ms) in enumerate(adjusted_paths):
        label = f"a{i}"
        filter_parts.append(f"[{i + 1}:a]adelay={delay_ms}|{delay_ms}[{label}]")
        mix_labels.append(f"[{label}]")

    n_inputs = len(mix_labels)
    filter_parts.append(
        "".join(mix_labels)
        + f"amix=inputs={n_inputs}:duration=longest:dropout_transition=0:normalize=0,"
        + f"{_LOUDNORM_AF}[out]"
    )
    all_input_paths = [str(base_silence)] + [path for path, _ in adjusted_paths]
    _run_timeline_filter(all_input_paths, filter_parts, out_mp3)
    log_info(f"Build timeline done out={out_mp3}")


def build_timeline_audio_fast(
    segments: list[Segment],
    segment_audio_paths: list[str],
    out_mp3: str,
) -> None:
    log_info(f"Build fast timeline start segments={len(segments)} out={out_mp3}")
    if len(segments) != len(segment_audio_paths):
        raise ValueError("Segment count and audio file count do not match")

    durations = _run_ffprobe_durations(segment_audio_paths)
    if _segments_are_sequential(segments):
        _build_timeline_audio_concat_filter(segments, segment_audio_paths, durations, out_mp3)
        log_info(f"Build fast sequential timeline done out={out_mp3}")
        return

    _build_timeline_audio_mix_filter(segments, segment_audio_paths, durations, out_mp3)
    log_info(f"Build fast mixed timeline done out={out_mp3}")


def _build_timeline_audio_concat_filter(
    segments: list[Segment],
    segment_audio_paths: list[str],
    durations: list[float],
    out_mp3: str,
) -> None:
    filter_parts: list[str] = []
    labels: list[str] = []
    cursor = 0.0
    silence_index = 0

    for idx, (seg, actual_duration) in enumerate(zip(segments, durations)):
        if actual_duration <= 0:
            raise RuntimeError(f"Cannot read duration for {segment_audio_paths[idx]}")

        start_sec = _parse_time(seg.start)
        end_sec = _parse_time(seg.end)
        gap = max(start_sec - cursor, 0.0)
        if gap >= 0.001:
            label = f"s{silence_index}"
            silence_index += 1
            labels.append(f"[{label}]")
            filter_parts.append(
                f"anullsrc=r=24000:cl=mono,atrim=duration={gap:.3f},asetpts=PTS-STARTPTS[{label}]"
            )

        target_duration = max(end_sec - start_sec, 0.01)
        label = f"a{idx}"
        labels.append(f"[{label}]")
        filters = [
            "aresample=24000",
            "aformat=sample_fmts=s16:channel_layouts=mono",
        ]
        if actual_duration > target_duration + 0.05:
            filters.append(_atempo_chain(actual_duration / target_duration))
        filters.extend(
            [
                f"apad=pad_dur={target_duration:.3f}",
                f"atrim=duration={target_duration:.3f}",
                "asetpts=PTS-STARTPTS",
            ]
        )
        filter_parts.append(f"[{idx}:a]{','.join(filters)}[{label}]")
        cursor = max(cursor, end_sec)

    filter_parts.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1,{_LOUDNORM_AF}[out]"
    )
    _run_timeline_filter(segment_audio_paths, filter_parts, out_mp3)


def _build_timeline_audio_mix_filter(
    segments: list[Segment],
    segment_audio_paths: list[str],
    durations: list[float],
    out_mp3: str,
) -> None:
    filter_parts: list[str] = []
    labels: list[str] = []

    for idx, (seg, actual_duration) in enumerate(zip(segments, durations)):
        if actual_duration <= 0:
            raise RuntimeError(f"Cannot read duration for {segment_audio_paths[idx]}")

        start_sec = _parse_time(seg.start)
        end_sec = _parse_time(seg.end)
        target_duration = max(end_sec - start_sec, 0.01)
        delay_ms = max(int(round(start_sec * 1000)), 0)
        label = f"a{idx}"
        labels.append(f"[{label}]")

        filters = [
            "aresample=24000",
            "aformat=sample_fmts=s16:channel_layouts=mono",
        ]
        if actual_duration > target_duration + 0.05:
            filters.append(_atempo_chain(actual_duration / target_duration))
        filters.extend(
            [
                f"apad=pad_dur={target_duration:.3f}",
                f"atrim=duration={target_duration:.3f}",
                "asetpts=PTS-STARTPTS",
                f"adelay={delay_ms}|{delay_ms}",
            ]
        )
        filter_parts.append(f"[{idx}:a]{','.join(filters)}[{label}]")

    filter_parts.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0,"
        + f"{_LOUDNORM_AF}[out]"
    )
    _run_timeline_filter(segment_audio_paths, filter_parts, out_mp3)


def _run_timeline_filter(
    segment_audio_paths: list[str],
    filter_parts: list[str],
    out_mp3: str,
) -> None:
    resolved_paths = [Path(path).resolve() for path in segment_audio_paths]
    common_dir = resolved_paths[0].parent
    if all(path.parent == common_dir for path in resolved_paths):
        ffmpeg_inputs = [path.name for path in resolved_paths]
        cwd = str(common_dir)
    else:
        ffmpeg_inputs = [str(path) for path in resolved_paths]
        cwd = None

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ffgraph", delete=False, encoding="utf-8"
    ) as script_file:
        script_file.write(";".join(filter_parts))
        filter_script = script_file.name

    try:
        cmd = [ffmpeg_cmd()]
        for path in ffmpeg_inputs:
            cmd.extend(["-i", path])
        cmd.extend(
            [
                "-filter_complex_script", filter_script,
                "-map", "[out]",
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                "-ar", "24000",
                "-ac", "1",
                "-threads", "0",   # use all CPU cores
                "-y", out_mp3,
            ]
        )
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            log_error(f"FFmpeg fast timeline failed detail={result.stderr[-800:]}")
            raise RuntimeError("FFmpeg fast timeline failed")
    finally:
        Path(filter_script).unlink(missing_ok=True)


def _segments_are_sequential(segments: list[Segment]) -> bool:
    previous_end = 0.0
    for seg in segments:
        start_sec = _parse_time(seg.start)
        end_sec = _parse_time(seg.end)
        if start_sec + 0.001 < previous_end:
            return False
        previous_end = max(previous_end, end_sec)
    return True


def _parse_time(value: str) -> float:
    hh, mm, sec_msec = value.split(":")
    sec, msec = sec_msec.split(",")
    return int(hh) * 3600 + int(mm) * 60 + int(sec) + int(msec) / 1000.0
