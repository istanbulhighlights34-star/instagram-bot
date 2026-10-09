"""Burn the existing brand into a short video while preserving sound."""
from pathlib import Path
import subprocess
import imageio_ffmpeg
from PIL import Image
from bot import render_free_design, brand_asset, claw_mark

MAX_VIDEO_BYTES = 45 * 1024 * 1024

def prepare_video(source, destination, kind):
    reader = imageio_ffmpeg.read_frames(str(source))
    try:
        info = next(reader)
    finally:
        reader.close()
    duration = info.get('duration', 0)
    if not 1 <= duration <= 60:
        raise ValueError('Video 1–60 saniye olmalı.')
    if max(info.get('source_size', (0, 0))) > 7680:
        raise ValueError('Video çözünürlüğü çok yüksek.')
    width, height = (720, 1280) if kind == 'reel' else (720, 900)
    top = 146
    folder = Path(destination).parent
    blank, framed, overlay = [folder / name for name in ('blank.jpg', 'header.jpg', 'overlay.png')]
    Image.new('RGB', (1080,1080), 'black').save(blank)
    render_free_design(blank, framed, '')
    canvas = Image.new('RGBA', (width,height))
    with Image.open(framed) as image:
        canvas.paste(image.crop((0,0,1080,220)).resize((width,top)), (0,0))
    logo = brand_asset('kartalpenche1903-logo',(130,130))
    canvas.alpha_composite(logo,(width-logo.width-18,8))
    mark = claw_mark((400,400),.28)
    canvas.alpha_composite(mark,((width-mark.width)//2,top+(height-top-mark.height)//2))
    canvas.save(overlay)
    filters = f'[0:v]fps=30,scale={width}:{height-top}:force_original_aspect_ratio=decrease,pad={width}:{height-top}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,pad={width}:{height}:0:{top}:black[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]'
    command = [imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-y','-hide_banner','-loglevel','error','-i',str(source),'-i',str(overlay),'-filter_complex_threads','1','-filter_complex',filters,'-map','[out]','-map','0:a?','-c:v','libx264','-preset','fast','-crf','22','-threads','2','-c:a','aac','-b:a','128k','-ac','2','-movflags','+faststart','-map_metadata','-1',str(destination)]
    result = subprocess.run(command, capture_output=True, timeout=240)
    if result.returncode or not Path(destination).is_file():
        raise ValueError('Video işlenemedi; MP4 veya MOV dosyasını kontrol edin.')
    if Path(destination).stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError('İşlenmiş video 45 MB sınırını aştı.')
