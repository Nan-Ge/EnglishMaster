# -*- coding:utf-8 -*-
import datetime
import os
import json
import re
import pandas as pd
from random import choice
import math
import base64

import tkinter as tk
from tkinter import ttk, messagebox, IntVar, Checkbutton, Text

import reportlab
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, BaseDocTemplate,PageTemplate, Frame
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.lib.pagesizes import A4
pdfmetrics.registerFont(reportlab.pdfbase.ttfonts.TTFont('SimSun', "simsun.ttc"))


def check_string(re_exp, str_to_check):
    res = re.search(re_exp, str_to_check)
    if res:
        return True
    else:
        return False


def split_list(raw_list, row_num):
    new_list = [[] for i in range(row_num)]

    idx = 0
    insert_ptr = 0
    while idx < len(raw_list):
        new_list[insert_ptr].append(raw_list[idx])
        insert_ptr += 1
        idx += 1
        if insert_ptr == row_num:
            insert_ptr = 0

    return new_list


class WordDict:
    def __init__(self):
        # 单词库
        self.wd_data_path = os.path.join(os.getcwd(), "app_data", "word_dict.json")
        if os.path.exists(self.wd_data_path):
            try:
                with open(file=self.wd_data_path, mode='r') as f:
                    self.word_dict = json.load(f)
            except json.decoder.JSONDecodeError:
                print("JSON file is empty")
                self.word_dict = dict()
        else:
            self.word_dict = dict()
            with open(file=self.wd_data_path, mode='w') as f:
                f.write(json.dumps(self.word_dict, sort_keys=True, indent=4, separators=(',', ':')))

        # 考试库
        self.ex_data_path = os.path.join(os.getcwd(), "app_data", "exam_json.json")
        if os.path.exists(self.ex_data_path):
            try:
                with open(file=self.ex_data_path, mode='r') as f:
                    self.exam_list = json.load(f)
            except json.decoder.JSONDecodeError:
                print("JSON file is empty")
                self.exam_list = list()
        else:
            self.exam_list = list()
            with open(file=self.ex_data_path, mode='w') as f:
                f.write(json.dumps(self.exam_list, sort_keys=True, indent=4, separators=(',', ':')))

        # 错题表
        self.err_word_df = pd.DataFrame(columns=['word', 'error_num', 'unit'])
        for unit, v in self.word_dict.items():
            for word, wv in v['words'].items():
                self.err_word_df.loc[len(self.err_word_df.index)] = [word, wv[2], unit]

    # ------ 基本方法 -------
    def add_unit(self, unit_id, tab):
        if unit_id in self.word_dict.keys():
            return 1
        else:
            self.word_dict.update({unit_id: {
                "words": {},
                "word_num": 0,
                "error_num": 0
            }})
            self.flush_wd_to_disk()
            tab.insert('', tk.END, values=(unit_id, 0, 0))
            return 0

    def del_unit(self, unit_id, tab):
        if unit_id in self.word_dict.keys():
            self.backup_to_disk()  # 备份一次避免误删除
            self.word_dict.pop(current_unit, None)
            self.flush_wd_to_disk()
            iid = tab.selection()
            tab.delete(iid)
            return 0
        else:
            return 1

    def add_del_word(self, unit, eng, chn, tab_op, tab_pro, ops):
        if ops == "add":
            if eng in self.word_dict[unit]['words'].keys():  # 单词已存在：刷新中文含义
                self.word_dict[unit]['words'][eng][0] = chn  # (中文，已考次数，错误次数)
                self.flush_wd_to_disk()
            else:  # 单词不存在：写入
                self.word_dict[unit]['words'].update({eng: [chn, 0, 0]})  # (中文，已考次数，错误次数)
                self.refresh_wd(unit=current_unit)
                self.flush_wd_to_disk()

            tab_op.insert(0, f"[{datetime.datetime.now().strftime('%H:%M:%S')}]: {eng} = {chn}")
            tab_pro.set(current_unit_item, 'Words', self.word_dict[unit]['word_num'])
            tab_pro.set(current_unit_item, 'Errors', self.word_dict[unit]['error_num'])
            tab_pro.update()

        elif ops == "del":
            if eng in self.word_dict[unit]['words'].keys():
                self.word_dict[unit]['words'].pop(eng, None)
                self.refresh_wd(unit=current_unit)
                self.flush_wd_to_disk()

                tab_op.insert(0, f"[{datetime.datetime.now().strftime('%H:%M:%S')}]: Removing word: {eng}")
                tab_pro.set(current_unit_item, 'Words', self.word_dict[unit]['word_num'])
                tab_pro.set(current_unit_item, 'Errors', self.word_dict[unit]['error_num'])
                tab_pro.update()
                return 0
            else:
                return 1

    def mark_unmark_word(self, task_word, tab_op, tab_err, tab_word, ops):
        global mark_words_tab_idx

        if len(mark_words_tab_idx) == 0:
            return 1
        else:
            # 根据索引提取表格数据
            mark_words = []
            for m_wd_idx in mark_words_tab_idx:
                mark_words.append(tab_word.item(m_wd_idx, 'values'))

            # 实际操作
            all_units = []
            for idx, m_wd in enumerate(mark_words):
                tid = int(m_wd[0]) - 1
                eng = task_word[tid].split('-')[1]
                unit = m_wd[2]
                mark_state = m_wd[3]

                if ops == "mark":
                    if int(mark_state) == 0:
                        self.word_dict[unit]["words"][eng][2] += 1  # 修改错误次数
                        self.err_word_df.loc[(self.err_word_df['word'] == eng) & (self.err_word_df['unit'] == unit), "error_num"] += 1  # 更新错误表
                        all_units.append(unit)  # 记录需要更新的unit

                        tab_word.set(mark_words_tab_idx[idx], "Mark", "1")  # 更新前台显示
                        tab_word.update()
                elif ops == "unmark":
                    if int(mark_state) == 0:
                        self.word_dict[unit]["words"][eng][2] -= 1  # 修改错误次数
                        self.err_word_df.loc[(self.err_word_df['word'] == eng) & (self.err_word_df['unit'] == unit), "error_num"] -= 1  # 更新错误表
                        all_units.append(unit)  # 记录需要更新的unit

                        tab_word.set(mark_words_tab_idx[idx], "Mark", "0")  # 更新前台显示
                        tab_word.update()

            # 刷新所有单元的后台数据
            for unit in all_units:
                self.refresh_wd(unit=unit)
            self.flush_wd_to_disk()

            self.refresh_word_stat(tab_err=tab_err)  # 刷新错误表前台数据
            tab_op.insert(0, f"[{datetime.datetime.now().strftime('%H:%M:%S')}]: Mark errors")  # 更新前台日志

            return 0

    def get_most_error_words(self, word_num):
        return self.err_word_df.sort_values(by=['error_num']).head(word_num)

    def generate_task(self, unit_str, task_word_num, tab_exam):
        tab_exam.delete(*tab_exam.get_children())  # 清空原表格
        unit_list = []
        if unit_str == "ALL":
            unit_list = list(self.word_dict.keys())
        else:
            for un in unit_str.split(','):
                if '-' in un:
                    s = un.split('-')[0]
                    e = un.split('-')[1]
                    for i in range(s, e+1):
                        unit_list.append(str(un))
                else:
                    unit_list.append(un)

        task_word = list()
        # 全随机采样
        while len(task_word) < task_word_num:
            t_unit = choice(unit_list)  # 随机取单元
            word_eng = choice(list(self.word_dict[t_unit]['words'].keys()))  # 随机取单词
            word_chn = self.word_dict[t_unit]['words'][word_eng][0]  # 取对应中文
            w = f"{t_unit}-{word_eng}-{word_chn}"
            if w not in task_word:
                task_word.append(w)
                self.word_dict[t_unit]['words'][word_eng][1] += 1
            else:
                task_word.append("NULL")
        task_word = [x for x in task_word if x != "NULL"]

        # 刷新后台数据
        self.flush_wd_to_disk()  # 修改了[已考次数]字段，所以刷新

        # 显示表格
        for idx, tw in enumerate(task_word):
            if idx <= len(task_word) / 2:
                tab_exam.insert('', tk.END, values=(idx + 1, tw.split('-')[1], tw.split('-')[0], 0))
            else:
                tab_exam.insert('', tk.END, values=(idx + 1, tw.split('-')[2], tw.split('-')[0], 0))

        # 生成默写文件
        exam_str = ["--- CHN to ENG ---"]
        for idx, tw in enumerate(task_word):
            if idx <= len(task_word) / 2:
                exam_str.append(f"{idx + 1}. {tw.split('-')[1]}: [          ]")
        exam_str.append("--- ENG to CHN ---")
        for idx, tw in enumerate(task_word):
            if idx > len(task_word) / 2:
                exam_str.append(f"{idx + 1}. {tw.split('-')[2]}: [          ]")

        doc = SimpleDocTemplate(os.path.join(os.getcwd(), "exam", f"exam_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf"), pagesize=(A4[0], A4[1]), topMargin=0.1 * inch, bottomMargin=0.1 * inch, leftMargin=0.1 * inch, rightMargin=0.1 * inch)
        # style = getSampleStyleSheet()['Normal']  # 指定模板
        story = []  # 初始化内容
        t_data = split_list(exam_str, 20)
        t = Table(t_data, colWidths=3 * inch, rowHeights=0.45 * inch, style={
            ("FONT", (0, 0), (-1, -1), "SimSun", 10),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ('ALIGN', (1, 0), (1, -1), 'LEFT')
        }, hAlign="LEFT")
        story.append(t)  # 将表格添加到内容中
        doc.build(story)  # 将内容输出到PDF中

        # 生成答案文件
        ans_str = ["--- CHN to ENG ---"]
        for idx, tw in enumerate(task_word):
            if idx <= len(task_word) / 2:
                ans_str.append(f"{idx + 1}. {tw.split('-')[1]}: [{tw.split('-')[2]}]")
        ans_str.append("--- ENG to CHN ---")
        for idx, tw in enumerate(task_word):
            if idx > len(task_word) / 2:
                ans_str.append(f"{idx + 1}. {tw.split('-')[2]}: [{tw.split('-')[1]}]")

        doc = SimpleDocTemplate(os.path.join(os.getcwd(), "exam", f"answer_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf"), pagesize=(A4[0], A4[1]), topMargin=0.1 * inch, bottomMargin=0.1 * inch, leftMargin=0.1 * inch, rightMargin=0.1 * inch)
        # style = getSampleStyleSheet()['Normal']  # 指定模板
        story = []  # 初始化内容
        t_data = split_list(ans_str, 20)
        t = Table(t_data, colWidths=3 * inch, rowHeights=0.45 * inch, style={
            ("FONT", (0, 0), (-1, -1), "SimSun", 10),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ('ALIGN', (1, 0), (1, -1), 'LEFT')
        }, hAlign="LEFT")
        story.append(t)  # 将表格添加到内容中
        doc.build(story)  # 将内容输出到PDF中

        # 更新exam后台数据
        self.exam_list.append({"time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "words": task_word})
        self.flush_ex_to_disk()

        return task_word

    # ----- 维护后台数据 -----
    def refresh_wd(self, unit):
        unit_word_num = len(self.word_dict[unit]['words'].keys())
        unit_error_num = 0
        for k, v in self.word_dict[unit]['words'].items():
            if v[2] > 0:
                unit_error_num += 1

        self.word_dict[unit]['word_num'] = unit_word_num
        self.word_dict[unit]['error_num'] = unit_error_num

    def refresh_word_stat(self, tab_err):
        tab_err.delete(*tab_err.get_children())  # 清空原表格
        error_words = self.get_most_error_words(20)
        for idx, row in error_words.iterrows():
            error_tab.insert('', 0, values=(row['word'], row['error_num'], row['unit']))

    def flush_wd_to_disk(self):
        with open(file=self.wd_data_path, mode='w') as f:
            f.write(json.dumps(self.word_dict, sort_keys=True, indent=4, separators=(',', ':')))

    def flush_ex_to_disk(self):
        with open(file=self.ex_data_path, mode='w') as f:
            f.write(json.dumps(self.exam_list, sort_keys=True, indent=4, separators=(',', ':')))

    def backup_to_disk(self):
        with open(file=self.wd_data_path.replace("word_dict", "word_dict_backup"), mode='w') as f:
            f.write(json.dumps(self.word_dict, sort_keys=True, indent=4, separators=(',', ':')))


blessing_word = [
    "Good, good, very good!",
    "Hang in there!",
    "Keep pushing!"
]

if __name__ == "__main__":
    # 全局数据结构
    wd = WordDict()
    current_unit = None
    current_unit_item = None
    task_words = []
    mark_words_tab_idx = []
    exam_cnt = 1

    root_win = tk.Tk()  # 调用Tk()创建主窗口

    win_width = 850
    win_height = 500

    screen_width = root_win.winfo_screenwidth()
    screen_height = root_win.winfo_screenheight()

    x = int((screen_width - win_width) / 2)
    y = int((win_height - screen_height) / 2)

    root_win.title('English Master for 1Nuo')  # 主窗口命名
    root_win.geometry(f"{win_width}x{win_height}+{x}+{y}")  # 窗口大小
    root_win.iconbitmap(os.path.join(os.getcwd(), "app_data", 'app_icon.ico'))

    local_time = datetime.datetime.now()
    exam_time = datetime.datetime(2023, 12, 24)

    text = tk.Label(root_win, text=f"{(exam_time - local_time).days} days to the final exam!", fg="#000000", font=('Times', 18, 'bold'))
    text.pack(pady=10)

    # ---------------- Frame1: 进度栏 -----------------
    frame_pro = tk.LabelFrame(root_win, text="Progress", labelanchor="n")
    frame_pro.place(relx=0.025, rely=0.1, relwidth=0.45, relheight=0.40)

    unit_tab_cols = ['Unit', "Words", "Errors"]
    unit_tab_sbar = tk.Scrollbar(frame_pro, orient="horizontal")
    unit_tab = ttk.Treeview(frame_pro, columns=unit_tab_cols, yscrollcommand=unit_tab_sbar.set, show='headings')
    for col in unit_tab_cols:
        unit_tab.heading(column=col, text=col, anchor='center')
        unit_tab.column(column=col, width=1, anchor='center')

    for key, val in wd.word_dict.items():
        unit_tab.insert('', tk.END, values=(key, val['word_num'], val['error_num']))

    unit_tab.place(relx=0.05, rely=0.25, relwidth=0.9, relheight=0.7)

    ent_unit_str = tk.StringVar()
    ent_unit = tk.Entry(frame_pro, textvariable=ent_unit_str)
    ent_unit.place(relx=0.05, rely=0.05, relwidth=0.3, relheight=0.1)

    def button_add_unit_act():
        in_str = ent_unit_str.get()
        if check_string("[0-9]+", in_str):  # 检查格式
            res = wd.add_unit(in_str, unit_tab)
            if res:
                messagebox.showinfo(title="Reminder", message=f"Unit-{in_str} has existed in the library!")
            else:
                messagebox.showinfo(title="Reminder", message=f"Add Unit-{in_str} to the library!")
        else:
            messagebox.showwarning(title="Warning", message=f"Please check the format!")
    button_add_unit = tk.Button(frame_pro, text='Add', command=button_add_unit_act)
    button_add_unit.place(relx=0.4, rely=0.05, relwidth=0.2, relheight=0.1)

    def button_del_unit_act():
        if current_unit is None:
            messagebox.showinfo(title="Reminder", message=f"Please select a unit!")
        else:
            result = messagebox.askokcancel(title="Warning", message=f"Confirm to delete Unit-{current_unit}")
            if not result:
                messagebox.showinfo(title="Warning", message=f"Unit-{current_unit} does not exist!")
            else:
                wd.del_unit(unit_id=current_unit, tab=unit_tab)
                messagebox.showinfo(title="Warning", message=f"Unit-{current_unit} has been deleted!")
    button_del_unit = tk.Button(frame_pro, text='Delete', command=button_del_unit_act)
    button_del_unit.place(relx=0.7, rely=0.05, relwidth=0.2, relheight=0.1)

    unit_tab_sbar.config(command=unit_tab.yview)
    unit_tab_sbar.pack(side='right', fill='y')

    # 选择列表元素
    def on_select_unit_tab(event):
        global current_unit
        global current_unit_item
        current_unit_item = unit_tab.selection()[0]
        current_unit = unit_tab.item(current_unit_item, 'values')[0]

    unit_tab.bind('<<TreeviewSelect>>', on_select_unit_tab)

    # --------------- Frame2：输入栏 -----------------
    frame_input = tk.LabelFrame(root_win, text="Input", labelanchor="n")
    frame_input.place(relx=0.525, rely=0.1, relwidth=0.45, relheight=0.40)

    button_check_batch_var = IntVar()
    button_check_batch = Checkbutton(frame_input, text="Batch mode", variable=button_check_batch_var, onvalue=1, offvalue=0)
    button_check_batch.toggle()
    button_check_batch.place(relx=0.65, rely=0, relwidth=0.3, relheight=0.1)

    lab_word = tk.Label(frame_input, text='ENG-CHN', borderwidth=1, relief='sunken')
    lab_word.place(relx=0.05, rely=0.1, relwidth=0.2, relheight=0.2)

    ent_eng_str = tk.StringVar()
    ent_eng = tk.Entry(frame_input, textvariable=ent_eng_str)
    ent_eng.place(relx=0.25, rely=0.1, relwidth=0.2, relheight=0.2)

    ent_chn_str = tk.StringVar()
    ent_chn = tk.Entry(frame_input, textvariable=ent_chn_str)
    ent_chn.place(relx=0.45, rely=0.1, relwidth=0.2, relheight=0.2)

    def button_add_word_act():
        # 单个输入
        if not button_check_batch_var:
            eng_str = ent_eng_str.get()
            chn_str = ent_chn_str.get()
            if len(eng_str) == 0 or len(chn_str) == 0:
                messagebox.showwarning(title="Warning", message=f"Please input the English and Chinese together!")
            elif current_unit is None:
                messagebox.showwarning(title="Warning", message=f"Please select the unit!")
            else:
                wd.add_del_word(unit=current_unit, eng=eng_str, chn=chn_str, tab_op=recent_op, tab_pro=unit_tab, ops="add")
                ent_eng.delete(0, "end")
                ent_chn.delete(0, "end")
        # 批输入
        else:
            batch_input_window = tk.Toplevel(root_win)
            batch_input_window.geometry(f"{200}x{350}+{x+win_width}+{y}")  # 窗口大小
            batch_text = Text(batch_input_window, width=50, height=20, undo=True, autoseparators=False)
            batch_text.place(relx=0.1, rely=0.1, relwidth=0.8, relheight=0.6)

            def button_confirm_act():
                if current_unit is None:
                    messagebox.showwarning(title="Warning", message=f"Please select the unit!")
                    batch_input_window.wm_attributes('-topmost', 1)  # 锁定窗口置顶
                else:
                    input_text = batch_text.get("1.0", "end")
                    if input_text == "\n":
                        messagebox.showwarning(title="Warning", message=f"Please input at least a word!")
                    else:
                        for in_item in input_text.split("\n"):
                            eng = in_item.split("=")[0]
                            chn = in_item.split("=")[1]
                            wd.add_del_word(unit=current_unit, eng=eng, chn=chn, tab_op=recent_op, tab_pro=unit_tab, ops="add")
            button_confirm = tk.Button(batch_input_window, text='Confirm', command=button_confirm_act)
            button_confirm.place(relx=0.2, rely=0.75, relwidth=0.25, relheight=0.1)

            def button_cancel_act():
                batch_input_window.destroy()
            button_cancel = tk.Button(batch_input_window, text='Cancel', command=button_cancel_act)
            button_cancel.place(relx=0.55, rely=0.75, relwidth=0.25, relheight=0.1)

    button_add_word = tk.Button(frame_input, text="Input", command=button_add_word_act)
    button_add_word.place(relx=0.65, rely=0.1, relwidth=0.15, relheight=0.2)

    def button_del_word_act():
        item_val = recent_op.get(recent_op.curselection())
        if "=" in item_val:
            eng = re.findall(r": (.+?) =", item_val)[0]
            res = wd.add_del_word(unit=current_unit, eng=eng, chn=None, tab_op=recent_op, tab_pro=unit_tab, ops="del")
            if res:
                messagebox.showwarning(title="Warning", message=f"Do not find the word, please check again!")
            else:
                pass
        else:
            messagebox.showwarning(title="Warning", message=f"Please select a right item!")
    button_del_word = tk.Button(frame_input, text="Delete", command=button_del_word_act)
    button_del_word.place(relx=0.8, rely=0.1, relwidth=0.15, relheight=0.2)

    s_bar = tk.Scrollbar(frame_input)
    recent_op = tk.Listbox(frame_input, yscrollcommand=s_bar.set)
    recent_op.place(relx=0.05, rely=0.35, relwidth=0.9, relheight=0.55)

    # --------------- Frame3：错题栏 -----------------
    frame_error = tk.LabelFrame(root_win, text="Error-prone words", labelanchor="n")
    frame_error.place(relx=0.525, rely=0.525, relwidth=0.45, relheight=0.45)

    error_tab_cols = ['Word', "Error", "Unit"]
    error_tab_sbar = tk.Scrollbar(frame_error, orient="horizontal")
    error_tab = ttk.Treeview(frame_error, columns=error_tab_cols, yscrollcommand=error_tab_sbar.set, show='headings')
    error_tab.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)
    for col in error_tab_cols:
        error_tab.heading(column=col, text=col, anchor='center')
        error_tab.column(column=col, width=1, anchor='center')

    wd.refresh_word_stat(tab_err=error_tab)

    # ------------------ Frame4：作业区 -------------------
    frame_func = tk.LabelFrame(root_win, text="Exam info", labelanchor="n")
    frame_func.place(relx=0.025, rely=0.525, relwidth=0.45, relheight=0.45)

    def on_select_word_tab(event):
        global mark_words_tab_idx
        mark_words_tab_idx = word_tab.selection()

    word_tab_cols = ['No.', 'Word', "Unit", "Mark"]
    word_tab_sbar = tk.Scrollbar(frame_func, orient="horizontal")
    word_tab = ttk.Treeview(frame_func, columns=word_tab_cols, yscrollcommand=word_tab_sbar.set, show='headings')
    for col in word_tab_cols:
        word_tab.heading(column=col, text=col, anchor='center')
        word_tab.column(column=col, width=1, anchor='center')
    word_tab.place(relx=0.05, rely=0.2, relwidth=0.9, relheight=0.75)
    word_tab.bind("<<TreeviewSelect>>", on_select_word_tab)

    ent_unit_list_str = tk.StringVar()
    ent_unit_list = tk.Entry(frame_func, textvariable=ent_unit_list_str)
    ent_unit_list.insert(0, 'ALL')
    ent_unit_list.place(relx=0.05, rely=0.05, relwidth=0.3, relheight=0.1)

    def button_generate_act():
        global task_words
        task_words = wd.generate_task(unit_str=ent_unit_list.get(), task_word_num=40, tab_exam=word_tab)
        if len(task_words) > 0:
            messagebox.showinfo(title="Reminder", message=f"The word exam and answer has been generated.")
    button_generate = tk.Button(frame_func, text="Begin", command=button_generate_act)
    button_generate.place(relx=0.4, rely=0.05, relwidth=0.15, relheight=0.1)

    def button_mark_word_act():
        res = wd.mark_unmark_word(task_word=task_words, tab_op=recent_op, tab_err=error_tab, tab_word=word_tab, ops="mark")
        if res:
            messagebox.showinfo(title="Reminder", text='Please select some words!')
    button_mark_word = tk.Button(frame_func, text="Mark", command=button_mark_word_act)
    button_mark_word.place(relx=0.60, rely=0.05, relwidth=0.15, relheight=0.1)

    def button_unmark_word_act():
        res = wd.mark_unmark_word(task_word=task_words, tab_op=recent_op, tab_err=error_tab, tab_word=word_tab, ops="unmark")
        if res:
            messagebox.showinfo(title="Reminder", text='Please select some words!')
    button_unmark_word = tk.Button(frame_func, text="Unmark", command=button_unmark_word_act)
    button_unmark_word.place(relx=0.75, rely=0.05, relwidth=0.2, relheight=0.1)

    def button_exit_act():
        messagebox.showinfo(title="Blessing", message=choice(blessing_word))
        root_win.destroy()
    button_exit = tk.Button(root_win, text="Exit", command=button_exit_act)
    button_exit.place(relx=0.925, rely=0.025, relwidth=0.05, relheight=0.05)

    # 开启主循环，让窗口处于显示状态
    root_win.mainloop()
