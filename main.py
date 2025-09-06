import sys
import subprocess
import re
import os
import tempfile
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QCheckBox,
    QScrollArea, QGroupBox, QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtCore import Qt
from PIL import Image

# 必要なオプションと説明
OPTION_DESCRIPTIONS = {
    "--onefile": "1つの実行可能ファイルを生成します。",
    "--onedir": "1つのフォルダに実行可能ファイルを生成します。",
    "--noconfirm": "既存出力ディレクトリを上書き確認なしで置き換えます。",
    "--clean": "キャッシュと一時ファイルを削除します。",
    "--strip": "不要な情報を削除してサイズを小さくします。",
    "--noconsole": "コンソールウィンドウを表示せずに実行可能ファイルを作ります。"
}

# Pythonファイルから import モジュールを解析
def parse_imports(py_file_path):
    modules = set()
    import_pattern = re.compile(r'^\s*(?:import|from)\s+([\w\.]+)')
    try:
        with open(py_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = import_pattern.match(line)
                if match:
                    modules.add(match.group(1).split('.')[0])
    except Exception as e:
        print(f"Import解析エラー: {e}")
    return sorted(modules)

# PNG/JPG を ICO に変換
def convert_to_ico(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    if ext == ".ico":
        return image_path
    temp_dir = tempfile.gettempdir()
    ico_path = os.path.join(temp_dir, "temp_icon.ico")
    try:
        img = Image.open(image_path)
        img.save(ico_path, format="ICO", sizes=[(256,256)])
        return ico_path
    except Exception as e:
        QMessageBox.critical(None, "エラー", f"アイコン変換に失敗しました: {e}")
        return None

class PyInstallerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyInstaller GUI Builder")
        self.resize(820, 650)
        self.center()

        self.option_cbs = {}
        self.module_cbs = []

        # 参照ボタンの統一スタイル
        self.browse_btn_style = "background-color:#6c63ff;color:white;border-radius:5px;padding:5px;"
        self.browse_btn_font = QFont("Segoe UI", 10)

        self.init_ui()

    def center(self):
        frame_geom = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry().center()
        frame_geom.moveCenter(screen)
        self.move(frame_geom.topLeft())

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Python ファイル選択
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setFont(QFont("Segoe UI", 10))
        browse_btn = QPushButton("参照")
        browse_btn.setFont(self.browse_btn_font)
        browse_btn.setStyleSheet(self.browse_btn_style)
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(QLabel("Pythonスクリプト:"))
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # 基本オプション
        options_group = QGroupBox("基本オプション")
        options_layout = QVBoxLayout()
        for opt, desc in OPTION_DESCRIPTIONS.items():
            cb = QCheckBox(f"{opt} - {desc}")
            cb.setFont(QFont("Segoe UI", 10))
            options_layout.addWidget(cb)
            self.option_cbs[opt] = cb
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 値付きオプション: --name, --icon, --add-data, --distpath
        special_group = QGroupBox("値指定オプション")
        special_layout = QVBoxLayout()

        # --name
        name_layout = QHBoxLayout()
        self.name_cb = QCheckBox("--name")
        self.name_cb.setFont(QFont("Segoe UI", 10))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("EXE の名前")
        name_layout.addWidget(self.name_cb)
        name_layout.addWidget(self.name_input)
        special_layout.addLayout(name_layout)

        # --icon
        icon_layout = QHBoxLayout()
        self.icon_cb = QCheckBox("--icon")
        self.icon_cb.setFont(QFont("Segoe UI", 10))
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("アイコンファイル (png/jpg/ico)")
        icon_btn = QPushButton("参照")
        icon_btn.setFont(self.browse_btn_font)
        icon_btn.setStyleSheet(self.browse_btn_style)
        icon_btn.clicked.connect(lambda: self.browse_icon())
        icon_layout.addWidget(self.icon_cb)
        icon_layout.addWidget(self.icon_input)
        icon_layout.addWidget(icon_btn)
        special_layout.addLayout(icon_layout)

        # --add-data
        adddata_layout = QHBoxLayout()
        self.adddata_cb = QCheckBox("--add-data")
        self.adddata_cb.setFont(QFont("Segoe UI", 10))
        self.adddata_input = QLineEdit()
        self.adddata_input.setPlaceholderText("data.txt;data フォルダ名")
        adddata_layout.addWidget(self.adddata_cb)
        adddata_layout.addWidget(self.adddata_input)
        special_layout.addLayout(adddata_layout)

        # --distpath
        dist_layout = QHBoxLayout()
        self.dist_cb = QCheckBox("--distpath")
        self.dist_cb.setFont(QFont("Segoe UI", 10))
        self.dist_input = QLineEdit()
        self.dist_input.setPlaceholderText("出力先フォルダ")
        dist_btn = QPushButton("参照")
        dist_btn.setFont(self.browse_btn_font)
        dist_btn.setStyleSheet(self.browse_btn_style)
        dist_btn.clicked.connect(lambda: self.browse_dist())
        dist_layout.addWidget(self.dist_cb)
        dist_layout.addWidget(self.dist_input)
        dist_layout.addWidget(dist_btn)
        special_layout.addLayout(dist_layout)

        special_group.setLayout(special_layout)
        layout.addWidget(special_group)

        # hidden-import
        self.module_label = QLabel("hidden-import （自動検出されない場合は対象のモジュールにチェック）:")
        self.module_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.module_label)

        self.module_scroll = QScrollArea()
        self.module_scroll.setWidgetResizable(True)
        self.module_container = QWidget()
        self.module_layout = QVBoxLayout()
        self.module_container.setLayout(self.module_layout)
        self.module_scroll.setWidget(self.module_container)
        self.module_scroll.setFixedHeight(10*25)
        layout.addWidget(self.module_scroll)

        # EXE化ボタン
        build_btn = QPushButton("EXE化")
        build_btn.setFont(QFont("Segoe UI", 11))
        build_btn.setStyleSheet("background-color:#008840;color:white;border-radius:6px;padding:8px;")
        build_btn.clicked.connect(self.build_exe_threaded)
        layout.addWidget(build_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    # ファイル・フォルダ参照
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pythonファイルを選択", "", "Python Files (*.py)")
        if path:
            self.file_input.setText(path)
            modules = parse_imports(path)
            self.load_module_checkboxes(modules)

    def browse_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, "アイコンファイルを選択", "", "Image Files (*.ico *.png *.jpg *.jpeg)")
        if path:
            self.icon_input.setText(path)

    def browse_dist(self):
        path = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択")
        if path:
            self.dist_input.setText(path)

    # hidden-import チェックボックス作成
    def load_module_checkboxes(self, modules):
        for cb in self.module_cbs:
            self.module_layout.removeWidget(cb)
            cb.setParent(None)
        self.module_cbs = []

        for m in modules:
            cb = QCheckBox(m)
            cb.setFont(QFont("Segoe UI", 10))
            self.module_layout.addWidget(cb)
            self.module_cbs.append(cb)

    # 別スレッドで build_exe
    def build_exe_threaded(self):
        threading.Thread(target=self.build_exe, daemon=True).start()

    # EXE化
    def build_exe(self):
        script = self.file_input.text()
        if not script:
            QMessageBox.warning(self, "警告", "Pythonスクリプトを選択してください")
            return

        cmd = ["pyinstaller", script]

        # 基本オプション
        for opt, cb in self.option_cbs.items():
            if cb.isChecked():
                cmd.append(opt)

        # 値付きオプション
        if self.name_cb.isChecked() and self.name_input.text():
            cmd.extend(["--name", self.name_input.text()])

        if self.icon_cb.isChecked() and self.icon_input.text():
            icon_path = convert_to_ico(self.icon_input.text())
            if icon_path:
                cmd.extend(["--icon", icon_path])

        if self.adddata_cb.isChecked() and self.adddata_input.text():
            cmd.extend(["--add-data", self.adddata_input.text()])

        if self.dist_cb.isChecked() and self.dist_input.text():
            cmd.extend(["--distpath", self.dist_input.text()])

        # hidden-import
        for cb in self.module_cbs:
            if cb.isChecked():
                cmd.append(f"--hidden-import={cb.text()}")

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                print(line, end="")
            process.wait()
            QMessageBox.information(self, "完了", "exe化が完了しました！")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"exe化に失敗しました: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f0f0"))
    app.setPalette(palette)
    window = PyInstallerGUI()
    window.show()
    sys.exit(app.exec())
