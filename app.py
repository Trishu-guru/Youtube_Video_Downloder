from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
import os
import shutil
import tempfile
import time
import threading
from yt_dlp import YoutubeDL

app = Flask(__name__)
app.secret_key = "replace-this-with-any-secret"

# Global progress tracking
download_progress = {}
download_files = {}
download_cancelled = {}


def get_http_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def build_download_options(format_type, quality, temp_dir, ffmpeg_path, progress_hook):
    outtmpl = os.path.join(temp_dir, "%(title)s.%(ext)s")

    if format_type == "audio":
        options = {
            "outtmpl": outtmpl,
            "format": "bestaudio/best",
            "progress_hooks": [progress_hook],
            "quiet": False,
            "http_headers": get_http_headers(),
        }

        if ffmpeg_path:
            options.update({
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "ffmpeg_location": ffmpeg_path,
            })

        return options

    if quality.isdigit():
        format_str = f"bestvideo[height<={quality}][ext=mp4]/best[ext=mp4]"
        if ffmpeg_path:
            format_str = f"bestvideo[height<={quality}]+bestaudio/best/best[ext=mp4]"
    else:
        format_str = "best[ext=mp4]/best"

    options = {
        "outtmpl": outtmpl,
        "format": format_str,
        "progress_hooks": [progress_hook],
        "quiet": False,
        "http_headers": get_http_headers(),
    }

    if ffmpeg_path:
        options["ffmpeg_location"] = ffmpeg_path
        options["merge_output_format"] = "mp4"

    return options


def download_video(url, format_type, quality, download_id, temp_dir):
    """Run download in background thread"""
    def progress_hook(d):
        # Check if download was cancelled
        if download_cancelled.get(download_id, False):
            raise Exception("Download cancelled by user")
        
        if d['status'] == 'downloading':
            total = d.get('total_bytes', d.get('total_bytes_estimate', 1))
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            eta = d.get('eta', 0)
            download_progress[download_id] = {
                "status": "downloading",
                "percent": round(percent, 1),
                "eta": f"{int(eta)}s" if eta else "calculating...",
                "downloaded": round(downloaded / (1024*1024), 1),
                "total": round(total / (1024*1024), 1)
            }
        elif d['status'] == 'finished':
            download_progress[download_id] = {
                "status": "processing",
                "percent": 95,
                "eta": "almost done"
            }

    try:
        ffmpeg_path = shutil.which("ffmpeg")
        ydl_opts = build_download_options(format_type, quality, temp_dir, ffmpeg_path, progress_hook)

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find downloaded file
        for entry in os.scandir(temp_dir):
            if entry.is_file():
                download_files[download_id] = entry.path
                break

        download_progress[download_id] = {"status": "completed", "percent": 100}
    except Exception as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() and "not found" in error_msg.lower():
            download_progress[download_id] = {
                "status": "error", 
                "error": "FFmpeg not found. Please install from: https://ffmpeg.org/download.html"
            }
        elif download_cancelled.get(download_id, False):
            download_progress[download_id] = {"status": "cancelled", "error": "Download cancelled"}
        else:
            download_progress[download_id] = {"status": "error", "error": error_msg}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/video_info", methods=["POST"])
def get_video_info():
    """Get video information including thumbnail"""
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"})
    
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "http_headers": get_http_headers()}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0)
            })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/download", methods=["POST"])
def start_download():
    url = request.form.get("url", "").strip()
    format_type = request.form.get("format", "video")
    quality = request.form.get("quality", "best")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    download_id = str(int(time.time() * 1000))
    temp_dir = tempfile.mkdtemp(prefix="yt_dl_")
    download_progress[download_id] = {"status": "queued", "percent": 0}

    thread = threading.Thread(
        target=download_video,
        args=(url, format_type, quality, download_id, temp_dir),
        daemon=True,
    )
    thread.start()

    return jsonify({"download_id": download_id})

@app.route("/progress/<download_id>")
def progress(download_id):
    return jsonify(download_progress.get(download_id, {"status": "unknown"}))

@app.route("/file/<download_id>")
def get_file(download_id):
    """Download the completed file"""
    if download_id not in download_files:
        return "File not ready", 404
    
    file_path = download_files[download_id]
    if not os.path.exists(file_path):
        return "File not found", 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=os.path.basename(file_path),
    )

@app.route("/cancel/<download_id>", methods=["POST"])
def cancel_download(download_id):
    """Cancel an ongoing download"""
    download_cancelled[download_id] = True
    download_progress[download_id] = {"status": "cancelling", "percent": 0}
    return jsonify({"status": "cancelled"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
