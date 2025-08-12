"""FastAPI AI Gateway & LSP Proxy service.

Provides:
- /health
- /ai/enhance  (POST)
- /ai/detect   (POST)
- /lsp/markdown (WebSocket proxy to marksman LSP server)

Run:
  uvicorn src.ai_gateway:app --reload --port 8001
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Optional, Dict, Any
import socket

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Reuse existing AI logic
from .notes.ai_client import NoteAIClient
from .notes.ghost_ai_client import GhostAIClient

app = FastAPI(title="AI Gateway", version="0.2.0")

# CORS: allow Flask app at http://localhost:5000 (and dev variants) to access the gateway
allowed_origins = os.environ.get("AI_GATEWAY_CORS_ORIGINS")
if allowed_origins:
    origins = [o.strip() for o in allowed_origins.split(",") if o.strip()]
else:
    origins = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://0.0.0.0:5000",
        "*"  # dev fallback
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Embedded background server support (for auto-start from Flask/Waitress) ----
_gateway_started = False
_gateway_port: Optional[int] = None

def _is_port_free(port: int, host: str = '0.0.0.0') -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False

def _pick_port(preferred: Optional[int], host: str = '0.0.0.0') -> int:
    if preferred and preferred > 0 and _is_port_free(preferred, host):
        return preferred
    # fallback to ephemeral free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]

def start_gateway_background(port: int = 8002, host: str = "0.0.0.0"):
    """Start this FastAPI app (including persistent LSP) in a background thread if not already running.

    Intended to be invoked from Flask dev/prod entry points so that AI Gateway + LSP
    is always available without a separate manual process. Can be disabled by env var
    DISABLE_INTERNAL_GATEWAY=1 to allow external deployment.
    """
    global _gateway_started, _gateway_port
    if os.environ.get("DISABLE_INTERNAL_GATEWAY") == "1":
        return
    if _gateway_started:
        return
    try:
        import threading, uvicorn  # local import to avoid mandatory dependency if unused
        # auto-pick free port if occupied
        chosen_port = _pick_port(port, host)
        _gateway_port = chosen_port
        os.environ["AI_GATEWAY_PORT_ACTUAL"] = str(chosen_port)
        config = uvicorn.Config(app, host=host, port=chosen_port, log_level="info")
        server = uvicorn.Server(config)

        def _run():
            try:
                import asyncio as _asyncio
                _asyncio.set_event_loop(_asyncio.new_event_loop())
                server.run()
            except Exception as e:  # pragma: no cover
                print(f"[AI-Gateway] Background server failed: {e}")

        t = threading.Thread(target=_run, name="AI-Gateway-Thread", daemon=True)
        t.start()
        _gateway_started = True
        print(f"[AI-Gateway] Background server starting on {host}:{_gateway_port} (thread)")
    except Exception as e:  # pragma: no cover
        print(f"[AI-Gateway] Could not start background server: {e}")

def get_gateway_port(default: int = 8002) -> int:
    """Return the actual running gateway port, if known.
    Falls back to env AI_GATEWAY_PORT_ACTUAL, then AI_GATEWAY_PORT, then default.
    """
    if _gateway_port:
        return _gateway_port
    env_actual = os.environ.get("AI_GATEWAY_PORT_ACTUAL")
    if env_actual and env_actual.isdigit():
        return int(env_actual)
    env_cfg = os.environ.get("AI_GATEWAY_PORT")
    if env_cfg and env_cfg.isdigit():
        return int(env_cfg)
    return default

_ai_client: Optional[NoteAIClient] = None
_ghost_client: Optional[GhostAIClient] = None
_shared_token = os.environ.get("AI_GATEWAY_TOKEN")  # if set, endpoints & websocket require it


def get_ai_client() -> NoteAIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = NoteAIClient()
    return _ai_client


def get_ghost_client() -> GhostAIClient:
    global _ghost_client
    if _ghost_client is None:
        _ghost_client = GhostAIClient()
    return _ghost_client


def require_token(x_ai_gateway_token: str | None = Header(None), token: str | None = Query(None)):
    """Simple shared-secret validation. If AI_GATEWAY_TOKEN env var not set, allow all."""
    if not _shared_token:
        return True
    provided = x_ai_gateway_token or token
    if provided != _shared_token:
        raise HTTPException(status_code=401, detail="Invalid or missing AI gateway token")
    return True


class EnhancementRequest(BaseModel):
    enhancement_request: str
    current_content: str = ""
    title: str = ""
    context: Dict[str, Any] | None = None


class DetectRequest(BaseModel):
    content: str
    context: Dict[str, Any] | None = None
    ai_enabled: bool = True
    request_type: str = "semantic"  # or syntax_only
    action: Optional[str] = None
    enhancement_request: Optional[str] = None
    current_content: Optional[str] = None
    title: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ai/enhance")
async def ai_content_enhance(req: EnhancementRequest, _: bool = Depends(require_token)):
    client = get_ghost_client()  # 使用 Ghost 客戶端處理內容增強
    result = client.generate_content_enhancement(
        enhancement_request=req.enhancement_request,
        current_content=req.current_content,
        title=req.title,
        context=req.context or {}
    )
    return result


@app.post("/ai/detect")
async def ai_detect(req: DetectRequest, _: bool = Depends(require_token)):
    client = get_ghost_client()  # 使用 Ghost 客戶端處理文字偵測

    if not req.ai_enabled:
        return {"suggestions": [], "has_suggestions": False, "source": "ai_disabled", "success": True}

    if req.request_type == "syntax_only":
        return {"use_lsp": True, "success": True}

    if req.action == "generate_enhancement" and req.enhancement_request:
        enhance_res = client.generate_content_enhancement(
            enhancement_request=req.enhancement_request,
            current_content=req.current_content or "",
            title=req.title or "",
            context=req.context or {}
        )
        return {"success": True, **enhance_res}

    detect_res = client.detect_and_suggest_text(req.content, req.context or {})
    detect_res["success"] = True
    return detect_res


# ---------------- LSP WebSocket Proxy -----------------
MARKSMAN_CMD = os.environ.get("MARKSMAN_CMD", "marksman")
MARKSMAN_ARGS = os.environ.get("MARKSMAN_ARGS", "")
MARKSMAN_DISABLE = os.environ.get("AI_GATEWAY_DISABLE_LSP") == "1" or os.environ.get("DISABLE_LSP") == "1"
_marksman_process: asyncio.subprocess.Process | None = None
_marksman_clients: set[WebSocket] = set()
_reader_task: asyncio.Task | None = None
_stderr_task: asyncio.Task | None = None
_monitor_task: asyncio.Task | None = None


def _is_lsp_alive() -> bool:
    return _marksman_process is not None and _marksman_process.returncode is None


def _build_marksman_cmd() -> list[str]:
    """Build command argv for various LSP binaries.
    - Rust marksman: marksman server
    - npm language servers (e.g. *language*server): use --stdio
    - Allow override via MARKSMAN_ARGS
    """
    exe = MARKSMAN_CMD
    args: list[str] = []
    if MARKSMAN_ARGS:
        try:
            import shlex
            args = shlex.split(MARKSMAN_ARGS, posix=False)
        except Exception:
            args = MARKSMAN_ARGS.split()
    else:
        base = os.path.basename(exe).lower()
        if 'marksman' in base and 'server' not in base:
            # Rust marksman binary -> needs 'server'
            args = ['server']
        elif 'language' in base and 'server' in base:
            # typical vscode-languageserver node binaries
            args = ['--stdio']
        else:
            # default: no args
            args = []
    return [exe, *args]


def _candidate_lsp_cmds() -> list[list[str]]:
    """Return a prioritized list of possible LSP command lines.
    Priority:
    1) Respect explicit MARKSMAN_CMD + MARKSMAN_ARGS
    2) marksman server (Rust LSP)
    3) markdown-language-server --stdio (Node LSP)
    4) vscode-markdown-language-server --stdio (alternate name)
    """
    if os.environ.get("MARKSMAN_CMD"):
        # Honor explicit config only
        return [_build_marksman_cmd()]
    cands: list[list[str]] = []
    cands.append(["marksman", "server"])  # Rust LSP
    cands.append(["markdown-language-server", "--stdio"])  # npm i -g markdown-language-server
    cands.append(["vscode-markdown-language-server", "--stdio"])  # alternate
    return cands

async def _spawn_marksman() -> bool:
    global _marksman_process
    import asyncio as _asyncio
    # If explicitly disabled, do nothing
    if MARKSMAN_DISABLE:
        print("[AI-Gateway] LSP disabled via env (AI_GATEWAY_DISABLE_LSP=1)")
        return False

    candidates = _candidate_lsp_cmds()
    last_error: str | None = None
    for argv in candidates:
        try:
            print("[AI-Gateway] Starting LSP:", ' '.join(argv))
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Briefly wait to see if it exits immediately (e.g., wrong CLI like pip marksman)
            try:
                await _asyncio.wait_for(proc.wait(), timeout=0.2)
                # Exited too quickly -> try next candidate
                rc = proc.returncode
                stderr_head = b""
                try:
                    if proc.stderr:
                        stderr_head = await proc.stderr.read(512)
                except Exception:
                    pass
                last_error = f"Exited immediately rc={rc} msg={(stderr_head or b'').decode(errors='ignore').strip()}"
                continue
            except _asyncio.TimeoutError:
                # Still running -> accept
                _marksman_process = proc
                print("[AI-Gateway] LSP started ->", ' '.join(argv))
                return True
        except FileNotFoundError:
            last_error = f"Not found: {argv[0]}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    print("[AI-Gateway] No working Markdown LSP found. Tried candidates:")
    for argv in candidates:
        print("  -", ' '.join(argv))
    if last_error:
        print("[AI-Gateway] Last error:", last_error)
    print("[AI-Gateway] Hint: set MARKSMAN_CMD to a working LSP (e.g., 'markdown-language-server') or install Rust 'marksman'.")
    _marksman_process = None
    return False


async def start_persistent_lsp():
    global _reader_task, _stderr_task
    if MARKSMAN_DISABLE:
        print("[AI-Gateway] LSP is disabled; persistent server will not start.")
        return
    if _is_lsp_alive():
        return
    if not await _spawn_marksman():
        return

    async def reader():
        assert _marksman_process and _marksman_process.stdout
        try:
            while True:
                # Read LSP headers until empty line
                headers: Dict[str, str] = {}
                while True:
                    line = await _marksman_process.stdout.readline()
                    if not line:
                        return
                    txt = line.decode(errors="ignore")
                    if txt in ("\r\n", "\n", ""):
                        break
                    if ":" in txt:
                        k, v = txt.split(":", 1)
                        headers[k.strip().lower()] = v.strip()
                content_length = int(headers.get("content-length", "0") or 0)
                if content_length <= 0:
                    continue
                body = await _marksman_process.stdout.readexactly(content_length)
                payload = body.decode(errors="ignore")
                # Broadcast to all clients
                dead = []
                for ws in list(_marksman_clients):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead.append(ws)
                for d in dead:
                    _marksman_clients.discard(d)
        except Exception as e:
            print(f"[AI-Gateway] LSP reader stopped: {e}")

    async def stderr_reader():
        assert _marksman_process and _marksman_process.stderr
        try:
            while True:
                line = await _marksman_process.stderr.readline()
                if not line:
                    return
                try:
                    print("[Marksman]", line.decode(errors="ignore").rstrip())
                except Exception:
                    pass
        except Exception as e:
            print(f"[AI-Gateway] LSP stderr reader stopped: {e}")

    _reader_task = asyncio.create_task(reader())
    _stderr_task = asyncio.create_task(stderr_reader())


@app.on_event("startup")
async def _startup():
    global _monitor_task
    await start_persistent_lsp()
    print("[AI-Gateway] Startup complete. LSP persistent server running:", _is_lsp_alive())

    async def monitor():
        while True:
            try:
                if not _is_lsp_alive():
                    await start_persistent_lsp()
            except Exception as e:  # pragma: no cover
                print("[AI-Gateway] LSP monitor error:", e)
            await asyncio.sleep(2)

    _monitor_task = asyncio.create_task(monitor())


@app.websocket("/lsp/markdown")
async def lsp_markdown_proxy(ws: WebSocket, token: str | None = Query(None)):
    # WebSocket token check
    if _shared_token and token != _shared_token:
        await ws.close(code=4401)
        return

    await ws.accept()

    # Ensure LSP is up (try once)
    if not _is_lsp_alive():
        await start_persistent_lsp()
    if not _is_lsp_alive():
        await ws.send_text(json.dumps({"error": "LSP not available"}))
        await ws.close()
        return

    _marksman_clients.add(ws)

    async def ws_to_lsp():
        try:
            while True:
                msg = await ws.receive_text()
                if not _is_lsp_alive():
                    # attempt restart and inform client
                    await start_persistent_lsp()
                    await ws.send_text(json.dumps({"warning": "LSP restarted"}))
                    if not _is_lsp_alive():
                        await ws.send_text(json.dumps({"error": "LSP crashed"}))
                        break
                # Write framed message
                try:
                    assert _marksman_process and _marksman_process.stdin
                    data = msg.encode()
                    header = f"Content-Length: {len(data)}\r\n\r\n".encode()
                    _marksman_process.stdin.write(header + data)
                    await _marksman_process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    await start_persistent_lsp()
                    await ws.send_text(json.dumps({"warning": "LSP restarted"}))
                    if not _is_lsp_alive():
                        await ws.send_text(json.dumps({"error": "LSP crashed"}))
                        break
        except WebSocketDisconnect:
            pass
        finally:
            _marksman_clients.discard(ws)

    await ws_to_lsp()


@app.get("/")
async def root():
    return {"service": "ai-gateway", "endpoints": ["/ai/enhance", "/ai/detect", "/lsp/markdown"], "lsp": "marksman proxy"}


@app.get("/lsp/status")
async def lsp_status():
    return {"running": _is_lsp_alive(), "cmd": MARKSMAN_CMD}
