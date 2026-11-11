file_path = "D:/AGROBOTAI/server.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import re

target = """# Serve static React frontend files if built
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")"""

replacement = """# Serve static React frontend files if built
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    @app.middleware("http")
    async def add_cache_control_header(request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched server.py successfully.")
else:
    print("Could not find target in server.py")
