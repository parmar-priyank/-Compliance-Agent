import io, zipfile, shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import auth

UPLOAD_DIR = Path("uploads")
DB_PATH    = auth.DB_PATH

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_token(request: Request) -> str:
    return (
        request.headers.get("X-Auth-Token") or
        request.cookies.get("qc_token") or ""
    )


def current_user(request: Request):
    return auth.get_user_by_token(get_token(request))


def require_admin(request: Request):
    user = current_user(request)
    if not user or user["role"] != "admin":
        return None
    return user


# ── Auth routes ────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Always show login — never redirect. Each tab manages its own session.
    return templates.TemplateResponse(request, "login.html", {"error": ""})


@router.post("/api/login")
async def login_submit(request: Request,
                       email: str = Form(...), password: str = Form(...)):
    user = auth.get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password"]):
        return JSONResponse({"ok": False, "error": "Incorrect email or password."}, status_code=400)
    if not user["is_active"]:
        return JSONResponse({"ok": False, "error": "Account deactivated. Contact admin."}, status_code=403)
    token = auth.create_session(user["id"])
    return JSONResponse({
        "ok":    True,
        "token": token,
        "role":  user["role"],
        "name":  user["name"],
    })


@router.post("/api/logout")
async def logout(request: Request):
    token = get_token(request)
    if token:
        auth.delete_session(token)
    return JSONResponse({"ok": True})


@router.get("/api/me")
async def me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"ok": False}, status_code=401)
    return JSONResponse({"ok": True, "id": user["id"], "name": user["name"], "role": user["role"]})


# ── Admin dashboard ────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Shell page — auth checked client-side via /api/me
    return templates.TemplateResponse(request, "admin.html", {
        "admin":    {"name": "Admin", "id": 0},
        "users":    [],
        "projects": [],
    })


@router.get("/admin/api/data")
async def admin_data(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    projects = auth.get_all_projects()
    return JSONResponse({
        "users":    auth.get_all_users(),
        "projects": projects,
    })


# ── User CRUD API ──────────────────────────────────────────────────────────

@router.post("/admin/api/users")
async def api_create_user(request: Request,
                          name: str = Form(...), email: str = Form(...),
                          password: str = Form(...), role: str = Form("user")):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    ok, msg = auth.create_user(name, email, password, role)
    return JSONResponse({"ok": ok, "message": msg})


@router.put("/admin/api/users/{user_id}")
async def api_update_user(user_id: int, request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    body  = await request.json()
    ok, msg = auth.update_user(
        user_id,
        body.get("name", ""), body.get("email", ""),
        body.get("role", "user"), int(body.get("is_active", 1)),
        body.get("password", "")
    )
    return JSONResponse({"ok": ok, "message": msg})


@router.delete("/admin/api/users/{user_id}")
async def api_delete_user(user_id: int, request: Request):
    admin = require_admin(request)
    if not admin:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if admin["id"] == user_id:
        return JSONResponse({"error": "Cannot delete your own account"}, status_code=400)
    auth.delete_user(user_id)
    return JSONResponse({"ok": True})


@router.get("/admin/api/users/{user_id}")
async def api_get_user(user_id: int, request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    user = auth.get_user_by_id(user_id)
    if not user:
        return JSONResponse({"error": "Not found"}, status_code=404)
    user.pop("password", None)
    return JSONResponse(user)


@router.delete("/admin/api/projects/{project_id}")
async def api_delete_project(project_id: int, request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    auth.delete_project(project_id)
    return JSONResponse({"ok": True})


# ── QC Items CRUD ──────────────────────────────────────────────────────────

@router.get("/admin/api/qc-items")
async def api_list_qc_items(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    return JSONResponse(auth.get_all_qc_items(active_only=False))


@router.post("/admin/api/qc-items")
async def api_create_qc_item(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    body = await request.json()
    ok, msg = auth.create_qc_item(
        body.get("sno", ""),
        body.get("label", ""),
        body.get("key", ""),
        body.get("check_type", "ai"),
        int(body.get("sort_order", 999)),
    )
    return JSONResponse({"ok": ok, "message": msg}, status_code=200 if ok else 400)


@router.put("/admin/api/qc-items/{item_id}")
async def api_update_qc_item(item_id: int, request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    body = await request.json()
    ok, msg = auth.update_qc_item(
        item_id,
        body.get("sno", ""),
        body.get("label", ""),
        body.get("key", ""),
        body.get("check_type", "ai"),
        int(body.get("sort_order", 999)),
        int(body.get("is_active", 1)),
    )
    return JSONResponse({"ok": ok, "message": msg}, status_code=200 if ok else 400)


@router.delete("/admin/api/qc-items/{item_id}")
async def api_delete_qc_item(item_id: int, request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    auth.delete_qc_item(item_id)
    return JSONResponse({"ok": True})


# ── Backup / Restore ───────────────────────────────────────────────────────

@router.get("/admin/backup")
async def download_backup(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    buf = io.BytesIO()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add the SQLite DB
        if DB_PATH.exists():
            zf.write(DB_PATH, arcname="data/app.db")

        # Add all upload session folders
        if UPLOAD_DIR.exists():
            for item in UPLOAD_DIR.rglob("*"):
                if item.is_file() and item.name != ".gitkeep":
                    zf.write(item, arcname=str(item).replace("\\", "/"))

    buf.seek(0)
    filename = f"qc_backup_{timestamp}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/admin/restore")
async def upload_restore(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    body = await request.body()
    if not body:
        return JSONResponse({"ok": False, "error": "No file received"}, status_code=400)

    try:
        buf = io.BytesIO(body)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

            # Restore DB
            if "data/app.db" in names:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                DB_PATH.write_bytes(zf.read("data/app.db"))

            # Restore upload folders
            for name in names:
                if name.startswith("uploads/") and not name.endswith("/"):
                    dest = Path(name)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(name))

        return JSONResponse({"ok": True, "files": len(names)})
    except zipfile.BadZipFile:
        return JSONResponse({"ok": False, "error": "Invalid zip file"}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
