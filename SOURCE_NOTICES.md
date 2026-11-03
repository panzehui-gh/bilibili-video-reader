# Sources and redistribution

The original video-reader workflow and helper script are based on
[yichen11818/bilibili-video-reader](https://github.com/yichen11818/bilibili-video-reader).
The original repository contained no LICENSE file when this version was prepared.
No repository-wide license is assigned here to that upstream material.

The local audio/visual integration, runtime setup, and multilingual documentation
are maintained by PAN ZEHUI. The retained helper is still imported by the new
pipeline; it is not presented as wholly original work.

Tools and model weights are downloaded separately and are not distributed in
this source repository. Consult each project's own terms:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/legal.html) and the [Gyan Windows build](https://www.gyan.dev/ffmpeg/builds/)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Whisper small model conversion](https://huggingface.co/Systran/faster-whisper-small)
- [YAMNet ONNX conversion](https://huggingface.co/audiomagic/yamnet-onnx)
  and [Google's YAMNet source](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet)
- NumPy and ONNX Runtime, installed from their package distributions

No user video, original soundtrack, transcript, screenshot, browser session,
credential, model weights, or machine-specific virtual environment is included.
