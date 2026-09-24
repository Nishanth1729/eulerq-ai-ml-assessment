from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd


class EulerQApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EulerQ — Offline Text-to-SQL")
        self.root.geometry("1180x800")
        self.root.minsize(980, 680)
        self.root.configure(bg="#f3f6fb")
        self.schema_path = tk.StringVar()
        self.csv_path = tk.StringVar()
        self.table_name = tk.StringVar()
        self.data: pd.DataFrame | None = None
        self.schema = None
        self.service = None
        self._style()
        self._layout()

    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TFrame", background="#f3f6fb")
        s.configure("Card.TFrame", background="#ffffff")
        s.configure("TLabel", background="#f3f6fb", foreground="#17243a", font=("Segoe UI", 10))
        s.configure("Card.TLabel", background="#ffffff", foreground="#17243a", font=("Segoe UI", 10))
        s.configure("Title.TLabel", background="#f3f6fb", foreground="#14233b", font=("Segoe UI", 21, "bold"))
        s.configure("Sub.TLabel", background="#f3f6fb", foreground="#607087", font=("Segoe UI", 10))
        s.configure("Green.TLabel", background="#e7f7ef", foreground="#147d4b", font=("Segoe UI", 10, "bold"), padding=7)
        s.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 9))
        s.map("Accent.TButton", background=[("!disabled", "#2459d3"), ("active", "#1746b1")], foreground=[("!disabled", "white")])
        s.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _layout(self):
        header = ttk.Frame(self.root, padding=(24, 18, 24, 12)); header.pack(fill="x")
        left = ttk.Frame(header); left.pack(side="left")
        ttk.Label(left, text="EulerQ — Offline Text-to-SQL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Schema-Agnostic AI Data Assistant", style="Sub.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Label(header, text="● Offline / Local AI", style="Green.TLabel").pack(side="right", anchor="n")

        body = ttk.Frame(self.root, padding=(20, 0, 20, 12)); body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, minsize=330); body.columnconfigure(1, weight=2); body.rowconfigure(0, weight=1)
        self._data_panel(body)
        self._work_panel(body)

        self.status = tk.StringVar(value="Choose a schema and table to connect local data.")
        ttk.Label(self.root, textvariable=self.status, anchor="w", padding=(22, 8), background="#e9eef6").pack(fill="x", side="bottom")

    def _card(self, parent, title):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
        ttk.Label(frame, text=title, style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        return frame

    def _data_panel(self, parent):
        panel = ttk.Frame(parent); panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10)); panel.rowconfigure(2, weight=1)
        card = self._card(panel, "DATA & RUNTIME SCHEMA"); card.pack(fill="x", pady=(0, 10))
        self._path_row(card, "Schema JSON", self.schema_path, self._browse_schema)
        self._path_row(card, "CSV data (optional)", self.csv_path, self._browse_csv)
        row = ttk.Frame(card, style="Card.TFrame"); row.pack(fill="x", pady=(5, 0))
        ttk.Label(row, text="Table name", style="Card.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.table_name, width=22).pack(side="right", fill="x", expand=True, padx=(8, 0))
        ttk.Button(card, text="Load schema and data", command=self.load_runtime).pack(anchor="e", pady=(10, 0))

        self.summary = ttk.Label(panel, text="No data loaded", style="Card.TLabel", padding=12)
        self.summary.pack(fill="x", pady=(0, 10))
        card2 = self._card(panel, "SCHEMA COLUMNS"); card2.pack(fill="both", expand=True, pady=(0, 10))
        self.columns = ttk.Treeview(card2, columns=("name", "description"), show="headings", height=10)
        self.columns.heading("name", text="Column"); self.columns.heading("description", text="Description")
        self.columns.column("name", width=125, stretch=False); self.columns.column("description", width=210, stretch=True)
        self.columns.pack(fill="both", expand=True)
        info = self._card(panel, "LOCAL MODEL"); info.pack(fill="x")
        ttk.Label(info, text="SLM: local  •  T5: local\nInference: offline  •  Ollama: not required\nAPI key: not required", style="Card.TLabel", justify="left").pack(anchor="w")

    def _path_row(self, parent, label, variable, command):
        frame = ttk.Frame(parent, style="Card.TFrame"); frame.pack(fill="x", pady=4)
        ttk.Label(frame, text=label, style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(frame, style="Card.TFrame"); row.pack(fill="x", pady=(3, 0))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=command).pack(side="right", padx=(5, 0))

    def _work_panel(self, parent):
        panel = ttk.Frame(parent); panel.grid(row=0, column=1, sticky="nsew"); panel.rowconfigure(3, weight=1); panel.columnconfigure(0, weight=1)
        card = self._card(panel, "ASK YOUR DATA"); card.grid(row=0, column=0, sticky="ew", pady=(0, 10)); card.columnconfigure(0, weight=1)
        self.question = tk.Text(card, height=4, wrap="word", font=("Segoe UI", 11), relief="solid", borderwidth=1, padx=9, pady=8)
        self.question.insert("1.0", "Ask a question about your data..."); self.question.pack(fill="x")
        actions = ttk.Frame(card, style="Card.TFrame"); actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Ask / Generate SQL", style="Accent.TButton", command=self.ask).pack(side="left")
        ttk.Button(actions, text="Clear", command=self.clear).pack(side="left", padx=8)
        self.examples = ttk.Frame(card, style="Card.TFrame"); self.examples.pack(fill="x", pady=(10, 0), anchor="w")

        sqlcard = self._card(panel, "GENERATED SQL"); sqlcard.grid(row=1, column=0, sticky="ew", pady=(0, 10)); sqlcard.columnconfigure(0, weight=1)
        row = ttk.Frame(sqlcard, style="Card.TFrame"); row.pack(fill="x")
        self.sql_text = tk.Text(row, height=4, wrap="word", font=("Consolas", 10), bg="#111c2e", fg="#d7e3fa", insertbackground="white", relief="flat", padx=10, pady=9)
        self.sql_text.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Copy SQL", command=self.copy_sql).pack(side="right", padx=(8, 0), anchor="n")

        result_card = self._card(panel, "QUERY RESULT"); result_card.grid(row=3, column=0, sticky="nsew")
        self.result = ttk.Treeview(result_card, show="headings"); self.result.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(result_card, orient="vertical", command=self.result.yview); yscroll.pack(side="right", fill="y"); self.result.configure(yscrollcommand=yscroll.set)

    def _browse_schema(self):
        path = filedialog.askopenfilename(filetypes=[("JSON schema", "*.json"), ("All files", "*.*")])
        if path: self.schema_path.set(path)

    def _browse_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV data", "*.csv"), ("All files", "*.*")])
        if path: self.csv_path.set(path)

    def load_runtime(self):
        try:
            if not self.schema_path.get() or not self.table_name.get().strip():
                raise ValueError("Select a schema JSON and enter a table name.")
            schema = json.loads(Path(self.schema_path.get()).read_text(encoding="utf-8"))
            if not isinstance(schema, list) or not schema:
                raise ValueError("Schema must be a non-empty JSON list of column definitions.")
            if self.csv_path.get():
                data = pd.read_csv(self.csv_path.get())
                missing = [x["name"] for x in schema if x["name"] not in data.columns]
                if missing: raise ValueError("CSV is missing schema columns: " + ", ".join(missing))
            else: data = None
            from app import TextToSQL
            # Reuse the same service class and bundled models as CLI/validation.
            self.service = TextToSQL(schema, data=data, table=self.table_name.get().strip())
            self.schema, self.data = schema, data
            for item in self.columns.get_children(): self.columns.delete(item)
            for item in schema: self.columns.insert("", "end", values=(item["name"], item.get("description", "")))
            file = Path(self.csv_path.get()).name if self.csv_path.get() else "No CSV"
            self.summary.configure(text=f"{file}\nTable: {self.table_name.get()}  •  Rows: {len(data) if data is not None else '—'}  •  Columns: {len(schema)}")
            self._make_examples()
            self.status.set("Schema and local models loaded successfully.")
        except Exception as exc:
            messagebox.showerror("Could not load data", str(exc))
            self.status.set("Load failed. Check the schema, CSV and table name.")

    def _make_examples(self):
        for child in self.examples.winfo_children(): child.destroy()
        if not self.schema: return
        names = [x["name"].replace("_", " ") for x in self.schema]
        candidates = [f"Show all rows with their {names[0]}."]
        if self.data is not None:
            for item in self.schema:
                col = item["name"]
                if col in self.data and not pd.api.types.is_numeric_dtype(self.data[col]):
                    values = self.data[col].dropna().astype(str)
                    if not values.empty:
                        candidates.append(f"Show all rows where {names[self.schema.index(item)]} is {values.iloc[0]}.")
                        break
        for item in self.schema:
            col = item["name"]
            if self.data is not None and col in self.data and pd.api.types.is_numeric_dtype(self.data[col]):
                candidates.extend([f"Show the top 5 rows by {col.replace('_', ' ')}.", f"What is the average {col.replace('_', ' ')}?"])
                break
        ttk.Label(self.examples, text="Examples:", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        for question in candidates[:3]:
            ttk.Button(self.examples, text=question, command=lambda q=question: self._set_question(q)).pack(anchor="w", pady=2)

    def _set_question(self, value):
        self.question.delete("1.0", "end"); self.question.insert("1.0", value)

    def clear(self):
        self.question.delete("1.0", "end"); self.sql_text.delete("1.0", "end")
        for item in self.result.get_children(): self.result.delete(item)
        self.result["columns"] = ()

    def copy_sql(self):
        sql = self.sql_text.get("1.0", "end").strip()
        if sql:
            self.root.clipboard_clear(); self.root.clipboard_append(sql); self.status.set("SQL copied to clipboard.")

    def ask(self):
        question = self.question.get("1.0", "end").strip()
        if not self.service:
            messagebox.showinfo("Load data first", "Choose a schema, table and optional CSV, then click Load schema and data.")
            return
        if not question or question == "Ask a question about your data...":
            messagebox.showinfo("Enter a question", "Type a question about the loaded data."); return
        self.status.set("Generating with local models…")
        threading.Thread(target=self._run_question, args=(question,), daemon=True).start()

    def _run_question(self, question):
        start = time.perf_counter()
        try:
            generated = self.service.generate(question)
            sql = generated["sql"]
            self.service.validate_sql(sql)
            frame = None
            if self.data is not None:
                con = sqlite3.connect(":memory:")
                try:
                    self.data.to_sql(self.table_name.get().strip(), con, index=False, if_exists="replace")
                    frame = pd.read_sql_query(sql, con)
                finally: con.close()
            elapsed = time.perf_counter() - start
            self.root.after(0, lambda: self._show_result(sql, frame, elapsed))
        except ValueError as exc:
            msg = str(exc)
            text = "Unsafe SQL blocked. Only safe read-only SELECT queries are allowed." if any(k in msg.lower() for k in ("unsafe", "destructive", "unsupported sql", "only one select")) else msg
            self.root.after(0, lambda message=text: self._show_error(message))
        except Exception as exc:
            message = f"Could not answer that question: {exc}"
            self.root.after(0, lambda message=message: self._show_error(message))

    def _show_result(self, sql, frame, elapsed):
        self.sql_text.delete("1.0", "end"); self.sql_text.insert("1.0", sql)
        for item in self.result.get_children(): self.result.delete(item)
        if frame is not None:
            columns = [str(c) for c in frame.columns]
            self.result.configure(columns=columns, show="headings")
            for c in columns: self.result.heading(c, text=c); self.result.column(c, width=120, stretch=True)
            for row in frame.head(500).itertuples(index=False, name=None): self.result.insert("", "end", values=[str(v) for v in row])
            self.status.set(f"Success  •  {len(frame):,} rows  •  {elapsed:.2f}s")
        else: self.status.set(f"SQL generated and validated  •  no CSV loaded  •  {elapsed:.2f}s")

    def _show_error(self, message):
        self.status.set(message)
        messagebox.showwarning("Query not run", message)


def launch_gui():
    root = tk.Tk()
    EulerQApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
