# Video Downloader

A native Windows desktop app that lists available resolutions before downloading.

## Run

1. Install Python 3.10 or newer.
2. Run `install.bat`.
3. Run `start.bat`.
4. Paste a public YouTube link, choose a quality, and download.

Completed files are saved in the Windows Downloads folder (`C:\Users\<username>\Downloads`). The app opens the folder after installation and on request.
Every completed download is saved as an MP4 containing H.264 video and AAC audio.
On Windows, conversion automatically uses hardware acceleration through Media Foundation when available, with a CPU fallback.
