import asyncio
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path(__file__).parent / "media"
MEDIA_ROOT.mkdir(exist_ok=True)

_FFMPEG = shutil.which("ffmpeg")
_FFPROBE = shutil.which("ffprobe")


def get_ffmpeg_binaries():
    """Resolve ffmpeg/ffprobe: system binaries if present, else pip-installed static builds."""
    global _FFMPEG, _FFPROBE
    if not _FFMPEG or not _FFPROBE:
        from static_ffmpeg import run
        _FFMPEG, _FFPROBE = run.get_or_fetch_platform_executables_else_raise()
    return _FFMPEG, _FFPROBE

MAX_CLIPS = 40
MIN_SEG = 4.0
MAX_SEG = 30.0


async def _run(cmd: List[str], timeout: int = 600) -> bool:
    ffmpeg_bin, _ = await asyncio.to_thread(get_ffmpeg_binaries)
    # Auto-prepend ffmpeg binary unless the caller already passed an absolute path
    if not cmd or not cmd[0].startswith("/"):
        cmd = [ffmpeg_bin] + list(cmd)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        logger.error(f"ffmpeg command timed out: {' '.join(cmd[:6])}")
        return False
    if proc.returncode != 0:
        logger.error(f"ffmpeg failed ({proc.returncode}): {stderr.decode()[-500:]}")
        return False
    return True


async def probe_duration(path: Path) -> Optional[float]:
    _, ffprobe = await asyncio.to_thread(get_ffmpeg_binaries)
    proc = await asyncio.create_subprocess_exec(
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except (ValueError, AttributeError):
        return None


async def _download(url: str, dest: Path) -> bool:
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url, timeout=180.0) as r:
                if r.status_code != 200:
                    return False
                with dest.open("wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=1024 * 512):
                        f.write(chunk)
        return dest.stat().st_size > 10000
    except Exception as e:
        logger.warning(f"Download failed {url[:80]}: {e}")
        return False


async def _normalize_video(src: Path, dest: Path, seg_dur: float) -> bool:
    return await _run([
        "-y", "-stream_loop", "-1", "-i", str(src), "-t", f"{seg_dur:.2f}",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,setsar=1",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        str(dest),
    ])


async def _normalize_image(src: Path, dest: Path, seg_dur: float) -> bool:
    frames = int(seg_dur * 30)
    return await _run([
        "-y", "-loop", "1", "-i", str(src), "-t", f"{seg_dur:.2f}",
        "-vf",
        f"scale=2400:1350:force_original_aspect_ratio=increase,crop=2400:1350,"
        f"zoompan=z='min(zoom+0.0006,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,setsar=1",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        str(dest),
    ])


async def render_video_file(
    video_id: str,
    clips: List[Dict],
    images: List[Dict],
    voiceover_path: Optional[Path],
    target_seconds: float,
    progress_cb: Optional[Callable[[int, str], Awaitable[None]]] = None,
) -> Path:
    """Render final 1080p MP4: dedupe clips, download, normalize, concat, mix voiceover."""
    async def report(pct: int, msg: str):
        if progress_cb:
            await progress_cb(pct, msg)

    out_dir = MEDIA_ROOT / video_id
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    if voiceover_path and voiceover_path.exists():
        audio_dur = await probe_duration(voiceover_path)
        if audio_dur and audio_dur > 5:
            target_seconds = audio_dur

    # Deduplicate clips by id/url so no clip repeats in the video
    seen = set()
    unique_clips = []
    for c in clips:
        key = c.get("id") or c.get("url")
        if key and key not in seen and c.get("url"):
            seen.add(key)
            unique_clips.append(c)
    unique_clips = unique_clips[:MAX_CLIPS]

    unique_images = []
    for im in images:
        key = im.get("id") or im.get("url")
        if key and key not in seen and im.get("url"):
            seen.add(key)
            unique_images.append(im)

    await report(84, f"Downloading {len(unique_clips)} stock clips...")

    sem = asyncio.Semaphore(5)
    downloaded = []

    async def dl_clip(i, item, ext):
        dest = work / f"src_{i}{ext}"
        async with sem:
            ok = await _download(item["url"], dest)
        if ok:
            downloaded.append((i, dest, ext == ".mp4"))

    tasks = [dl_clip(i, c, ".mp4") for i, c in enumerate(unique_clips)]
    await asyncio.gather(*tasks)

    # Fall back to images (Ken Burns) if not enough footage
    if len(downloaded) < 3 and unique_images:
        img_tasks = [dl_clip(1000 + i, im, ".jpg") for i, im in enumerate(unique_images[:10])]
        await asyncio.gather(*img_tasks)

    if not downloaded:
        raise RuntimeError("No stock media could be downloaded for rendering")

    downloaded.sort(key=lambda x: x[0])
    n = len(downloaded)
    seg_dur = max(MIN_SEG, target_seconds / n)
    if seg_dur > MAX_SEG and n >= 5:
        seg_dur = MAX_SEG
    n_used = min(n, max(1, int(round(target_seconds / seg_dur))))
    seg_dur = target_seconds / n_used
    used = downloaded[:n_used]

    await report(88, f"Rendering {n_used} scenes in HD 1080p...")

    enc_sem = asyncio.Semaphore(2)
    segments: List[Path] = []
    done_count = 0

    async def encode(idx, src, is_video):
        nonlocal done_count
        dest = work / f"seg_{idx:03d}.mp4"
        async with enc_sem:
            ok = await (_normalize_video(src, dest, seg_dur) if is_video else _normalize_image(src, dest, seg_dur))
        done_count += 1
        if done_count % 3 == 0:
            await report(min(96, 88 + int(8 * done_count / n_used)), f"Rendering scenes ({done_count}/{n_used})...")
        if ok:
            segments.append(dest)

    await asyncio.gather(*[encode(i, src, isv) for i, (_, src, isv) in enumerate(used)])

    segments.sort()
    if not segments:
        raise RuntimeError("Video rendering failed: no segments encoded")

    concat_list = work / "list.txt"
    concat_list.write_text("\n".join(f"file '{s}'" for s in segments))

    final = out_dir / "final.mp4"
    await report(97, "Merging video and voiceover...")

    if voiceover_path and voiceover_path.exists():
        ok = await _run([
            "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-i", str(voiceover_path),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", str(final),
        ], timeout=900)
    else:
        ok = await _run([
            "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", "-movflags", "+faststart", str(final),
        ], timeout=900)

    shutil.rmtree(work, ignore_errors=True)

    if not ok or not final.exists():
        raise RuntimeError("Final video assembly failed")
    return final
