import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import simpledialog
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

        self.setup_menu()
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
        
        # カテゴリ選択
        tk.Label(self.left_frame, text="カテゴリ", font=("Arial", 9)).pack(anchor="w")
        self.category_cb = ttk.Combobox(self.left_frame, values=self.data.get("categories", ["-"]), state="readonly")
        current_cat = self.data.get("categories", ["-"])[0] if self.data.get("categories") else "-"
        self.category_cb.set(current_cat)
        self.category_cb.pack(fill="x", pady=1)
        
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
        columns = ("name", "progress", "deadline", "worker", "category")
        self.task_tree = ttk.Treeview(self.left_frame, columns=columns, show="headings", height=20)
        self.task_tree.heading("name", text="タスク名")
        self.task_tree.heading("progress", text="進捗")
        self.task_tree.heading("deadline", text="期限")
        self.task_tree.heading("worker", text="担当")
        self.task_tree.heading("category", text="カテゴリ")
        self.task_tree.column("name", width=120, anchor="w")
        self.task_tree.column("progress", width=50, anchor="center")
        self.task_tree.column("deadline", width=70, anchor="center")
        self.task_tree.column("worker", width=70, anchor="w")
        self.task_tree.column("category", width=70, anchor="w")

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
        # カテゴリの選択を復元
        self.category_cb.set(task.get("category", self.data.get("categories", ["-"])[0]))
        
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
            "end_date": e_d,
            "category": self.category_cb.get() or "-"
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
                t.get("name", ""), f"{t.get('progress', 0)}%", deadline_short, t.get("worker", "-"), t.get("category", "-")
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
            self.sub_info_label.config(text=f"期間: {task.get('start_date')}〜{task.get('end_date')} | 担当: {task['worker']} | 予定: {task['estimate']}h | カテゴリ: {task.get('category', '-')}")
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
        # 初期データにはカテゴリ配列を持たせる
        return {"tasks": [], "categories": ["-"]}

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    # --- メニュとカテゴリ管理 ---
    def setup_menu(self):
        menubar = tk.Menu(self.root)
        menu = tk.Menu(menubar, tearoff=0)
        menu.add_command(label="カテゴリ", command=self.open_category_manager)
        menu.add_command(label="グラフ", command=self.open_category_graph)
        menubar.add_cascade(label="メニュー", menu=menu)
        self.root.config(menu=menubar)

    def open_category_manager(self):
        win = tk.Toplevel(self.root)
        win.title("カテゴリ管理")
        win.geometry("300x300")

        lb_frame = tk.Frame(win)
        lb_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.cat_listbox = tk.Listbox(lb_frame)
        self.cat_listbox.pack(side=tk.LEFT, fill="both", expand=True)
        sb = tk.Scrollbar(lb_frame, orient=tk.VERTICAL, command=self.cat_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cat_listbox.config(yscrollcommand=sb.set)

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="追加", command=self.add_category).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="削除", command=self.delete_selected_category).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="閉じる", command=win.destroy).pack(side=tk.RIGHT, padx=5)

        self.refresh_category_listbox()

    def refresh_category_listbox(self):
        if not hasattr(self, 'cat_listbox'):
            return
        self.cat_listbox.delete(0, tk.END)
        for c in self.data.get('categories', []):
            self.cat_listbox.insert(tk.END, c)

    def add_category(self):
        new = simpledialog.askstring("カテゴリ追加", "カテゴリ名を入力してください:", parent=self.root)
        if not new: return
        new = new.strip()
        if not new: return
        if new in self.data.get('categories', []):
            messagebox.showinfo("情報", "既に同名のカテゴリが存在します")
            return
        self.data.setdefault('categories', []).append(new)
        self.save_data()
        self.refresh_category_listbox()
        self.refresh_category_comboboxes()

    def delete_selected_category(self):
        sel = None
        try:
            sel = self.cat_listbox.get(self.cat_listbox.curselection())
        except Exception:
            messagebox.showwarning("警告", "削除するカテゴリを選択してください")
            return
        if sel == "-":
            messagebox.showwarning("警告", """'-' は削除できません""")
            return
        if not messagebox.askyesno("確認", f"カテゴリ '{sel}' を削除しますか？\n削除するとこのカテゴリを参照しているタスクのカテゴリは '-' に変更されます"):
            return
        # タスクのカテゴリ参照をリセット
        for t in self.data.get('tasks', []):
            if t.get('category') == sel:
                t['category'] = '-'
        self.data['categories'].remove(sel)
        self.save_data()
        self.refresh_category_listbox()
        self.refresh_category_comboboxes()
        self.refresh_listbox()

    def refresh_category_comboboxes(self):
        vals = self.data.get('categories', ['-'])
        try:
            self.category_cb.config(values=vals)
            # 既定値が存在しなければ '-' を選択
            if self.category_cb.get() not in vals:
                self.category_cb.set(vals[0] if vals else '-')
        except Exception:
            pass

    def open_category_graph(self):
        """タスク別の累計作業時間を、同名タスクの合計で比較する棒グラフとして表示します。
        各タスクのバーはカテゴリごとの内訳で色分け（積み上げ）して表示されます。
        日本語を表示できるフォントがあれば自動で設定を試みます。
        """
        try:
            import matplotlib
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib.font_manager as fm
            import numpy as np
        except Exception:
            messagebox.showerror("依存パッケージ不足", "グラフ表示には matplotlib と numpy が必要です。\n\npip install matplotlib numpy でインストールしてください。")
            return

        # --- 日本語フォントの自動検出（Windows の代表的なフォントを探す）
        try:
            candidates = ['Meiryo', 'Yu Gothic', 'MS Gothic', 'Noto Sans CJK JP', 'IPAPGothic', 'TakaoPGothic']
            jp_font = None
            for fpath in fm.findSystemFonts():
                name = fpath.lower()
                for c in candidates:
                    if c.lower() in name:
                        jp_font = fpath
                        break
                if jp_font:
                    break
            if jp_font:
                prop = fm.FontProperties(fname=jp_font)
                try:
                    font_name = prop.get_name()
                    matplotlib.rcParams['font.family'] = 'sans-serif'
                    matplotlib.rcParams['font.sans-serif'] = [font_name] + matplotlib.rcParams.get('font.sans-serif', [])
                except Exception:
                    pass
        except Exception:
            pass

        # 集計: タスク名ごと -> カテゴリごとの秒数合計
        task_map = {}
        categories = list(self.data.get('categories', ['-']))
        for t in self.data.get('tasks', []):
            name = t.get('name', '-')
            cat = t.get('category', '-')
            try:
                secs = int(t.get('actual_sec', 0))
            except Exception:
                secs = 0
            task_map.setdefault(name, {})
            task_map[name].setdefault(cat, 0)
            task_map[name][cat] += secs

        # ソート（合計降順）
        items = sorted([(name, d) for name, d in task_map.items()], key=lambda x: sum(x[1].values()), reverse=True)
        labels = [i[0] for i in items]
        if not labels:
            messagebox.showinfo("情報", "表示するタスクデータがありません。")
            return

        # 色割り当て
        cmap = plt.get_cmap('tab20')
        cat_colors = {c: cmap(i % cmap.N) for i, c in enumerate(categories)}

        # 各カテゴリごとの値配列を作成（単位: 時間）
        data_matrix = []
        for c in categories:
            row = []
            for _, d in items:
                row.append(d.get(c, 0) / 3600.0)
            data_matrix.append(row)
        data_matrix = np.array(data_matrix)

        x = np.arange(len(labels))
        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.6), 5))

        bottom = np.zeros(len(labels))
        bars = []
        for i, c in enumerate(categories):
            vals = data_matrix[i]
            b = ax.bar(x, vals, bottom=bottom, color=cat_colors.get(c), label=c)
            bars.append(b)
            bottom += vals

        # バー上に合計を表示
        for xi, total in enumerate(bottom):
            if total > 0:
                ax.text(xi, total, f"{total:.2f}h", ha='center', va='bottom', fontsize=9)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_ylabel('作業時間（時間）')
        ax.set_title('タスク別 作業時間（カテゴリ内訳）')

        # 凡例（カテゴリ）
        ax.legend(title='カテゴリ', bbox_to_anchor=(1.02, 1), loc='upper left')

        fig.tight_layout()

        # 表示ウィンドウ
        win = tk.Toplevel(self.root)
        win.title("タスク別グラフ（カテゴリ内訳）")
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill='x', pady=5)
        def save_png():
            import tkinter.filedialog as fd
            path = fd.asksaveasfilename(defaultextension='.png', filetypes=[('PNG', '*.png')])
            if path:
                fig.savefig(path)
                messagebox.showinfo("保存", f"グラフを保存しました: {path}")

        tk.Button(btn_frame, text="画像として保存", command=save_png).pack(side=tk.RIGHT, padx=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskTimerApp(root)
    root.mainloop()