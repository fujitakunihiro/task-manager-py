import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import json
import time
import os
from datetime import datetime

DATA_FILE = "tasks_std_v24.json"

class TaskTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Manager (UI Fixed)")
        self.root.geometry("1100x800")

        self.is_running = False
        self.start_time = 0
        self.selected_task_index = None
        self.is_edit_mode = False 
        self.data = self.load_data()

        self.setup_ui()

    def format_seconds(self, seconds):
        hrs, rem = divmod(int(seconds), 3600)
        mins, secs = divmod(rem, 60)
        return f"{hrs:02}:{mins:02}:{secs:02}"

    def setup_ui(self):
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=4)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # --- 左側: 入力・リストエリア ---
        self.left_frame = tk.Frame(self.main_paned, padx=10, pady=10)
        self.main_paned.add(self.left_frame, width=400)

        self.input_title_label = tk.Label(self.left_frame, text="タスク登録・編集", font=("Arial", 11, "bold"))
        self.input_title_label.pack(pady=5)
        
        self.entries = {}
        for label_text, key in [("タスク名", "name"), ("作業者", "worker"), ("予定(h)", "estimate")]:
            tk.Label(self.left_frame, text=label_text, font=("Arial", 9)).pack(anchor="w")
            ent = tk.Entry(self.left_frame)
            ent.pack(fill="x", pady=1)
            self.entries[key] = ent
        
        now = datetime.now()
        current_year = now.year
        years = [str(i) for i in range(current_year - 1, current_year + 6)]

        for title, prefix in [("開始日", "s"), ("期限日", "e")]:
            f = tk.Frame(self.left_frame)
            f.pack(fill="x", pady=2)
            tk.Label(f, text=title, font=("Arial", 9), width=6).pack(side=tk.LEFT)
            y_cb = ttk.Combobox(f, values=years, width=5, state="readonly")
            y_cb.set(str(current_year)); y_cb.pack(side=tk.LEFT)
            m_cb = ttk.Combobox(f, values=[f"{i:02}" for i in range(1, 13)], width=3, state="readonly")
            m_cb.set(now.strftime("%m")); m_cb.pack(side=tk.LEFT, padx=2)
            d_cb = ttk.Combobox(f, values=[f"{i:02}" for i in range(1, 32)], width=3, state="readonly")
            d_cb.set(now.strftime("%d")); d_cb.pack(side=tk.LEFT)
            setattr(self, f"{prefix}_year_cb", y_cb)
            setattr(self, f"{prefix}_month_cb", m_cb)
            setattr(self, f"{prefix}_day_cb", d_cb)
        
        # ボタンエリアの構成を修正
        self.action_btn = tk.Button(self.left_frame, text="タスクを追加", command=self.handle_action, bg="#e1e1e1")
        self.action_btn.pack(fill="x", pady=(10, 2))
        
        # キャンセルボタンをあらかじめ作成し、初期状態は隠す
        self.cancel_btn = tk.Button(self.left_frame, text="編集をキャンセル", command=self.exit_edit_mode, bg="#f8d7da")
        
        # Treeview (表形式)
        columns = ("name", "progress", "deadline", "worker")
        self.task_tree = ttk.Treeview(self.left_frame, columns=columns, show="headings", height=20)
        self.task_tree.heading("name", text="タスク名")
        self.task_tree.heading("progress", text="進捗")
        self.task_tree.heading("deadline", text="期限")
        self.task_tree.heading("worker", text="担当")
        self.task_tree.column("name", width=140, anchor="w")
        self.task_tree.column("progress", width=50, anchor="center")
        self.task_tree.column("deadline", width=80, anchor="center")
        self.task_tree.column("worker", width=70, anchor="w")

        scrollbar = ttk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscroll=scrollbar.set)
        
        # Treeviewを配置する前にキャンセルボタン用のスペースを確保
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(10, 0))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(10, 0))

        self.task_tree.bind("<<TreeviewSelect>>", self.on_select_task)
        self.task_tree.bind("<ButtonPress-1>", self.on_tree_drag_start)
        self.task_tree.bind("<ButtonRelease-1>", self.on_tree_drag_stop)
        
        self.refresh_listbox()

        # --- 右側: 詳細エリア ---
        self.right_frame = tk.Frame(self.main_paned, padx=20, pady=20, bg="#fdfdfd")
        self.main_paned.add(self.right_frame)

        task_header_frame = tk.Frame(self.right_frame, bg="#fdfdfd")
        task_header_frame.pack(fill="x", anchor="w")
        self.info_label = tk.Label(task_header_frame, text="タスクを選択", bg="#fdfdfd", font=("Arial", 16, "bold"))
        self.info_label.pack(side=tk.LEFT)
        self.task_total_time_label = tk.Label(task_header_frame, text="", bg="#fdfdfd", font=("Arial", 11, "bold"), fg="#0056b3")
        self.task_total_time_label.pack(side=tk.LEFT, padx=10)

        self.sub_info_label = tk.Label(self.right_frame, text="", bg="#fdfdfd", font=("Arial", 10), fg="#666")
        self.sub_info_label.pack(anchor="w", pady=5)

        btn_f = tk.Frame(self.right_frame, bg="#fdfdfd")
        btn_f.pack(anchor="w")
        self.edit_btn = tk.Button(btn_f, text="情報を編集", state="disabled", command=self.enter_edit_mode)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        self.delete_btn = tk.Button(btn_f, text="削除", state="disabled", fg="red", command=self.delete_task)
        self.delete_btn.pack(side=tk.LEFT, padx=2)

        self.prog_input_frame = tk.LabelFrame(self.right_frame, text="進捗率", bg="#fdfdfd", padx=10)
        self.prog_input_frame.pack(fill="x", pady=10)
        self.prog_var = tk.IntVar()
        self.prog_slider = tk.Scale(self.prog_input_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.prog_var, bg="#fdfdfd")
        self.prog_slider.pack(side=tk.LEFT, fill="x", expand=True)
        tk.Button(self.prog_input_frame, text="更新", command=self.save_manual_progress).pack(side=tk.LEFT, padx=5)

        self.timer_label = tk.Label(self.right_frame, text="00:00:00", font=("Courier", 50, "bold"), bg="#fdfdfd", fg="#28a745")
        self.timer_label.pack(pady=10)

        self.btn_frame = tk.Frame(self.right_frame, bg="#fdfdfd")
        self.btn_frame.pack()
        self.start_btn = tk.Button(self.btn_frame, text="計測開始", width=12, height=2, command=self.start_timer, state="disabled")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = tk.Button(self.btn_frame, text="計測停止", width=12, height=2, command=self.stop_timer, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        tk.Label(self.right_frame, text="作業メモ:", bg="#fdfdfd", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10,0))
        self.memo_text = tk.Text(self.right_frame, height=10, font=("Arial", 10))
        self.memo_text.pack(fill="both", expand=True, pady=5)
        tk.Button(self.right_frame, text="メモを保存", command=self.save_memo).pack(anchor="e")

    # --- 編集モード管理 (修正箇所) ---
    def enter_edit_mode(self):
        if self.selected_task_index is None: return
        self.is_edit_mode = True
        task = self.data["tasks"][self.selected_task_index]
        
        # 入力欄に現在の値をセット
        self.clear_entry_fields()
        self.entries["name"].insert(0, task.get("name", ""))
        self.entries["worker"].insert(0, task.get("worker", ""))
        self.entries["estimate"].insert(0, task.get("estimate", "0"))
        
        # ボタン状態の変更
        self.input_title_label.config(text="【編集モード】", fg="blue")
        self.action_btn.config(text="変更を更新する", bg="#cce5ff")
        
        # キャンセルボタンを表示（action_btnの直後に挿入）
        self.cancel_btn.pack(fill="x", after=self.action_btn, pady=(0, 5))

    def exit_edit_mode(self):
        self.is_edit_mode = False
        self.clear_entry_fields()
        self.input_title_label.config(text="タスク登録・編集", fg="black")
        self.action_btn.config(text="タスクを追加", bg="#e1e1e1")
        # キャンセルボタンを隠す
        self.cancel_btn.pack_forget()

    # --- 基本機能 ---
    def handle_action(self):
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "タスク名は必須です")
            return
            
        s_d = f"{self.s_year_cb.get()}/{self.s_month_cb.get()}/{self.s_day_cb.get()}"
        e_d = f"{self.e_year_cb.get()}/{self.e_month_cb.get()}/{self.e_day_cb.get()}"
        
        task_data = {
            "name": name, 
            "worker": self.entries["worker"].get() or "-", 
            "estimate": self.entries["estimate"].get() or "0", 
            "start_date": s_d, 
            "end_date": e_d
        }

        if self.is_edit_mode:
            self.data["tasks"][self.selected_task_index].update(task_data)
            self.exit_edit_mode()
        else:
            task_data.update({"actual_sec": 0, "progress": 0, "memo": ""})
            self.data["tasks"].append(task_data)
            
        self.save_data()
        self.refresh_listbox()
        self.clear_entry_fields()

    def refresh_listbox(self):
        for item in self.task_tree.get_children(): self.task_tree.delete(item)
        for t in self.data["tasks"]:
            deadline_short = t.get('end_date', '')[2:]
            self.task_tree.insert("", tk.END, values=(
                t.get("name", ""), f"{t.get('progress', 0)}%", deadline_short, t.get("worker", "-")
            ))

    def on_select_task(self, event):
        if self.is_running: return # 計測中は選択変更不可
        selected_items = self.task_tree.selection()
        if selected_items:
            item = selected_items[0]
            self.selected_task_index = self.task_tree.index(item)
            task = self.data["tasks"][self.selected_task_index]
            self.info_label.config(text=task['name'])
            self.task_total_time_label.config(text=f"累計: {self.format_seconds(task.get('actual_sec', 0))}")
            self.sub_info_label.config(text=f"期間: {task.get('start_date')}〜{task.get('end_date')} | 担当: {task['worker']} | 予定: {task['estimate']}h")
            self.prog_var.set(task.get("progress", 0))
            self.memo_text.delete("1.0", tk.END); self.memo_text.insert("1.0", task.get("memo", ""))
            self.start_btn.config(state="normal"); self.edit_btn.config(state="normal"); self.delete_btn.config(state="normal")
            self.timer_label.config(text="00:00:00")

    def start_timer(self):
        self.is_running = True; self.start_time = time.time()
        self.start_btn.config(state="disabled"); self.stop_btn.config(state="normal")
        self.update_timer_loop()

    def update_timer_loop(self):
        if self.is_running:
            self.timer_label.config(text=self.format_seconds(time.time() - self.start_time))
            self.root.after(200, self.update_timer_loop)

    def stop_timer(self):
        self.is_running = False
        duration = int(time.time() - self.start_time)
        self.data["tasks"][self.selected_task_index]["actual_sec"] += duration
        self.save_data()
        self.task_total_time_label.config(text=f"累計: {self.format_seconds(self.data['tasks'][self.selected_task_index]['actual_sec'])}")
        self.stop_btn.config(state="disabled"); self.start_btn.config(state="normal")
        self.refresh_listbox()

    def save_manual_progress(self):
        if self.selected_task_index is not None:
            self.data["tasks"][self.selected_task_index]["progress"] = self.prog_var.get()
            self.save_data(); self.refresh_listbox()

    def save_memo(self):
        if self.selected_task_index is not None:
            self.data["tasks"][self.selected_task_index]["memo"] = self.memo_text.get("1.0", tk.END).strip()
            self.save_data(); messagebox.showinfo("保存", "メモを保存しました")

    def delete_task(self):
        if self.selected_task_index is not None and messagebox.askyesno("確認", "このタスクを削除しますか？"):
            self.data["tasks"].pop(self.selected_task_index)
            self.save_data(); self.refresh_listbox(); self.selected_task_index = None

    def on_tree_drag_start(self, event):
        item = self.task_tree.identify_row(event.y)
        if item: self._drag_item = item

    def on_tree_drag_stop(self, event):
        if hasattr(self, '_drag_item'):
            target = self.task_tree.identify_row(event.y)
            if target and self._drag_item != target:
                idx_f = self.task_tree.index(self._drag_item)
                idx_t = self.task_tree.index(target)
                self.data["tasks"].insert(idx_t, self.data["tasks"].pop(idx_f))
                self.save_data(); self.refresh_listbox()
            del self._drag_item

    def clear_entry_fields(self):
        for e in self.entries.values(): e.delete(0, tk.END)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return {"tasks": []}

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskTimerApp(root)
    root.mainloop()