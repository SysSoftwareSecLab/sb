"""Offline conflict-only adjudication UI; used after both independent returns exist."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


def run() -> None:
    root_dir = Path(__file__).resolve().parent
    manifest = json.loads((root_dir / "ITEMS.json").read_text(encoding="utf-8"))
    returns = []
    for reviewer in ("Reviewer1", "Reviewer2"):
        path = root_dir / f"RETURN_{reviewer}.json"
        if not path.exists():
            messagebox.showerror("不能开始", f"缺少 {path.name}；两位独立初审完成后才能裁决。")
            return
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") != "COMPLETE":
            messagebox.showerror("不能开始", f"{path.name} 尚未标记完成。")
            return
        returns.append(value)
    by_id = [{key: value for key, value in record["answers"].items()} for record in returns]
    conflicts = []
    for item in manifest:
        left, right = by_id[0][item["blind_id"]], by_id[1][item["blind_id"]]
        fields = ("treatment_integrity", "P_exposure", "P_label")
        if any(left[field] != right[field] for field in fields) or left["P_label"] == "U" or left["P_exposure"] == "UNCLEAR" or left["treatment_integrity"] == "UNCLEAR":
            conflicts.append(item)
    output = root_dir / "RETURN_ADJUDICATION.json"
    record = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
        "schema": "paper3.rq2.human_adjudication_return.v1",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "answers": {},
    }
    if not conflicts:
        record.update(status="COMPLETE_NO_CONFLICTS", completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo("无需裁决", "两位初审没有需裁决项目，已保存完成记录。")
        return

    window = tk.Tk()
    window.title("Paper3 RQ2 冲突裁决")
    window.geometry("1450x900")
    index = 0
    integrity, exposure, p_label = tk.StringVar(), tk.StringVar(), tk.StringVar()
    header = ttk.Label(window, font=("TkDefaultFont", 12, "bold"))
    header.pack(fill="x", padx=8, pady=5)
    pane = ttk.Panedwindow(window, orient="horizontal")
    pane.pack(fill="both", expand=True, padx=8)
    left_text, right_text = tk.Text(pane, wrap="none"), tk.Text(pane, wrap="none")
    pane.add(left_text, weight=1); pane.add(right_text, weight=1)
    controls = ttk.Frame(window); controls.pack(fill="x", padx=8, pady=6)
    for title, variable, values in (
        ("结构", integrity, ("MET", "NOT_MET", "UNCLEAR")),
        ("暴露", exposure, ("EXPOSED", "NOT_EXPOSED", "UNCLEAR")),
        ("P结论", p_label, ("C", "V", "U")),
    ):
        ttk.Label(controls, text=title).pack(side="left", padx=(8, 2))
        for value in values:
            ttk.Radiobutton(controls, text=value, variable=variable, value=value).pack(side="left")
    ttk.Label(controls, text="理由").pack(side="left", padx=(12, 2))
    rationale = ttk.Entry(controls, width=55); rationale.pack(side="left", fill="x", expand=True)

    def show() -> None:
        item = conflicts[index]
        payload = json.loads((root_dir / item["item_path"]).read_text(encoding="utf-8"))
        saved = record["answers"].get(item["blind_id"], {})
        integrity.set(saved.get("treatment_integrity", "")); exposure.set(saved.get("P_exposure", "")); p_label.set(saved.get("P_label", ""))
        rationale.delete(0, "end"); rationale.insert(0, saved.get("rationale", ""))
        header.config(text=f'{index+1}/{len(conflicts)}  {item["blind_id"]}  冲突裁决')
        left_text.delete("1.0", "end")
        left_text.insert("1.0", "两位独立初审\n" + json.dumps({returns[0]["reviewer"]: by_id[0][item["blind_id"]], returns[1]["reviewer"]: by_id[1][item["blind_id"]]}, ensure_ascii=False, indent=2) + "\n\n公开任务与P定义\n" + json.dumps(payload["public_evidence"], ensure_ascii=False, indent=2))
        right_text.delete("1.0", "end")
        right_text.insert("1.0", "原子源码\n" + payload["atomic_source"] + "\n\n组合源码\n" + payload["composed_source"] + "\n\n代表可信轨迹\n" + json.dumps(payload["representative_traces"], ensure_ascii=False, indent=2))

    def save() -> bool:
        nonlocal index
        if not integrity.get() or not exposure.get() or not p_label.get() or not rationale.get().strip():
            messagebox.showwarning("未完成", "三项和裁决理由均必填。")
            return False
        blind_id = conflicts[index]["blind_id"]
        record["answers"][blind_id] = {"treatment_integrity": integrity.get(), "P_exposure": exposure.get(), "P_label": p_label.get(), "rationale": rationale.get().strip(), "saved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True

    def next_item() -> None:
        nonlocal index
        if not save(): return
        if index + 1 < len(conflicts):
            index += 1; show()
        elif len(record["answers"]) == len(conflicts):
            record.update(status="COMPLETE", completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            messagebox.showinfo("完成", f"已保存 {output.name}")

    ttk.Button(window, text="保存并下一项 / 完成", command=next_item).pack(pady=(0, 8))
    show(); window.mainloop()
