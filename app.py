import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


HOST = "127.0.0.1"
PORT = 8000
DATA_FILE = Path(__file__).with_name("tasks.json")


class TaskStore:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = Path(data_file)
        self.tasks = self._load()

    def _load(self):
        if not self.data_file.exists():
            return []

        with self.data_file.open("r", encoding="utf-8") as file:
            tasks = json.load(file)

        if not isinstance(tasks, list):
            raise ValueError("The task data file must contain a JSON list.")
        for task in tasks:
            if (
                not isinstance(task, dict)
                or not isinstance(task.get("id"), int)
                or not isinstance(task.get("title"), str)
                or not isinstance(task.get("done"), bool)
            ):
                raise ValueError("The task data file contains an invalid task.")
        return tasks

    def _save(self):
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(self.tasks, file, indent=2)
            file.write("\n")

    def add(self, title):
        title = title.strip()
        if not title:
            raise ValueError("Please enter a task.")
        if len(title) > 200:
            raise ValueError("Tasks must be 200 characters or fewer.")

        task = {
            "id": max((item["id"] for item in self.tasks), default=0) + 1,
            "title": title,
            "done": False,
        }
        self.tasks.append(task)
        self._save()

    def toggle(self, task_id):
        task = self._find(task_id)
        task["done"] = not task["done"]
        self._save()

    def delete(self, task_id):
        task = self._find(task_id)
        self.tasks.remove(task)
        self._save()

    def _find(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        raise ValueError("That task could not be found.")


def render_page(tasks, error=""):
    task_rows = []
    for task in tasks:
        task_id = task["id"]
        title = html.escape(task["title"])
        done_class = " done" if task["done"] else ""
        task_rows.append(
            f"""
            <li class="task{done_class}">
              <form method="post">
                <input type="hidden" name="action" value="toggle">
                <input type="hidden" name="id" value="{task_id}">
                <button class="check" aria-label="Toggle task status">
                  {"&#10003;" if task["done"] else ""}
                </button>
              </form>
              <span>{title}</span>
              <form method="post">
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="id" value="{task_id}">
                <button class="delete" aria-label="Delete task">&times;</button>
              </form>
            </li>"""
        )

    content = "\n".join(task_rows) or '<li class="empty">Nothing here yet. Add your first task.</li>'
    error_message = f'<p class="error">{html.escape(error)}</p>' if error else ""
    remaining = sum(not task["done"] for task in tasks)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>My Tasks</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; padding: 56px 20px;
      background: #f3f5f9; color: #202638;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 620px; margin: 0 auto; padding: 36px;
      background: white; border: 1px solid #e6e9f0; border-radius: 18px;
      box-shadow: 0 16px 50px #26335412;
    }}
    h1 {{ margin: 0; font-size: 30px; letter-spacing: -1px; }}
    .subtitle {{ margin: 6px 0 26px; color: #727b8c; }}
    .add {{ display: flex; gap: 10px; }}
    input[name="title"] {{
      flex: 1; min-width: 0; padding: 12px 14px;
      border: 1px solid #dce1ea; border-radius: 9px; font: inherit;
    }}
    button {{ cursor: pointer; font: inherit; }}
    .add button {{
      padding: 0 18px; border: 0; border-radius: 9px;
      background: #5168e8; color: white; font-weight: 650;
    }}
    ul {{ list-style: none; margin: 22px 0 0; padding: 0; }}
    .task {{
      display: flex; align-items: center; gap: 12px; padding: 13px 2px;
      border-bottom: 1px solid #edf0f4;
    }}
    .task span {{ flex: 1; overflow-wrap: anywhere; }}
    .task.done span {{ color: #9299a7; text-decoration: line-through; }}
    .task form {{ margin: 0; }}
    .check {{
      width: 24px; height: 24px; border: 1.5px solid #c9cfdb;
      border-radius: 50%; background: white; color: #5168e8; padding: 0;
    }}
    .done .check {{ border-color: #5168e8; }}
    .delete {{ border: 0; background: transparent; color: #9aa1ad; font-size: 23px; }}
    .delete:hover {{ color: #d24f5b; }}
    .empty {{ padding: 26px 0; color: #858d9b; text-align: center; }}
    .footer {{ margin: 20px 0 0; color: #858d9b; font-size: 14px; }}
    .error {{
      margin: 12px 0 0; padding: 10px 12px; border-radius: 8px;
      background: #fff0f0; color: #a92e3a;
    }}
    @media (max-width: 520px) {{ main {{ padding: 26px 20px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>My Tasks</h1>
    <p class="subtitle">A little progress, every day.</p>
    <form class="add" method="post">
      <input type="hidden" name="action" value="add">
      <input name="title" type="text" maxlength="200" placeholder="What needs doing?" required autofocus>
      <button type="submit">Add task</button>
    </form>
    {error_message}
    <ul>{content}</ul>
    <p class="footer">{remaining} task{"s" if remaining != 1 else ""} remaining</p>
  </main>
</body>
</html>"""


class TaskHandler(BaseHTTPRequestHandler):
    store = None

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        self._send_page()

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 10_000:
                raise ValueError("Invalid form submission.")
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            action = form.get("action", [""])[0]

            if action == "add":
                self.store.add(form.get("title", [""])[0])
            elif action in ("toggle", "delete"):
                task_id = int(form.get("id", [""])[0])
                if action == "toggle":
                    self.store.toggle(task_id)
                else:
                    self.store.delete(task_id)
            else:
                raise ValueError("Unknown action.")
        except (UnicodeDecodeError, ValueError) as error:
            self._send_page(str(error), status=400)
            return

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def _send_page(self, error="", status=200):
        body = render_page(self.store.tasks, error).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def main():
    TaskHandler.store = TaskStore()
    address = f"http://{HOST}:{PORT}"
    with ThreadingHTTPServer((HOST, PORT), TaskHandler) as server:
        print(f"To-do app running at {address} (press Ctrl+C to stop)")
        threading.Timer(0.8, webbrowser.open, args=(address,)).start()
        server.serve_forever()


if __name__ == "__main__":
    main()
