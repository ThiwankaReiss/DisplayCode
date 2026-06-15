"""
display.py  —  Team Falcone Racing · EV Dashboard  (PyQt5)
Backend : http://127.0.0.1:5000/values
Run     : python3 display.py
"""

import sys, json, math, os, threading
import urllib.request as _urllib

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel,
                              QVBoxLayout, QHBoxLayout, QSizePolicy,
                              QStackedWidget)
from PyQt5.QtCore   import (Qt, QTimer, QRectF, QPointF,
                             pyqtSignal, QObject, QUrl)
from PyQt5.QtGui    import (QFont, QPainter, QColor, QPen, QBrush,
                             QPixmap, QLinearGradient, QConicalGradient)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL    = "http://127.0.0.1:5000/values"
LOG_TOGGLE_URL = "http://127.0.0.1:5000/log-toggle"
POLL_MS     = 100
WAVE_MS     = 40
MAX_SPEED   = 120.0

_HERE     = os.path.dirname(os.path.abspath(__file__))
BG_PATH   = os.path.join(_HERE, "electrone-display-app", "public", "background.jpg")
LOGO_PATH = os.path.join(_HERE, "electrone-display-app", "public", "logo.png")

# ── Palette ───────────────────────────────────────────────────────────────────
C_ACCENT = QColor(  0, 212, 255)   # team cyan-blue
C_GOLD   = QColor(255, 215,   0)
C_GREEN  = QColor(  0, 255, 120)
C_RED    = QColor(255,  48,  48)
C_WHITE  = QColor(255, 255, 255) 

def _a(c: QColor, alpha: int) -> QColor:
    """Return a copy of QColor with the given alpha."""
    r = QColor(c); r.setAlpha(alpha); return r


# ── Typography  ───────────────────────────────────────────────────────────────
# Stat-card LABEL  (e.g. "HIGH TEMP", "PACK VOLTAGE")
LABEL_SIZE  = 15                      # pt
LABEL_COLOR = "rgba(255, 255, 255, 0.9)"

# Stat-card VALUE  (the big number)
VALUE_SIZE  = 28                     # pt
# colour is per-card (C_ACCENT / C_GOLD etc.) — override below if you want one global
# e.g. set VALUE_COLOR = "#00d4ff" and pass it in StatRow
VALUE_COLOR = None                   # None = use the per-card accent colour

# Stat-card UNIT   (°C, A, V, …)
UNIT_SIZE   = 20                    # pt
UNIT_COLOR  = "rgba(255,255,255,0.9)"

# ── Battery ───────────────────────────────────────────────────────────────────
# Wall thickness of the battery outline (px). Increase for a chunkier look.
BATTERY_WALL = 5
# Height of the battery widget (px) — increase to make it taller / wider visually.
BATTERY_HEIGHT = 80
# Font size of the percentage label inside the battery (e.g. "80%")
BATTERY_LABEL_SIZE = 30
# Fill colour thresholds — edit the colours or the % breakpoints freely
#   value < BATT_LOW_PCT   → BATT_LOW_COLOR  (red)
#   value < BATT_MID_PCT   → BATT_MID_COLOR  (yellow)
#   otherwise              → BATT_HIGH_COLOR (green)
BATT_LOW_PCT   = 15
BATT_MID_PCT   = 50
BATT_LOW_COLOR  = QColor(220,  40,  40)   # red
BATT_MID_COLOR  = QColor(255, 210,   0)   # yellow
BATT_HIGH_COLOR = QColor( 30, 210,  80)   # green


# ─────────────────────────────────────────────────────────────────────────────
# Animated ECG waveform widget
# ─────────────────────────────────────────────────────────────────────────────
class WaveformWidget(QWidget):
    _RAW_PTS = [(0.157,24),(14,24),(21.843,44),(43,4),(50,24),(64,24)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0
        self.setFixedSize(54, 32)
        self.setAutoFillBackground(False)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(WAVE_MS)

    def _tick(self):
        self._phase = (self._phase + 4) % 144
        self.update()

    def _pts(self):
        sx, sy = self.width()/64., self.height()/48.
        return [QPointF(x*sx, y*sy) for x, y in self._RAW_PTS]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pts   = self._pts()
        segs  = [(math.hypot(pts[i+1].x()-pts[i].x(), pts[i+1].y()-pts[i].y()),
                  pts[i], pts[i+1]) for i in range(len(pts)-1)]
        total = sum(s[0] for s in segs)
        hw    = total * 48 / 144.

        # dim background trace
        p.setPen(QPen(_a(C_ACCENT, 35), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for _, a, b in segs:
            p.drawLine(a, b)

        # two animated highlight dashes
        for phase_start in (self._phase, (self._phase + 96) % 144):
            off    = total * phase_start / 144.
            walked = 0.
            pen    = QPen(C_ACCENT, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            for sl, a, b in segs:
                se = walked + sl
                ds = max(off, walked)
                de = min(off + hw, se)
                if de > ds:
                    t0 = (ds - walked) / sl
                    t1 = (de - walked) / sl
                    p.drawLine(
                        QPointF(a.x() + t0*(b.x()-a.x()), a.y() + t0*(b.y()-a.y())),
                        QPointF(a.x() + t1*(b.x()-a.x()), a.y() + t1*(b.y()-a.y())),
                    )
                walked = se
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Battery widget  — range-based fill, auto-contrasting label
# ─────────────────────────────────────────────────────────────────────────────
class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.setMinimumSize(150, BATTERY_HEIGHT)
        self.setFixedHeight(BATTERY_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAutoFillBackground(False)

    def setValue(self, v):
        self._value = max(0., min(100., float(v)))
        self.update()

    @staticmethod
    def _fill_color(pct):
        """Return fill QColor based on charge level thresholds."""
        if pct < BATT_LOW_PCT:
            return BATT_LOW_COLOR
        if pct < BATT_MID_PCT:
            return BATT_MID_COLOR
        return BATT_HIGH_COLOR

    @staticmethod
    def _label_color(fill: QColor) -> QColor:
        """
        Pick a label colour that contrasts strongly against the fill.
        Uses perceived luminance (ITU-R BT.601) to decide dark vs light text.
        """
        lum = (0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()) / 255.0
        # dark fill (e.g. red)  → bright white text
        # light fill (e.g. yellow/green) → near-black text for maximum contrast
        return QColor(10, 10, 10) if lum > 0.45 else QColor(255, 255, 255)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h   = self.width(), self.height()
        pw     = BATTERY_WALL          # wall thickness controlled by variable
        cap_w  = max(7, int(w * 0.04))
        bw     = w - cap_w - 4
        bh     = h - pw * 2
        bx     = pw // 2
        by     = pw

        fill_col  = self._fill_color(self._value)
        label_col = self._label_color(fill_col)

        # body outline — glow + solid wall
        for stroke, al in ((pw * 2 + 4, 18), (pw, 200)):
            p.setPen(QPen(_a(C_ACCENT, al), stroke))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(bx + stroke/2, by + stroke/2,
                                     bw - stroke, bh - stroke), 5, 5)

        # cap
        cap_stroke = max(2, pw - 1)
        p.setPen(QPen(_a(C_WHITE, 160), cap_stroke))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(bx + bw, by + bh/3, cap_w, bh/3), 2, 2)

        # fill bar — solid colour based on charge level
        pad = pw + 1
        fw  = max(0, int((bw - pad * 2) * self._value / 100))
        if fw > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fill_col))
            p.drawRoundedRect(QRectF(bx + pad, by + pad,
                                     fw, bh - pad * 2), 3, 3)

        # percentage label — auto-contrasting colour
        p.setPen(QPen(label_col))
        p.setFont(QFont("Segoe UI", BATTERY_LABEL_SIZE, QFont.Bold))
        p.drawText(QRectF(bx, by, bw, bh), Qt.AlignCenter, f"{self._value:.0f}%")
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Glass panel — dark fill + layered neon glow border + corner brackets
# ─────────────────────────────────────────────────────────────────────────────
class GlassPanel(QWidget):
    def __init__(self, accent=None, parent=None):
        super().__init__(parent)
        self._accent = accent or C_ACCENT
        self.setAutoFillBackground(False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), 10.

        # fill
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(4, 10, 22, 205)))
        p.drawRoundedRect(0, 0, w, h, r, r)

        # layered glow border
        ac = self._accent
        for pw, al in ((12, 12), (6, 30), (2, 140)):
            p.setPen(QPen(_a(ac, al), pw))
            p.setBrush(Qt.NoBrush)
            half = pw / 2.0
            p.drawRoundedRect(QRectF(half, half, w - pw, h - pw), r, r)

        # corner bracket accents
        bl = 18
        p.setPen(QPen(_a(ac, 200), 2))
        for x0, y0, dx, dy in [
            (1, 1, bl, 0), (1, 1, 0, bl),
            (w-1, 1, -bl, 0), (w-1, 1, 0, bl),
            (1, h-1, bl, 0), (1, h-1, 0, -bl),
            (w-1, h-1, -bl, 0), (w-1, h-1, 0, -bl),
        ]:
            p.drawLine(QPointF(x0, y0), QPointF(x0+dx, y0+dy))
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Speed dial — arc gauge + large glowing number
# ─────────────────────────────────────────────────────────────────────────────
class SpeedDial(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._speed = 0.0
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setSpeed(self, v):
        self._speed = max(0., min(MAX_SPEED, float(v)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h   = self.width(), self.height()
        cx, cy = w / 2, h / 2
        margin = min(w, h) * 0.07
        radius = min(w, h) / 2 - margin
        arc_w  = max(7, int(radius * 0.07))

        arc_rect = QRectF(cx - radius, cy - radius, radius*2, radius*2)
        START    =  225 * 16   # 7 o'clock, Qt angles in 1/16°
        FULL     = -270 * 16   # clockwise full sweep

        # ── background arc (dim) ─────────────────────────────────────────
        p.setPen(QPen(_a(C_ACCENT, 22), arc_w, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(arc_rect, START, FULL)

        # ── speed fill arc (green → gold → red) ─────────────────────────
        frac = self._speed / MAX_SPEED
        if frac > 0:
            fill_span = int(-270 * frac * 16)
            # conical gradient centred at arc centre, rotated to match start
            grad = QConicalGradient(cx, cy, 225)
            grad.setColorAt(0.0,          C_GREEN)
            grad.setColorAt(270/360 * 0.5, C_GOLD)
            grad.setColorAt(270/360,       C_RED)
            grad.setColorAt(1.0,           C_RED)
            p.setPen(QPen(QBrush(grad), arc_w, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(arc_rect, START, fill_span)

        # ── tick marker at current position ─────────────────────────────
        if frac > 0:
            angle_deg = 225 - 270 * frac            # clockwise from 7 o'clock
            angle_rad = math.radians(angle_deg)
            tip_r  = radius + arc_w * 0.5
            base_r = radius - arc_w * 0.5
            tx = cx + tip_r  * math.cos(angle_rad)
            ty = cy - tip_r  * math.sin(angle_rad)
            bx2 = cx + base_r * math.cos(angle_rad)
            by2 = cy - base_r * math.sin(angle_rad)
            for pw, al in ((6, 40), (3, 180)):
                p.setPen(QPen(_a(C_WHITE, al), pw, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(bx2, by2), QPointF(tx, ty))

        # ── tick labels at 0, 40, 80, 120 ───────────────────────────────
        label_r = radius + arc_w * 3
        p.setFont(QFont("Segoe UI", 7))
        for val in (0, 40, 80, 120):
            ang = math.radians(225 - 270 * val / MAX_SPEED)
            lx  = cx + label_r * math.cos(ang)
            ly  = cy - label_r * math.sin(ang)
            p.setPen(QPen(_a(C_WHITE, 90)))
            p.drawText(QRectF(lx-14, ly-8, 28, 16), Qt.AlignCenter, str(val))

        # ── speed number ─────────────────────────────────────────────────
        spd_str  = str(int(self._speed))
        num_rect = QRectF(0, cy - radius * 0.52, w, radius * 0.9)

        # glow passes
        p.setFont(QFont("Segoe UI", 82, QFont.Black))
        for dx, dy in ((-3,-3),(3,-3),(-3,3),(3,3),(0,-5),(0,5),(-5,0),(5,0)):
            p.setPen(QPen(_a(C_GOLD, 45)))
            r2 = QRectF(num_rect.x()+dx, num_rect.y()+dy,
                        num_rect.width(), num_rect.height())
            p.drawText(r2, Qt.AlignCenter, spd_str)

        p.setPen(QPen(C_GOLD))
        p.drawText(num_rect, Qt.AlignCenter, spd_str)

        # km/h label
        p.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        p.setPen(QPen(_a(C_GOLD, 160)))
        p.drawText(QRectF(0, cy + radius * 0.38, w, 28), Qt.AlignCenter, "km / h")

        # ── subtle inner ring ────────────────────────────────────────────
        inner_r = radius * 0.78
        p.setPen(QPen(_a(C_ACCENT, 18), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Speed — plain number only (no gauge arc)
# ─────────────────────────────────────────────────────────────────────────────
class SpeedPlain(QWidget):
    """Draws only the glowing number + km/h label, no arc."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._speed = 0.0
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setSpeed(self, v):
        self._speed = max(0., min(MAX_SPEED, float(v)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        spd_str  = str(int(self._speed))
        num_rect = QRectF(0, cy - h * 0.28, w, h * 0.5)

        # glow passes
        p.setFont(QFont("Segoe UI", 110, QFont.Black))
        for dx, dy in ((-4,-4),(4,-4),(-4,4),(4,4),(0,-6),(0,6),(-6,0),(6,0)):
            p.setPen(QPen(_a(C_GOLD, 40)))
            p.drawText(QRectF(num_rect.x()+dx, num_rect.y()+dy,
                              num_rect.width(), num_rect.height()),
                       Qt.AlignCenter, spd_str)

        p.setPen(QPen(C_GOLD))
        p.drawText(num_rect, Qt.AlignCenter, spd_str)

        # km/h
        p.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        p.setPen(QPen(_a(C_GOLD, 160)))
        p.drawText(QRectF(0, cy + h * 0.22, w, 32), Qt.AlignCenter, "km / h")
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Stat row  —  label + optional waveform + value
# ─────────────────────────────────────────────────────────────────────────────
def _lbl(text, size=9, bold=True, color="#ffffff"):
    l = QLabel(text)
    l.setFont(QFont("Segoe UI", size, QFont.Bold if bold else QFont.Normal))
    l.setStyleSheet(f"color:{color}; background:transparent; border:none;")
    return l


class StatRow(QWidget):
    def __init__(self, label, unit="", color=C_ACCENT, wave=False, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 2, 0, 2)
        lo.setSpacing(1)

        # ── label row  (uses LABEL_SIZE / LABEL_COLOR) ────────────────────
        lo.addWidget(_lbl(label.upper(), size=LABEL_SIZE, color=LABEL_COLOR))

        # ── value + unit row ──────────────────────────────────────────────
        row = QHBoxLayout()
        row.setSpacing(6)
        if wave:
            self._wave = WaveformWidget()
            row.addWidget(self._wave, alignment=Qt.AlignVCenter)

        val_color = VALUE_COLOR if VALUE_COLOR is not None else color.name()
        self._val = _lbl("0", size=VALUE_SIZE, color=val_color)
        row.addWidget(self._val)

        if unit:
            row.addWidget(
                _lbl(unit, size=UNIT_SIZE, bold=False, color=UNIT_COLOR),
                alignment=Qt.AlignBottom,
            )
        row.addStretch()
        lo.addLayout(row)

    def setValue(self, v, decimals=0):
        self._val.setText(f"{v:.{decimals}f}")


# ─────────────────────────────────────────────────────────────────────────────
# Data fetcher  —  Qt-native async HTTP (no threads)
# ─────────────────────────────────────────────────────────────────────────────
class DataFetcher(QObject):
    dataReady = pyqtSignal(dict)

    def __init__(self, url, interval_ms):
        super().__init__()
        self._url      = url
        self._pending  = False
        self._manager  = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_reply)
        self._timer    = QTimer(self)
        self._timer.timeout.connect(self._fetch)
        self._interval = interval_ms

    def start(self):
        self._fetch()
        self._timer.start(self._interval)

    def _fetch(self):
        if self._pending:
            return
        self._pending = True
        self._manager.get(QNetworkRequest(QUrl(self._url)))

    def _on_reply(self, reply):
        self._pending = False
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            if isinstance(data, dict):
                self.dataReady.emit(data)
        except Exception:
            pass
        finally:
            reply.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# Main Dashboard window
# ─────────────────────────────────────────────────────────────────────────────
class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self._bg        = QPixmap(BG_PATH)   if os.path.exists(BG_PATH)   else QPixmap()
        self._logo      = QPixmap(LOGO_PATH) if os.path.exists(LOGO_PATH) else QPixmap()
        self._connected = False
        self._pulse     = 0.0

        pulse_t = QTimer(self)
        pulse_t.timeout.connect(self._pulse_tick)
        pulse_t.start(40)

        self._build_ui()

        self._fetcher = DataFetcher(BACKEND_URL, POLL_MS)
        self._fetcher.dataReady.connect(self._on_data)
        self._fetcher.start()

    # ── animated status dot ───────────────────────────────────────────────────
    def _pulse_tick(self):
        self._pulse = (self._pulse + 0.06) % (2 * math.pi)
        self.update(0, 0, self.width(), 58)   # repaint header region only

    # ── background + chrome painting ──────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # background image scaled to cover
        if not self._bg.isNull():
            sc = self._bg.scaled(w, h, Qt.KeepAspectRatioByExpanding,
                                 Qt.SmoothTransformation)
            p.drawPixmap((w - sc.width()) // 2, (h - sc.height()) // 2, sc)
        else:
            p.fillRect(0, 0, w, h, QColor(5, 10, 20))

        # dark gradient overlay (preserves background texture at low opacity)
        ov = QLinearGradient(0, 0, 0, h)
        ov.setColorAt(0.0, QColor(3,  7, 18, 215))
        ov.setColorAt(0.4, QColor(3,  7, 18, 188))
        ov.setColorAt(1.0, QColor(3,  7, 18, 225))
        p.fillRect(0, 0, w, h, ov)

        # header separator — glowing cyan line
        y_sep = 56
        for pw, al in ((8, 10), (4, 35), (1, 200)):
            gl = QLinearGradient(0, 0, w, 0)
            gl.setColorAt(0.00, _a(C_ACCENT,  0))
            gl.setColorAt(0.12, _a(C_ACCENT, al))
            gl.setColorAt(0.88, _a(C_ACCENT, al))
            gl.setColorAt(1.00, _a(C_ACCENT,  0))
            p.setPen(QPen(QBrush(gl), pw))
            p.drawLine(0, y_sep, w, y_sep)

        # status dot (pulsing)
        pulse_a  = int(80 + 80 * math.sin(self._pulse))
        dot_col  = C_ACCENT if self._connected else QColor(255, 80, 80)
        dot_x    = w - 52
        dot_y    = 28
        for dot_r, al in ((10, 15), (6, 40), (3, 180)):
            dc = QColor(dot_col); dc.setAlpha(al if self._connected else
                                               min(255, al + pulse_a // 3))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(dc))
            p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

        p.end()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("Team Falcone Racing")
        self.showFullScreen()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ───────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(16, 10, 14, 10)
        hdr.setSpacing(10)

        if not self._logo.isNull():
            logo_lbl = QLabel()
            logo_lbl.setPixmap(self._logo.scaledToHeight(34, Qt.SmoothTransformation))
            logo_lbl.setStyleSheet("background:transparent;")
            hdr.addWidget(logo_lbl)

        title = _lbl("TEAM FALCONE RACING", size=13, color="rgba(255,255,255,190)")
        title.setStyleSheet(
            "color:rgba(255,255,255,190); letter-spacing:4px; "
            "background:transparent; border:none;"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        # log-file label — shows the current CSV log filename
        self._log_file_lbl = _lbl("—", size=8, color="rgba(0,212,255,120)")
        self._log_file_lbl.setStyleSheet(
            "color:rgba(0,212,255,120); letter-spacing:0.5px; "
            "background:transparent; border:none;"
        )
        hdr.addWidget(self._log_file_lbl)

        # NEW-file button — click to start logging to the next file
        new_btn = QLabel("⊕  NEW")
        new_btn.setFixedSize(78, 34)
        new_btn.setAlignment(Qt.AlignCenter)
        new_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        new_btn.setStyleSheet(
            "QLabel { background:rgba(0,160,80,180); color:white; "
            "border-radius:6px; letter-spacing:1px; }"
        )
        new_btn.mousePressEvent = lambda _: self._new_log()
        hdr.addWidget(new_btn)

        self._status_lbl = _lbl("CONNECTING…", size=8, color="rgba(0,212,255,140)")
        hdr.addWidget(self._status_lbl)

        # spacer for the drawn dot
        dot_sp = QLabel(); dot_sp.setFixedWidth(22)
        dot_sp.setStyleSheet("background:transparent;")
        hdr.addWidget(dot_sp)

        # gauge toggle button
        self._gauge_on = True
        self._toggle_btn = QLabel("◎  GAUGE")
        self._toggle_btn.setFixedSize(88, 34)
        self._toggle_btn.setAlignment(Qt.AlignCenter)
        self._toggle_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._toggle_btn.setStyleSheet(
            "QLabel { background:rgba(0,160,200,180); color:white; "
            "border-radius:6px; letter-spacing:1px; }"
        )
        self._toggle_btn.mousePressEvent = lambda _: self._toggle_gauge()
        hdr.addWidget(self._toggle_btn)

        # log toggle button  (ON by default — green)
        self._log_on = True
        self._log_btn = QLabel("⏺  LOG")
        self._log_btn.setFixedSize(78, 34)
        self._log_btn.setAlignment(Qt.AlignCenter)
        self._log_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._log_btn.setStyleSheet(
            "QLabel { background:rgba(0,180,60,180); color:white; "
            "border-radius:6px; letter-spacing:1px; }"
        )
        self._log_btn.mousePressEvent = lambda _: self._toggle_log()
        hdr.addWidget(self._log_btn)

        # exit button
        x_btn = QLabel("✕")
        x_btn.setFixedSize(34, 34)
        x_btn.setAlignment(Qt.AlignCenter)
        x_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        x_btn.setStyleSheet("""
            QLabel { background:rgba(190,0,0,190); color:white; border-radius:6px; }
        """)
        x_btn.mousePressEvent = lambda _: QApplication.quit()
        hdr.addWidget(x_btn)

        root.addLayout(hdr)

        # ── body ─────────────────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(14, 8, 14, 14)
        body.setSpacing(12)

        body.addWidget(self._make_left_panel(),   stretch=3)
        body.addWidget(self._make_center_panel(), stretch=5)
        body.addWidget(self._make_right_panel(),  stretch=3)

        root.addLayout(body, stretch=1)

    # ── panel builders ────────────────────────────────────────────────────────
    def _make_left_panel(self) -> QWidget:
        panel = GlassPanel()
        lo    = QVBoxLayout(panel)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(8)
        self.w_high_temp  = StatRow("High Temp",        "°C", C_ACCENT)
        self.w_low_temp   = StatRow("Low Temp",         "°C", C_ACCENT)
        self.w_motor_cur  = StatRow("Motor Current",    "A",  C_ACCENT, wave=True)
        self.w_high_cell  = StatRow("High Cell Voltage", "V",  C_GREEN)
        self.w_low_cell   = StatRow("Low Cell Voltage",  "V",  C_GREEN)
        lo.addWidget(self.w_high_temp)
        lo.addWidget(self._sep())
        lo.addWidget(self.w_low_temp)
        lo.addWidget(self._sep())
        lo.addWidget(self.w_motor_cur)
        lo.addWidget(self._sep())
        lo.addWidget(self.w_high_cell)
        lo.addWidget(self._sep())
        lo.addWidget(self.w_low_cell)
        lo.addStretch()
        return panel

    def _make_center_panel(self) -> QWidget:
        panel = GlassPanel(accent=C_GOLD)
        lo    = QVBoxLayout(panel)
        lo.setContentsMargins(8, 8, 8, 8)

        self._speed_stack = QStackedWidget()
        self._speed_stack.setAutoFillBackground(False)

        self.w_speed       = SpeedDial()   # index 0 — gauge (default)
        self.w_speed_plain = SpeedPlain()  # index 1 — number only

        self._speed_stack.addWidget(self.w_speed)        # 0
        self._speed_stack.addWidget(self.w_speed_plain)  # 1
        self._speed_stack.setCurrentIndex(0)

        lo.addWidget(self._speed_stack)
        return panel

    def _toggle_gauge(self):
        self._gauge_on = not self._gauge_on
        self._speed_stack.setCurrentIndex(0 if self._gauge_on else 1)
        if self._gauge_on:
            self._toggle_btn.setText("◎  GAUGE")
            self._toggle_btn.setStyleSheet(
                "QLabel { background:rgba(0,160,200,180); color:white; "
                "border-radius:6px; letter-spacing:1px; }"
            )
        else:
            self._toggle_btn.setText("≡  NUMBER")
            self._toggle_btn.setStyleSheet(
                "QLabel { background:rgba(80,80,80,180); color:rgba(255,255,255,160); "
                "border-radius:6px; letter-spacing:1px; }"
            )

    def _toggle_log(self):
        """Toggle CAN logging on/off and notify the backend."""
        self._log_on = not self._log_on
        if self._log_on:
            self._log_btn.setText("⏺  LOG")
            self._log_btn.setStyleSheet(
                "QLabel { background:rgba(0,180,60,180); color:white; "
                "border-radius:6px; letter-spacing:1px; }"
            )
        else:
            self._log_btn.setText("⏹  LOG")
            self._log_btn.setStyleSheet(
                "QLabel { background:rgba(160,40,40,180); color:rgba(255,255,255,160); "
                "border-radius:6px; letter-spacing:1px; }"
            )

        def _post():
            try:
                _urllib.urlopen(
                    _urllib.Request(
                        LOG_TOGGLE_URL,
                        data=b"",
                        method="POST",
                    ),
                    timeout=3,
                ).read()
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

    def _make_right_panel(self) -> QWidget:
        panel = GlassPanel()
        lo    = QVBoxLayout(panel)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(8)

        lo.addWidget(_lbl("STATE OF CHARGE", size=15, color="rgba(255, 255, 255, 0.9)"))
        self.w_battery = BatteryWidget()
        lo.addWidget(self.w_battery)

        lo.addWidget(self._sep())
        self.w_pack_volt = StatRow("Pack Voltage", "V",  C_GOLD)
        lo.addWidget(self.w_pack_volt)
        lo.addWidget(self._sep())
        self.w_pack_cur = StatRow("Pack Current",  "A",  C_ACCENT, wave=True)
        self.w_delta   = StatRow("Delta",           "V",  C_GOLD)
        lo.addWidget(self.w_pack_cur)
        lo.addWidget(self._sep())
        lo.addWidget(self.w_delta)
        lo.addStretch()
        return panel

    @staticmethod
    def _sep() -> QWidget:
        d = QWidget()
        d.setFixedHeight(1)
        d.setAutoFillBackground(True)
        d.setStyleSheet("background:rgba(0,212,255,40);")
        return d

    # ── log-file helpers ──────────────────────────────────────────────────────
    def _new_log(self):
        """POST /new-log in a daemon thread (fire-and-forget).
        The updated filename arrives automatically on the next /values poll."""
        def _post():
            try:
                _urllib.urlopen(
                    _urllib.Request(
                        "http://127.0.0.1:5000/new-log",
                        data=b"",
                        method="POST",
                    ),
                    timeout=3,
                ).read()
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

    # ── data update ───────────────────────────────────────────────────────────
    def _on_data(self, d: dict):
        self._connected = True
        self._status_lbl.setText("● LIVE")
        self._status_lbl.setStyleSheet(
            "color:rgba(0,255,160,200); background:transparent; border:none; "
            "letter-spacing:2px;"
        )
        self.w_high_temp.setValue(d.get("high_temp",       0))
        self.w_low_temp.setValue( d.get("low_temp",        0))
        self.w_motor_cur.setValue(d.get("motor_current",   0))
        self.w_speed.setSpeed(      d.get("speed",           0))
        self.w_speed_plain.setSpeed( d.get("speed",           0))
        self.w_battery.setValue(  d.get("state_of_charge", 0))
        self.w_pack_volt.setValue(d.get("pack_voltage",    0), decimals=1)
        pack_cur = d.get("pack_current", 0)
        self.w_pack_cur.setValue(pack_cur, decimals=(2 if abs(pack_cur) < 1.0 else 0))
        high_cell = d.get("high_cell_voltage", 0)
        low_cell  = d.get("low_cell_voltage",  0)
        self.w_high_cell.setValue(high_cell, decimals=4)
        self.w_low_cell.setValue( low_cell,  decimals=4)
        self.w_delta.setValue(high_cell - low_cell, decimals=4)
        filename = d.get("log_filename", "")
        if filename:
            self._log_file_lbl.setText(filename)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.quit()
        else:
            super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Team Falcone Racing")
    dash = Dashboard()
    sys.exit(app.exec_())

