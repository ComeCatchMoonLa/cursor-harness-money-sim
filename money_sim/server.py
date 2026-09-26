"""本地图形界面。页面上的金额都来自这里返回的状态，不在浏览器里另算。"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from money_sim.constants import LOG_FIELDS, REGIME_LABEL
from money_sim.economy import exit_pct, living_cost, salary
from money_sim.engine import preview, resolve
from money_sim.state import Plan, from_save_dict, new_game, public_view, to_save_dict

WEB = Path(__file__).resolve().parent.parent / "web"
STAGE_LABEL = {"none": "还没有副业", "building": "建造中", "running": "在经营"}


class Session:
    def __init__(self, log_path: Path, save_path: Path, seed: int | None = None):
        self.log_path = log_path
        self.save_path = save_path
        self.state = new_game(seed)
        self.recent: list[dict] = []
        self.lock = threading.Lock()

    def payload(self) -> dict:
        state = self.state
        view = public_view(state)
        view["salary_full"] = salary(state.career, state.network, "full")
        view["salary_part"] = salary(state.career, state.network, "part")
        view["living"] = living_cost(state.lifestyle, state.price_index)
        view["regime_label"] = REGIME_LABEL.get(state.regime, state.regime)
        view["stage_label"] = STAGE_LABEL.get(state.business_stage, state.business_stage)
        pct = exit_pct(state.business_stage, state.last_business_net, 0, False)
        view["exit_value"] = state.business_book * pct // 100 if state.business_stage != "none" else 0
        view["recent"] = list(self.recent[-8:])
        return view

    def remember(self, report: dict) -> None:
        slim = {key: report[key] for key in LOG_FIELDS}
        slim["notes"] = list(report.get("notes") or [])
        slim["regime"] = report.get("regime")
        slim["employment"] = report.get("employment")
        slim["slots"] = list(report.get("slots") or [])
        self.recent.append(slim)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, ensure_ascii=False) + "\n")


def parse_plan(data: dict) -> Plan:
    if not isinstance(data, dict):
        raise ValueError("方案必须是对象")

    def num(key: str) -> int:
        value = data.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key}必须是数字")
        return int(value)

    slots = data.get("slots", [])
    if not isinstance(slots, list) or not all(isinstance(item, str) for item in slots):
        raise ValueError("时间槽无效")
    employment = data.get("employment", "")
    if not isinstance(employment, str):
        raise ValueError("就业形态无效")
    return Plan(
        employment=employment,
        slots=list(slots),
        to_index=num("to_index"),
        from_index=num("from_index"),
        to_business=num("to_business"),
        debt_pay=num("debt_pay"),
        consume_cash=num("consume_cash"),
        risk_pct=num("risk_pct"),
        automate=bool(data.get("automate", False)),
        exit_business=bool(data.get("exit_business", False)),
        accept_offer=bool(data.get("accept_offer", False)),
    )


def make_server(host: str, port: int, log_path: Path, save_path: Path, seed: int | None = None) -> ThreadingHTTPServer:
    session = Session(log_path, save_path, seed)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _file(self, name: str) -> None:
            path = (WEB / name).resolve()
            if not str(path).startswith(str(WEB.resolve())) or not path.is_file():
                self._json(404, {"error": "找不到页面"})
                return
            kind = "text/html" if path.suffix == ".html" else "text/css" if path.suffix == ".css" else "text/javascript"
            raw = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._file("index.html")
                return
            if path.startswith("/static/"):
                self._file(path.removeprefix("/static/"))
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if path == "/api/state":
                with session.lock:
                    self._json(200, session.payload())
                return
            self._json(404, {"error": "没有这个接口"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                data = self._read()
            except json.JSONDecodeError:
                self._json(400, {"error": "JSON 无法解析"})
                return
            with session.lock:
                if path == "/api/new":
                    seed = data.get("seed")
                    session.state = new_game(None if seed in (None, "") else int(seed))
                    session.recent = []
                    self._json(200, session.payload())
                    return
                if path == "/api/preview":
                    try:
                        plan = parse_plan(data)
                    except ValueError as exc:
                        self._json(400, {"ok": False, "errors": [str(exc)], "warnings": []})
                        return
                    self._json(200, preview(session.state, plan))
                    return
                if path == "/api/resolve":
                    try:
                        plan = parse_plan(data)
                    except ValueError as exc:
                        self._json(400, {"errors": [str(exc)]})
                        return
                    state, errors, report = resolve(session.state, plan)
                    if errors:
                        self._json(200, {"errors": errors, "state": session.payload()})
                        return
                    session.state = state
                    session.remember(report)
                    self._json(200, {"errors": [], "state": session.payload()})
                    return
                if path == "/api/save":
                    session.save_path.parent.mkdir(parents=True, exist_ok=True)
                    session.save_path.write_text(
                        json.dumps(to_save_dict(session.state), ensure_ascii=False),
                        encoding="utf-8",
                    )
                    self._json(200, {"ok": True, "state": session.payload()})
                    return
                if path == "/api/load":
                    if not session.save_path.is_file():
                        self._json(404, {"error": "没有存档"})
                        return
                    session.state = from_save_dict(json.loads(session.save_path.read_text(encoding="utf-8")))
                    # 读档回到更早的月份时，不能继续显示读档之后才发生的结算。
                    session.recent = []
                    self._json(200, {"ok": True, "state": session.payload()})
                    return
            self._json(404, {"error": "没有这个接口"})

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="启动九年账")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log", default="logs/game.jsonl")
    parser.add_argument("--save", default="saves/manual.json")
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port, Path(args.log), Path(args.save))
    print(f"九年账 http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
