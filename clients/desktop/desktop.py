"""Native desktop data explorer and local graphical workbench launcher."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RESULTS = "results/socioeconomic/four-year-exploratory"
COLUMNS = [("year", "年份"), ("district", "区县"), ("group", "区组"), ("built_km2", "不透水面 km²"),
           ("expansion_km2", "阶段净增 km²"), ("population", "常住人口"), ("gdp_10k_cny", "GDP 万元"),
           ("intensive_score", "集约得分"), ("rank", "年度排名")]


def resources():
    archive = Path(sys.argv[0])
    if archive.is_file() and zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            return {path.removeprefix("assets/"): z.read(path) for path in z.namelist()
                    if path.startswith("assets/") and not path.endswith("/")}
    assets = {p.name: p.read_bytes() for p in (ROOT / "web").iterdir() if p.is_file()}
    for name in ("dashboard.json", "districts.geojson"):
        assets[name] = (ROOT / RESULTS / name).read_bytes()
    return assets


def local_server(assets, port=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            key = urlsplit(self.path).path.removeprefix("/") or "index.html"
            data = b"{}" if key == "api/config" else assets.get(key)
            if data is None:
                self.send_error(404)
                return
            types = {".js": "text/javascript", ".css": "text/css", ".html": "text/html",
                     ".png": "image/png", ".webp": "image/webp", ".webmanifest": "application/manifest+json"}
            self.send_response(200)
            self.send_header("Content-Type", types.get(Path(key).suffix, "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def browser_app(url):
    candidates = ["chromium", "google-chrome", "msedge", "chrome",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates += [str(Path(base) / sub) for sub in
                           ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe")]
    for exe in candidates:
        if shutil.which(exe):
            subprocess.Popen([exe, "--app=" + url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    webbrowser.open(url)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify packaged data without opening a window.")
    args = parser.parse_args()
    assets = resources()
    records = json.loads(assets["dashboard.json"])
    features = json.loads(assets["districts.geojson"])["features"]
    if len(records) != 84 or len(features) != 21:
        raise ValueError("Incomplete embedded study data")
    if args.check:
        with local_server(assets) as server:
            import urllib.request
            t = threading.Thread(target=server.handle_request)
            t.start()
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/dashboard.json") as response:
                assert json.load(response) == records
            t.join()
        print("Desktop resources verified: 21 districts, 84 observations.")
        return
    import tkinter as tk
    from tkinter import filedialog, ttk
    window = tk.Tk()
    window.title("山城地研 · 桌面研究台")
    window.geometry("1080x680")
    server = local_server(assets, 38422)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    toolbar = ttk.Frame(window, padding=14)
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="重庆土地利用研究台", font=("", 17, "bold")).pack(side="left")
    ttk.Button(toolbar, text="打开桌面分析台",
               command=lambda: browser_app(f"http://127.0.0.1:{server.server_port}/desktop.html")).pack(side="right")
    controls = ttk.Frame(window, padding=10)
    controls.pack(fill="x")
    year = tk.StringVar(value="2022")
    area = tk.StringVar()
    for label, widget in [
        ("观测年份", ttk.Combobox(controls, textvariable=year, values=["全部","2010","2015","2020","2022"], state="readonly", width=8)),
        ("区县检索", ttk.Entry(controls, textvariable=area, width=16)),
    ]:
        ttk.Label(controls, text=label).pack(side="left", padx=4)
        widget.pack(side="left", padx=4)
    container = ttk.Frame(window)
    container.pack(expand=True, fill="both", padx=12)
    grid = ttk.Treeview(container, columns=[k for k, _ in COLUMNS], show="headings")
    scroll = ttk.Scrollbar(container, command=grid.yview)
    grid.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right",fill="y")
    grid.pack(fill="both",expand=True)
    for key, label in COLUMNS:
        grid.heading(key, text=label)
        grid.column(key, width=104, minwidth=52, anchor="center")
    status = tk.StringVar()
    ttk.Label(window, textvariable=status, padding=10).pack(fill="x")
    def filtered():
        return [r for r in records if year.get() in ("全部", str(r["year"])) and
                (area.get() in r["district"] or area.get() in r["code"])]
    def refresh(*_):
        rows = filtered()
        grid.delete(*grid.get_children())
        for r in sorted(rows, key=lambda r:(r["year"],r["rank"])):
            grid.insert("", "end", values=["—" if r.get(k) is None else
                        round(r[k],4) if isinstance(r[k],float) else r[k] for k,_ in COLUMNS])
        status.set(f"{len(rows)} 条区年观测　｜　GDP 为现价，四期评分含早期待复核记录")
    def export():
        target = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if target:
            with open(target,"w",encoding="utf-8-sig",newline="") as f:
                writer = csv.DictWriter(f,fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(filtered())
    ttk.Button(controls,text="导出 CSV",command=export).pack(side="right")
    year.trace_add("write",refresh)
    area.trace_add("write",refresh)
    refresh()
    try:
        window.mainloop()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run()
