from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.deps import require_admin, owner_scope
from app.db.models.user import User
from app.db.enums import GenerationMode
from app.modules.videos.service import VideoService
from app.modules.videos.schemas import VideoSubmitURL, VideoResponse, VideoListResponse, VideoStatsResponse, VideoAnalyzeRequest, VideoAnalyzeResponse, TranscriptResponse
from app.modules.shorts.service import ShortService
from app.modules.shorts.schemas import ShortResponse
from app.workers.queues import enqueue_video
from app.workers.ffmpeg import get_yt_info
from app.workers.ai.factory import get_ai_provider

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/analyze", response_model=VideoAnalyzeResponse, summary="Analyze URL and suggest shorts count")
async def analyze_video_url(
    payload: VideoAnalyzeRequest,
    current_user: User = Depends(require_admin),
):
    import asyncio
    from app.core.config import settings

    info = await asyncio.to_thread(
        get_yt_info, payload.url,
        settings.YTDLP_COOKIES_FILE,
        settings.YTDLP_COOKIES_FROM_BROWSER,
    )

    context = ""
    if info.title: context += f"Title: {info.title}\n"
    if info.description: context += f"Description: {info.description}\n"
    if info.chapters:
        context += "Chapters:\n" + "\n".join(
            f"  {c.get('title','')} ({c.get('start_time',0):.0f}s-{c.get('end_time',0):.0f}s)"
            for c in info.chapters
        )

    ai = get_ai_provider()
    count, reason = await asyncio.to_thread(ai.suggest_shorts_count, info.duration, context)
    return VideoAnalyzeResponse(suggested_count=count, reason=reason, duration=info.duration)


@router.get("/stats", response_model=VideoStatsResponse, summary="Get aggregated stats")
def get_stats(
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return VideoService(db).get_stats(scope)


@router.get("", response_model=VideoListResponse, summary="List all videos")
def list_videos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None, pattern="^(pending|downloading|processing|completed|failed)$"),
    # One mode, or a comma-separated set so a module lists only its own job
    # types: "?mode=tts,dub,cleanup,separate,transcribe". Names are validated
    # against GenerationMode in the service.
    mode: str | None = Query(None, max_length=120, pattern="^[a-z]+(,[a-z]+)*$"),
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return VideoService(db).list_videos(page, limit, search or None, status or None, mode or None, scope)


@router.post("/url", response_model=VideoResponse, status_code=202, summary="Submit video URL")
async def submit_video_url(
    payload: VideoSubmitURL,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = await VideoService(db).submit_url(payload, user_id=current_user.id)
    enqueue_video(video)
    return video


@router.post("/upload", response_model=VideoResponse, status_code=202, summary="Upload video file")
async def upload_video(
    file: UploadFile = File(...),
    shorts_count: int = Form(..., ge=1, le=10),
    subtitles_enabled: bool = Form(True),
    subtitle_language: str = Form(""),
    generation_mode: GenerationMode = Form(GenerationMode.smart),
    transcript_text: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = await VideoService(db).submit_upload(
        file, shorts_count, user_id=current_user.id,
        subtitles_enabled=subtitles_enabled, subtitle_language=subtitle_language,
        generation_mode=generation_mode, transcript_text=transcript_text,
    )
    enqueue_video(video)
    return video


@router.post("/tts", response_model=VideoResponse, status_code=202, summary="Synthesise speech from text (XTTS-v2)")
async def submit_tts(
    text: str = Form(...),
    language: str = Form(""),
    voice: str = Form(""),
    reference_audio: UploadFile | None = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = await VideoService(db).submit_tts(
        text, user_id=current_user.id,
        language=language or None, voice=voice or None,
        reference_audio=reference_audio,
    )
    enqueue_video(video)
    return video


@router.post("/dub", response_model=VideoResponse, status_code=202, summary="Translate + dub a video/audio")
async def submit_dub(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form(""),
    voice: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = await VideoService(db).submit_dub(
        file, target_language, user_id=current_user.id,
        source_language=source_language or None, voice=voice or None,
    )
    enqueue_video(video)
    return video


@router.post("/edit", response_model=VideoResponse, status_code=202, summary="Manual montage: multi-cut + aspect + timed text")
async def submit_edit(
    file: UploadFile = File(...),
    aspect: str = Form("9:16"),
    fit: str = Form("crop"),
    output_mode: str = Form("custom"),
    segments: str = Form(""),     # JSON: [{"start":s,"end":e}, …]
    texts: str = Form(""),        # JSON: [{"text","start","end","position","color","scale"}, …]
    # Legacy single-clip fields (older clients).
    start: float = Form(0.0, ge=0),
    end: float = Form(0.0, ge=0),
    text: str = Form(""),
    text_position: str = Form("bottom"),
    text_color: str = Form(""),
    text_scale: float = Form(1.0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import json

    def _parse_array(raw: str, field: str):
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{field} must be valid JSON")
        if not isinstance(value, list):
            raise HTTPException(status_code=422, detail=f"{field} must be a JSON array")
        return value

    video = await VideoService(db).submit_edit(
        file, user_id=current_user.id,
        aspect=aspect, fit=fit, output_mode=output_mode,
        segments=_parse_array(segments, "segments"),
        texts=_parse_array(texts, "texts"),
        start=start, end=end, text=text, text_position=text_position,
        text_color=text_color, text_scale=text_scale,
    )
    enqueue_video(video)
    return video


@router.post("/tool", response_model=VideoResponse, status_code=202, summary="Run a single-purpose media tool")
async def submit_tool(
    file: UploadFile = File(...),
    op: str = Form(...),
    params: str = Form("{}"),
    extra: UploadFile | None = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import json
    try:
        parsed = json.loads(params or "{}")
        if not isinstance(parsed, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="params must be a JSON object")
    video = await VideoService(db).submit_tool(file, op, parsed, user_id=current_user.id, extra=extra)
    enqueue_video(video)
    return video


@router.post("/merge", response_model=VideoResponse, status_code=202, summary="Merge audio/video (concat / mix / vconcat)")
async def submit_merge(
    files: list[UploadFile] = File(...),
    op: str = Form(...),
    params: str = Form("{}"),
    music: UploadFile | None = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import json
    try:
        parsed = json.loads(params or "{}")
        if not isinstance(parsed, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="params must be a JSON object")
    video = await VideoService(db).submit_merge(files, op, parsed, user_id=current_user.id, music=music)
    enqueue_video(video)
    return video


@router.get("/{video_id}", response_model=VideoResponse, summary="Get video status")
def get_video(
    video_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return VideoService(db).get_video(video_id, scope)


@router.post("/{video_id}/cancel", response_model=VideoResponse, summary="Cancel a queued or running job")
def cancel_video(
    video_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return VideoService(db).cancel_video(video_id, scope)


@router.delete("/{video_id}", status_code=204, summary="Delete video and its files")
def delete_video(
    video_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    VideoService(db).delete_video(video_id, scope)


@router.get("/{video_id}/transcript", response_model=TranscriptResponse, summary="Get STT transcript")
def get_transcript(
    video_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    import json
    video = VideoService(db).get_video(video_id, scope)
    segments = []
    if video.transcript_segments:
        try:
            segments = json.loads(video.transcript_segments)
        except (ValueError, TypeError):
            segments = []
    return TranscriptResponse(
        video_id=video.id,
        status=video.status,
        filename=video.original_filename,
        text=video.transcript_text or "",
        segments=segments,
    )


@router.get("/{video_id}/shorts", response_model=list[ShortResponse], summary="List shorts for a video")
def get_video_shorts(
    video_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return ShortService(db).list_by_video(video_id, scope)
