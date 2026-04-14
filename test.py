import json
import os
import sys
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from create_desktop_file import create_desktop_file


def get_config_path():
    """Ensure the config file's directory exists and return its path."""
    config_folder = (
        os.getenv("APPDATA")
        if os.name == "nt"
        else os.path.join(os.path.expanduser("~"), ".config")
    )
    config_directory = os.path.join(config_folder, "Focus-F*cker")
    os.makedirs(config_directory, exist_ok=True)
    return config_directory


def get_config_file(config_folder):
    """Ensure the config file exists and return its path."""
    config_file = os.path.join(config_folder, "config.json")
    if not os.path.exists(config_file):
        default_config = {
            "font_color": [100, 255, 255],
            "transparency": 150,
            "reminder_text": "FocusF*cker!",
            "alarm_interval_minutes": 3,
            "alarm_video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }
        try:
            with open(config_file, "w") as f:
                json.dump(default_config, f)
        except IOError as e:
            print(f"Error writing to config file: {e}")
    return config_file


def load_config():
    """Load configuration and reminder text."""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config, config.get("reminder_text", "FocusF*cker!")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading configuration: {e}")
        return {}, "FocusF*cker!"


# Paths and Config Initialization
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = get_config_path()
CONFIG_FILE = get_config_file(CONFIG_PATH)
ICON_PATH = os.path.join(SCRIPT_PATH, "icon.png")
EXE_PATH = os.path.join(SCRIPT_PATH, "main.py")
CONFIGS, PREVIOUS_TEXT = load_config()


# ---------------------------------------------------------------------------
# Alarm Overlay — full-screen flickering "GET BACK TO WORK" popup
# ---------------------------------------------------------------------------


class AlarmOverlay(QWidget):
    """Full-screen invasive flicker overlay that demands a response."""

    FLICKER_COLORS = [
        "#FF0000",
        "#FF6600",
        "#FFFF00",
        "#FF0000",
        "#FF6600",
    ]

    def __init__(self, on_dismissed, on_ignored_too_many_times):
        super().__init__()
        self._on_dismissed = on_dismissed
        self._on_ignored = on_ignored_too_many_times

        # Window setup: always on top, full screen, frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.showFullScreen()

        # Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("⚠️  HEY! GET BACK TO WORK!  ⚠️")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color: white; font-size: 52px; font-weight: bold;"
        )
        layout.addWidget(self.title_label)

        self.sub_label = QLabel("Click the button to dismiss this alarm.")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(self.sub_label)

        self.dismiss_button = QPushButton("✅  I'M BACK ON TASK")
        self.dismiss_button.setStyleSheet(
            "QPushButton {"
            "  background-color: #00cc44; color: white; font-size: 28px;"
            "  padding: 20px 60px; border-radius: 12px; font-weight: bold;"
            "}"
            "QPushButton:hover { background-color: #00ff55; }"
        )
        self.dismiss_button.clicked.connect(self._dismiss)
        layout.addWidget(self.dismiss_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Auto-close timer: if not dismissed in 30 seconds, count as ignored
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._ignored)
        self._auto_close_timer.start(30_000)  # 30 seconds to respond

        # Flicker timer
        self._flicker_index = 0
        self._flicker_timer = QTimer(self)
        self._flicker_timer.timeout.connect(self._flicker)
        self._flicker_timer.start(250)  # flicker every 250 ms

    def _flicker(self):
        color = self.FLICKER_COLORS[self._flicker_index % len(self.FLICKER_COLORS)]
        self.setStyleSheet(f"background-color: {color};")
        self._flicker_index += 1

    def _dismiss(self):
        self._flicker_timer.stop()
        self._auto_close_timer.stop()
        self.close()
        self._on_dismissed()

    def _ignored(self):
        self._flicker_timer.stop()
        self.close()
        self._on_ignored()


# ---------------------------------------------------------------------------
# Main Reminder Widget
# ---------------------------------------------------------------------------


class TransparentReminder(QWidget):
    def __init__(self, text, desktop_app_file):
        super().__init__()

        self.font_color = CONFIGS.get("font_color", [255, 0, 0])
        self.transparency = CONFIGS.get("transparency", 150)
        self.padding = CONFIGS.get("padding", 10)
        self.alarm_interval_minutes = CONFIGS.get("alarm_interval_minutes", 3)
        self.alarm_video_url = CONFIGS.get(
            "alarm_video_url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

        # Alarm state
        self._missed_alarms = 0  # consecutive ignored alarms
        self._alarm_overlay = None

        QGuiApplication.setDesktopFileName(desktop_app_file)

        self.custom_font = self.load_custom_font()
        self.label = QLabel(text, self)
        self.label.setStyleSheet(
            f"color: rgba({self.font_color[0]}, {self.font_color[1]}, {self.font_color[2]}, {self.transparency}); "
            f"background: transparent; padding: {self.padding}px;"
        )
        self.label.setFont(self.custom_font)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )

        self.position_text(text)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.adjustSize()
        self.moving_label_to_center()

        # Tray icon
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_PATH), self)
        self.tray_menu = TrayMenuCustom(
            self.tray_icon,
            self.update_text,
            self.quit_app,
            self.open_config_window,
        )

        # Alarm interval timer
        self._alarm_timer = QTimer(self)
        self._alarm_timer.timeout.connect(self._trigger_alarm)
        self._restart_alarm_timer()

    # ------------------------------------------------------------------
    # Alarm logic
    # ------------------------------------------------------------------

    def _restart_alarm_timer(self):
        interval_ms = self.alarm_interval_minutes * 60 * 1000
        self._alarm_timer.start(interval_ms)

    def _trigger_alarm(self):
        """Show the invasive full-screen alarm overlay."""
        if self._alarm_overlay is not None:
            # Already showing — treat as ignored
            self._handle_ignored()
            return

        self._alarm_overlay = AlarmOverlay(
            on_dismissed=self._handle_dismissed,
            on_ignored_too_many_times=self._handle_ignored,
        )

    def _handle_dismissed(self):
        """User clicked 'I'm back on task'."""
        self._alarm_overlay = None
        self._missed_alarms = 0  # reset streak
        self._restart_alarm_timer()

    def _handle_ignored(self):
        """Alarm timed out without response."""
        self._alarm_overlay = None
        self._missed_alarms += 1
        if self._missed_alarms >= 3:
            self._open_punishment_video()
            self._missed_alarms = 0
        self._restart_alarm_timer()

    def _open_punishment_video(self):
        webbrowser.open(self.alarm_video_url)

    # ------------------------------------------------------------------
    # Existing helpers (unchanged)
    # ------------------------------------------------------------------

    def show_window(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()

    def update_text(self):
        new_text, ok = QInputDialog.getText(self, "Update Reminder", "Enter new text:")
        if ok and new_text.strip():
            self.position_text(new_text)
            self.save_text(new_text)

    def save_text(self, new_text):
        try:
            config, _ = load_config()
            config["reminder_text"] = new_text
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
        except IOError as e:
            print(f"Error saving reminder text: {e}")

    def moving_label_to_center(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def position_text(self, new_text):
        self.label.setText(new_text.strip())
        self.label.adjustSize()
        self.adjustSize()
        self.moving_label_to_center()

    def load_custom_font(self):
        font_path = os.path.join(SCRIPT_PATH, "fonts", "KOMIKAX_.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print("Custom font not found, using default font.")
            return QFont("Arial", 24)
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        return QFont(font_family, 24)

    def open_config_window(self):
        self.config_window = ConfigWindow(
            self.font_color,
            self.transparency,
            self.alarm_interval_minutes,
            self.alarm_video_url,
            self.apply_config_changes,
        )
        self.config_window.show()

    def apply_config_changes(
        self, font_color, transparency, alarm_interval, alarm_video_url
    ):
        self.font_color = font_color
        self.transparency = transparency
        self.alarm_interval_minutes = alarm_interval
        self.alarm_video_url = alarm_video_url
        self.label.setStyleSheet(
            f"color: rgba({self.font_color[0]}, {self.font_color[1]}, {self.font_color[2]}, {self.transparency}); "
            f"background: transparent; padding: {self.padding}px;"
        )
        self._restart_alarm_timer()
        self.save_config()

    def quit_app(self):
        self._alarm_timer.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def save_config(self):
        config = {
            "font_color": self.font_color,
            "transparency": self.transparency,
            "padding": self.padding,
            "alarm_interval_minutes": self.alarm_interval_minutes,
            "alarm_video_url": self.alarm_video_url,
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
        except IOError as e:
            print(f"Error saving configuration: {e}")


# ---------------------------------------------------------------------------
# Tray Menu (unchanged interface)
# ---------------------------------------------------------------------------


class TrayMenuCustom:
    def __init__(self, tray_icon, update_text, quit_app, open_config_window):
        self.tray_icon = tray_icon
        self.tray_menu = QMenu()

        self.update_text_action = QAction("Update Text")
        self.quit_action = QAction("Quit")
        self.configurations_action = QAction("Configurations")

        self.update_text_action.triggered.connect(update_text)
        self.quit_action.triggered.connect(quit_app)
        self.configurations_action.triggered.connect(open_config_window)

        self.tray_menu.addAction(self.update_text_action)
        self.tray_menu.addAction(self.configurations_action)
        self.tray_menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.show_window)
        self.tray_icon.show()

    def show_window(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.tray_icon.show()


# ---------------------------------------------------------------------------
# Config Window — extended with alarm settings
# ---------------------------------------------------------------------------


class ConfigWindow(QDialog):
    def __init__(
        self,
        current_font_color,
        current_transparency,
        current_alarm_interval,
        current_alarm_video_url,
        apply_changes_callback,
    ):
        super().__init__()
        self.setWindowTitle("Configuration")
        self.apply_changes_callback = apply_changes_callback
        self.font_color = current_font_color
        self.transparency = current_transparency

        layout = QVBoxLayout()

        # --- Font color ---
        self.color_button = QPushButton("Choose Font Color", self)
        self.color_button.clicked.connect(self.choose_color)
        layout.addWidget(self.color_button)

        # --- Transparency ---
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.transparency_slider.setRange(0, 255)
        self.transparency_slider.setValue(self.transparency)
        self.transparency_slider.setTickInterval(10)
        self.transparency_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.transparency_label = QLabel(f"Transparency: {self.transparency}", self)
        self.transparency_slider.valueChanged.connect(self.update_transparency_label)
        layout.addWidget(self.transparency_label)
        layout.addWidget(self.transparency_slider)

        # --- Alarm interval ---
        alarm_row = QHBoxLayout()
        alarm_row.addWidget(QLabel("Focus alarm every (minutes):"))
        self.alarm_spinbox = QSpinBox(self)
        self.alarm_spinbox.setRange(1, 120)
        self.alarm_spinbox.setValue(current_alarm_interval)
        alarm_row.addWidget(self.alarm_spinbox)
        layout.addLayout(alarm_row)

        # --- Punishment video URL ---
        layout.addWidget(QLabel("Punishment video URL (opened after 3 missed alarms):"))
        self.video_url_input = QLineEdit(self)
        self.video_url_input.setText(current_alarm_video_url)
        layout.addWidget(self.video_url_input)

        # --- Buttons ---
        self.apply_button = QPushButton("Apply", self)
        self.apply_button.clicked.connect(self.apply_changes)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def update_transparency_label(self):
        self.transparency_label.setText(
            f"Transparency: {self.transparency_slider.value()}"
        )

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.font_color = color.getRgb()[:3]

    def apply_changes(self):
        transparency = self.transparency_slider.value()
        alarm_interval = self.alarm_spinbox.value()
        alarm_video_url = self.video_url_input.text().strip()
        self.apply_changes_callback(
            self.font_color, transparency, alarm_interval, alarm_video_url
        )
        self.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    desktop_app_file = create_desktop_file(ICON_PATH, EXE_PATH)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    reminder = TransparentReminder(PREVIOUS_TEXT, desktop_app_file)
    reminder.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
