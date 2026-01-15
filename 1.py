# -*- coding: utf-8 -*-
import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import mock_uat


class TkLogHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text) -> None:
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)

        def append() -> None:
            self.text_widget.configure(state="normal")
            self.text_widget.insert(tk.END, message + "\n")
            self.text_widget.configure(state="disabled")
            self.text_widget.see(tk.END)

        self.text_widget.after(0, append)


class MockUatApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DPU 状态模拟工具")
        self.geometry("980x680")
        self.minsize(880, 600)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.db_executor: mock_uat.DatabaseExecutor | None = None
        self.service: mock_uat.DPUMockService | None = None

        self.env_var = tk.StringVar(value=mock_uat.ENV)
        self.phone_var = tk.StringVar()
        self.status_var = tk.StringVar(value="未连接")
        self.skip_check_var = tk.BooleanVar(value=False)
        self.action_buttons: list[ttk.Button] = []

        self._build_ui()
        self._configure_logging()
        self._configure_input_provider()
        self._set_actions_state(False)

    def _build_ui(self) -> None:
        config_frame = ttk.LabelFrame(self, text="连接设置")
        config_frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(config_frame, text="环境").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        env_values = list(mock_uat.DatabaseConfig._DATABASE_CONFIG.keys())
        env_box = ttk.Combobox(config_frame, textvariable=self.env_var, values=env_values, state="readonly", width=12)
        env_box.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(config_frame, text="手机号").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        phone_entry = ttk.Entry(config_frame, textvariable=self.phone_var, width=24)
        phone_entry.grid(row=0, column=3, sticky="w", padx=6, pady=6)

        ttk.Button(config_frame, text="注册新账号", command=self.register_account).grid(
            row=0, column=4, sticky="w", padx=6, pady=6
        )
        ttk.Button(config_frame, text="连接", command=self.connect_service).grid(
            row=0, column=5, sticky="w", padx=6, pady=6
        )
        ttk.Button(config_frame, text="断开", command=self.disconnect_service).grid(
            row=0, column=6, sticky="w", padx=6, pady=6
        )

        ttk.Checkbutton(config_frame, text="跳过注册校验", variable=self.skip_check_var).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )
        ttk.Label(config_frame, textvariable=self.status_var).grid(
            row=1, column=2, columnspan=5, sticky="w", padx=6, pady=4
        )

        actions_frame = ttk.LabelFrame(self, text="操作")
        actions_frame.pack(fill="x", padx=10, pady=8)

        actions = [
            ("1 - SPAPI授权回调", "mock_spapi_auth"),
            ("2 - link-sp-3pl关联", "mock_link_sp_3pl_shop"),
            ("3 - 核保(underwritten)", "mock_underwritten_status"),
            ("4 - 审批(approved)", "mock_approved_offer_status"),
            ("5 - 创建PSP记录", "mock_create_psp_record"),
            ("6 - PSP开始(psp_start)", "mock_psp_start_status"),
            ("7 - PSP完成(psp_completed)", "mock_psp_completed_status"),
            ("8 - 电子签(esign)", "mock_esign_status"),
            ("9 - 放款(drawdown)", "mock_drawdown_status"),
            ("10 - 还款开始(repayment_start)", "mock_repayment_start_status"),
            ("11 - 还款(repayment)", "mock_repayment_status"),
            ("12 - SP店铺绑定", "mock_multi_shop_binding"),
            ("13 - 3PL重定向", "mock_multi_shop_3pl_redirect"),
        ]

        for idx, (label, method_name) in enumerate(actions):
            row = idx // 3
            col = idx % 3
            button = ttk.Button(actions_frame, text=label, command=lambda m=method_name: self.run_action(m))
            button.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
            self.action_buttons.append(button)

        for col in range(3):
            actions_frame.columnconfigure(col, weight=1)

        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(fill="both", expand=True, padx=10, pady=8)

        self.log_text = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _configure_logging(self) -> None:
        handler = TkLogHandler(self.log_text)
        handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)

    def _configure_input_provider(self) -> None:
        def gui_input(prompt: str) -> str | None:
            return simpledialog.askstring("输入", prompt, parent=self)

        def gui_error(message: str) -> None:
            messagebox.showerror("输入错误", message, parent=self)

        mock_uat.set_input_provider(gui_input, gui_error)

    def _set_actions_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def register_account(self) -> None:
        env = self.env_var.get().strip()
        try:
            phone = mock_uat.DPUMockService.register_new_account(env=env, max_attempts=3)
        except mock_uat.UserCancelledError:
            logging.getLogger(__name__).info("已取消输入")
            return
        except Exception as exc:
            messagebox.showerror("注册失败", str(exc), parent=self)
            return
        self.phone_var.set(phone)
        if messagebox.askyesno("注册成功", f"手机号: {phone}\n是否立即连接？", parent=self):
            self.connect_service()

    def connect_service(self) -> None:
        env = self.env_var.get().strip()
        phone = self.phone_var.get().strip()
        if not phone:
            messagebox.showwarning("缺少手机号", "请输入手机号或先注册", parent=self)
            return
        if not mock_uat.validate_phone_number(phone):
            messagebox.showerror("手机号格式错误", "请输入8位或11位数字", parent=self)
            return

        self.disconnect_service()
        try:
            self.db_executor = mock_uat.DatabaseExecutor(env=env)
            self.db_executor.connect()
        except Exception as exc:
            messagebox.showerror("数据库连接失败", str(exc), parent=self)
            self.db_executor = None
            return

        if not self.skip_check_var.get():
            if not mock_uat.check_is_registered(phone, self.db_executor):
                proceed = messagebox.askyesno("未注册", "手机号未注册或无授权，是否继续？", parent=self)
                if not proceed:
                    self.disconnect_service()
                    return

        self.service = mock_uat.DPUMockService(phone, self.db_executor)
        self.status_var.set(f"已连接: {env} | {phone}")
        self._set_actions_state(True)

    def disconnect_service(self) -> None:
        if self.db_executor:
            self.db_executor.close()
        self.db_executor = None
        self.service = None
        self.status_var.set("未连接")
        self._set_actions_state(False)

    def run_action(self, method_name: str) -> None:
        if not self.service:
            messagebox.showwarning("未连接", "请先连接账号后再操作", parent=self)
            return
        try:
            getattr(self.service, method_name)()
        except mock_uat.UserCancelledError:
            logging.getLogger(__name__).info("已取消输入")
        except Exception as exc:
            logging.getLogger(__name__).error(f"{method_name} 执行失败: {exc}")

    def on_close(self) -> None:
        self.disconnect_service()
        self.destroy()


if __name__ == "__main__":
    app = MockUatApp()
    app.mainloop()
