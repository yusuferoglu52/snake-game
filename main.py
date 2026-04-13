"""
Snake — tkinter + standart kütüphane.
Menü, duraklatma, rekor dosyası, skora bağlı hız (seviye).
"""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

CELL = 22
COLS = 24
ROWS = 24
CANVAS_W = COLS * CELL
CANVAS_H = ROWS * CELL

TICK_MS_START = 118
TICK_MS_MIN = 48
SPEED_STEP_SCORE = 5
SPEED_DELTA_MS = 10

BG = "#0c0e14"
BG_CELL_A = "#12151f"
BG_CELL_B = "#0e1118"
GRID_LINE = "#1a2030"
FRAME_OUTER = "#1e2538"
ACCENT = "#818cf8"
ACCENT_SOFT = "#a5b4fc"
SNAKE_HEAD = "#5eead4"
SNAKE_HEAD_EDGE = "#2dd4bf"
SNAKE_BODY = "#3d9f8f"
SNAKE_BODY_ALT = "#348a7c"
SNAKE_SHADOW = "#050608"
FOOD = "#f43f5e"
FOOD_DEEP = "#be123c"
FOOD_SHINE = "#fda4af"
FOOD_BONUS = "#fbbf24"
FOOD_BONUS_RING = "#f59e0b"
TEXT = "#f1f5f9"
MUTED = "#94a3b8"
OVERLAY_BG = "#0a0c12"
OVERLAY_STROKE = ACCENT
GOLD = "#fcd34d"

HIGHSCORE_FILE = Path(__file__).resolve().with_name("highscore.txt")
BONUS_FOOD_CHANCE = 0.12
BONUS_POINTS = 2


def _opposite(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] == -b[0] and a[1] == -b[1]


class SnakeApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Snake")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self._subtitle_font = tkfont.Font(family="Segoe UI", size=12)
        self._small_font = tkfont.Font(family="Segoe UI", size=10)

        self.state = "menu"
        self.high_score = self._load_high_score()
        self.score = 0
        self.direction = (1, 0)
        self.pending_dir = (1, 0)
        self.snake: list[tuple[int, int]] = []
        self.food: tuple[int, int] | None = None
        self.food_bonus = False
        self._step_after_id: str | None = None

        self._build_ui()
        self._bind_keys()
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.canvas.focus_set()
        self._refresh_canvas()

    def _build_ui(self) -> None:
        self.score_var = tk.StringVar(value="Skor: —")
        self.level_var = tk.StringVar(value="Seviye: —")
        self.record_var = tk.StringVar(value=f"Rekor: {self.high_score}")

        bar = tk.Frame(self.root, bg=BG, padx=12, pady=10)
        bar.pack(fill=tk.X)

        left = tk.Frame(bar, bg=BG)
        left.pack(side=tk.LEFT)
        tk.Label(
            left,
            textvariable=self.score_var,
            font=self._subtitle_font,
            fg=TEXT,
            bg=BG,
        ).pack(anchor=tk.W)
        tk.Label(
            left,
            textvariable=self.level_var,
            font=self._small_font,
            fg=MUTED,
            bg=BG,
        ).pack(anchor=tk.W)

        mid = tk.Frame(bar, bg=BG)
        mid.pack(side=tk.LEFT, expand=True)
        tk.Label(
            mid,
            textvariable=self.record_var,
            font=self._subtitle_font,
            fg=GOLD,
            bg=BG,
        ).pack()

        hints = (
            "Space: başlat · P/Esc: duraklat · R: sıfırla · M: menü · Ok tuşları"
        )
        tk.Label(
            bar,
            text=hints,
            font=self._small_font,
            fg=MUTED,
            bg=BG,
            wraplength=CANVAS_W - 40,
            justify=tk.RIGHT,
        ).pack(side=tk.RIGHT)

        sep = tk.Frame(self.root, height=2, bg=FRAME_OUTER)
        sep.pack(fill=tk.X, padx=14)

        board_wrap = tk.Frame(self.root, bg=FRAME_OUTER, padx=2, pady=2)
        board_wrap.pack(padx=14, pady=(0, 14))
        self.canvas = tk.Canvas(
            board_wrap,
            width=CANVAS_W,
            height=CANVAS_H,
            highlightthickness=0,
            bg=BG,
            bd=0,
        )
        self.canvas.pack()
        self.canvas.focus_set()

        self._overlay_rect: int | None = None
        self._overlay_text_ids: list[int] = []
        self._last_was_record = False

    def _load_high_score(self) -> int:
        try:
            text = HIGHSCORE_FILE.read_text(encoding="utf-8").strip()
            return max(0, int(text))
        except (OSError, ValueError):
            return 0

    def _save_high_score(self) -> None:
        try:
            HIGHSCORE_FILE.write_text(str(self.high_score), encoding="utf-8")
        except OSError:
            pass

    def _tick_interval_ms(self) -> int:
        tier = self.score // SPEED_STEP_SCORE
        return max(TICK_MS_MIN, TICK_MS_START - tier * SPEED_DELTA_MS)

    def _level_display(self) -> int:
        return 1 + self.score // SPEED_STEP_SCORE

    def _update_hud(self) -> None:
        if self.state in ("playing", "paused"):
            self.score_var.set(f"Skor: {self.score}")
            self.level_var.set(f"Seviye: {self._level_display()} · gecikme {self._tick_interval_ms()} ms")
        elif self.state == "game_over":
            self.score_var.set(f"Skor: {self.score}")
            self.level_var.set(f"Seviye: {self._level_display()}")
        else:
            self.score_var.set("Skor: —")
            self.level_var.set("Seviye: —")
        self.record_var.set(f"Rekor: {self.high_score}")

    def _bind_keys(self) -> None:
        self.root.bind("<Left>", lambda e: self._queue_dir((-1, 0)))
        self.root.bind("<Right>", lambda e: self._queue_dir((1, 0)))
        self.root.bind("<Up>", lambda e: self._queue_dir((0, -1)))
        self.root.bind("<Down>", lambda e: self._queue_dir((0, 1)))
        self.canvas.bind("<Left>", lambda e: self._queue_dir((-1, 0)))
        self.canvas.bind("<Right>", lambda e: self._queue_dir((1, 0)))
        self.canvas.bind("<Up>", lambda e: self._queue_dir((0, -1)))
        self.canvas.bind("<Down>", lambda e: self._queue_dir((0, 1)))

        self.root.bind("<space>", lambda e: self._on_space())
        self.root.bind("<Return>", lambda e: self._on_space())
        self.root.bind("<p>", lambda e: self._toggle_pause())
        self.root.bind("<P>", lambda e: self._toggle_pause())
        self.root.bind("<Escape>", lambda e: self._toggle_pause())
        self.root.bind("<r>", lambda e: self._restart())
        self.root.bind("<R>", lambda e: self._restart())
        self.root.bind("<m>", lambda e: self._to_menu())
        self.root.bind("<M>", lambda e: self._to_menu())

    def _on_close(self) -> None:
        self._cancel_step()
        self.root.destroy()

    def _cancel_step(self) -> None:
        if self._step_after_id is not None:
            try:
                self.root.after_cancel(self._step_after_id)
            except tk.TclError:
                pass
            self._step_after_id = None

    def _schedule_next_step(self) -> None:
        self._cancel_step()
        if self.state != "playing":
            return
        delay = self._tick_interval_ms()
        self._step_after_id = self.root.after(delay, self._on_step)

    def _on_step(self) -> None:
        self._step_after_id = None
        if self.state != "playing":
            return
        self._simulate_tick()
        if self.state == "playing":
            self._schedule_next_step()

    def _on_space(self) -> None:
        if self.state == "menu":
            self._begin_round()
        elif self.state in ("game_over", "victory"):
            self._restart()

    def _toggle_pause(self) -> None:
        if self.state == "playing":
            self.state = "paused"
            self._cancel_step()
            self._show_pause_overlay()
            self._update_hud()
        elif self.state == "paused":
            self.state = "playing"
            self._clear_overlay()
            self._draw_entities()
            self._update_hud()
            self._schedule_next_step()

    def _queue_dir(self, d: tuple[int, int]) -> None:
        if self.state not in ("playing", "paused"):
            return
        if self.state == "paused":
            return
        if _opposite(d, self.direction):
            return
        self.pending_dir = d

    def _begin_round(self) -> None:
        self._cancel_step()
        self._reset_snake_and_food()
        self.score = 0
        self.state = "playing"
        self._clear_overlay()
        self._update_hud()
        self._refresh_canvas()
        self._schedule_next_step()

    def _restart(self) -> None:
        if self.state == "menu":
            self._begin_round()
            return
        self._cancel_step()
        self._reset_snake_and_food()
        self.score = 0
        self.state = "playing"
        self._clear_overlay()
        self._update_hud()
        self._refresh_canvas()
        self._schedule_next_step()

    def _to_menu(self) -> None:
        self._cancel_step()
        self.state = "menu"
        self.snake = []
        self.food = None
        self._clear_overlay()
        self._update_hud()
        self._refresh_canvas()

    def _reset_snake_and_food(self) -> None:
        self.direction = (1, 0)
        self.pending_dir = (1, 0)
        mid_y = ROWS // 2
        mid_x = COLS // 2
        self.snake = [(mid_x, mid_y), (mid_x - 1, mid_y), (mid_x - 2, mid_y)]
        self.food, self.food_bonus = self._spawn_food_with_kind()

    def _spawn_food_with_kind(self) -> tuple[tuple[int, int] | None, bool]:
        blocked = set(self.snake)
        choices = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in blocked]
        if not choices:
            return None, False
        pos = random.choice(choices)
        bonus = random.random() < BONUS_FOOD_CHANCE
        return pos, bonus

    def _clear_overlay(self) -> None:
        for iid in self._overlay_text_ids:
            self.canvas.delete(iid)
        self._overlay_text_ids.clear()
        if self._overlay_rect is not None:
            self.canvas.delete(self._overlay_rect)
            self._overlay_rect = None

    def _panel(self, lines: list[tuple[str, tkfont.Font, str]]) -> None:
        self._clear_overlay()
        pad = 28
        self._overlay_rect = self.canvas.create_rectangle(
            pad,
            pad,
            CANVAS_W - pad,
            CANVAS_H - pad,
            fill=OVERLAY_BG,
            outline=OVERLAY_STROKE,
            width=2,
        )
        cx = CANVAS_W // 2
        y = CANVAS_H // 2 - (len(lines) - 1) * 14
        ids: list[int] = []
        for text, font, color in lines:
            ids.append(self.canvas.create_text(cx, y, text=text, fill=color, font=font))
            y += 28 if font == self._title_font else 22
        self._overlay_text_ids = ids

    def _show_menu_overlay(self) -> None:
        lines = [
            ("SNAKE", self._title_font, ACCENT_SOFT),
            ("Space veya Enter — oyunu başlat", self._subtitle_font, MUTED),
            ("P / Esc — duraklat · R — yeniden · M — menü", self._small_font, MUTED),
            ("Sarı yem: bonus puan", self._small_font, FOOD_BONUS),
        ]
        self._panel(lines)

    def _show_pause_overlay(self) -> None:
        lines = [
            ("Duraklatıldı", self._title_font, TEXT),
            ("Devam: P veya Esc", self._subtitle_font, MUTED),
            ("R — sıfırla · M — ana menü", self._small_font, MUTED),
        ]
        self._panel(lines)

    def _show_game_over(self, new_record: bool) -> None:
        extra = "Yeni rekor!" if new_record else ""
        lines = [
            ("Oyun bitti", self._title_font, TEXT),
            (f"Skor: {self.score}  {extra}".strip(), self._subtitle_font, GOLD if new_record else ACCENT_SOFT),
            ("R — tekrar · M — menü · Space — yeni oyun", self._small_font, MUTED),
        ]
        self._panel(lines)

    def _show_victory(self, new_record: bool) -> None:
        sub = "Tüm alanı doldurdun."
        if new_record:
            sub = f"{sub} Yeni rekor!"
        lines = [
            ("Tebrikler!", self._title_font, TEXT),
            (sub, self._subtitle_font, MUTED),
            ("R veya Space — yeni oyun · M — menü", self._small_font, MUTED),
        ]
        self._panel(lines)

    def _draw_board(self) -> None:
        for y in range(ROWS):
            for x in range(COLS):
                fill = BG_CELL_A if (x + y) % 2 == 0 else BG_CELL_B
                x0, y0 = x * CELL, y * CELL
                self.canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + CELL,
                    y0 + CELL,
                    fill=fill,
                    outline=GRID_LINE,
                    width=1,
                    tags="cell",
                )
        self.canvas.create_rectangle(
            1,
            1,
            CANVAS_W - 2,
            CANVAS_H - 2,
            outline=FRAME_OUTER,
            width=2,
            tags="cell",
        )

    def _oval_segment(
        self,
        gx: int,
        gy: int,
        inset: int,
        fill: str,
        outline: str,
        shadow: bool = True,
    ) -> None:
        x1 = gx * CELL + inset
        y1 = gy * CELL + inset
        x2 = (gx + 1) * CELL - inset
        y2 = (gy + 1) * CELL - inset
        if shadow and x2 > x1 + 2 and y2 > y1 + 2:
            self.canvas.create_oval(
                x1 + 2,
                y1 + 2,
                x2 + 2,
                y2 + 2,
                fill=SNAKE_SHADOW,
                outline="",
                tags="cell",
            )
        self.canvas.create_oval(
            x1,
            y1,
            x2,
            y2,
            fill=fill,
            outline=outline,
            width=1,
            tags="cell",
        )

    def _draw_eyes(self, gx: int, gy: int, direction: tuple[int, int]) -> None:
        dx, dy = direction
        cx = gx * CELL + CELL // 2
        cy = gy * CELL + CELL // 2
        if dx != 0:
            s = 1 if dx > 0 else -1
            eyes = [(cx + s * 5, cy - 3), (cx + s * 5, cy + 3)]
            pup = (s * 2, 0)
        else:
            s = 1 if dy > 0 else -1
            eyes = [(cx - 3, cy + s * 5), (cx + 3, cy + s * 5)]
            pup = (0, s * 2)
        for ex, ey in eyes:
            self.canvas.create_oval(
                ex - 3,
                ey - 3,
                ex + 3,
                ey + 3,
                fill="#f8fafc",
                outline="#cbd5e1",
                width=1,
                tags="cell",
            )
            px, py = ex + pup[0], ey + pup[1]
            self.canvas.create_oval(
                px - 2,
                py - 2,
                px + 2,
                py + 2,
                fill="#0f172a",
                outline="",
                tags="cell",
            )

    def _draw_food(self, fx: int, fy: int) -> None:
        if self.food_bonus:
            self._oval_segment(fx, fy, 2, FOOD_BONUS, FOOD_BONUS_RING, shadow=False)
            self._oval_segment(fx, fy, 5, "#fde68a", "#ca8a04", shadow=False)
            hx = fx * CELL + 5
            hy = fy * CELL + 5
            self.canvas.create_oval(
                hx,
                hy,
                hx + 6,
                hy + 6,
                fill="#fffbeb",
                outline="",
                tags="cell",
            )
            return

        self._oval_segment(fx, fy, 3, FOOD, FOOD_DEEP, shadow=True)
        sx = fx * CELL + 5
        sy = fy * CELL + 4
        self.canvas.create_oval(
            sx,
            sy,
            sx + 7,
            sy + 7,
            fill=FOOD_SHINE,
            outline="",
            tags="cell",
        )
        mx = fx * CELL + CELL // 2
        top = fy * CELL + 2
        self.canvas.create_line(
            mx - 1,
            fy * CELL + 8,
            mx + 2,
            top,
            fill="#3f6212",
            width=2,
            capstyle=tk.ROUND,
            tags="cell",
        )

    def _draw_entities(self) -> None:
        if self.food is not None:
            fx, fy = self.food
            self._draw_food(fx, fy)

        for i, (sx, sy) in enumerate(self.snake):
            is_head = i == 0
            inset = 2 if is_head else 3
            if is_head:
                fill, outline = SNAKE_HEAD, SNAKE_HEAD_EDGE
            else:
                fill = SNAKE_BODY if i % 2 == 0 else SNAKE_BODY_ALT
                outline = SNAKE_BODY_ALT if i % 2 == 0 else SNAKE_BODY
            self._oval_segment(sx, sy, inset, fill, outline, shadow=True)

        if self.snake:
            hx, hy = self.snake[0]
            self._draw_eyes(hx, hy, self.direction)

    def _refresh_canvas(self) -> None:
        self.canvas.delete("cell")
        self._draw_board()
        if self.state == "menu":
            self._show_menu_overlay()
            return
        self._draw_entities()
        if self.state == "paused":
            self._show_pause_overlay()
        elif self.state == "game_over":
            self._show_game_over(self._last_was_record)
        elif self.state == "victory":
            self._show_victory(self._last_was_record)

    def _simulate_tick(self) -> None:
        self.direction = self.pending_dir
        hx, hy = self.snake[0]
        dx, dy = self.direction
        nx, ny = hx + dx, hy + dy

        if nx < 0 or nx >= COLS or ny < 0 or ny >= ROWS:
            self._game_over()
            return

        eating = self.food is not None and (nx, ny) == self.food
        if eating:
            if (nx, ny) in self.snake:
                self._game_over()
                return
        else:
            if (nx, ny) in self.snake[:-1]:
                self._game_over()
                return

        self.snake.insert(0, (nx, ny))
        if eating:
            add = 1 + (BONUS_POINTS if self.food_bonus else 0)
            self.score += add
            self._update_hud()
            nxt, bonus = self._spawn_food_with_kind()
            if nxt is None:
                self.food = None
                self.state = "victory"
                self._last_was_record = self.score > self.high_score
                if self._last_was_record:
                    self.high_score = self.score
                    self._save_high_score()
                self._cancel_step()
                self._update_hud()
                self._refresh_canvas()
                return
            self.food = nxt
            self.food_bonus = bonus
        else:
            self.snake.pop()

        self.canvas.delete("cell")
        self._draw_board()
        self._draw_entities()

    def _game_over(self) -> None:
        self.state = "game_over"
        self._cancel_step()
        self._last_was_record = self.score > self.high_score
        if self._last_was_record:
            self.high_score = self.score
            self._save_high_score()
        self._update_hud()
        self._show_game_over(self._last_was_record)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    SnakeApp().run()


if __name__ == "__main__":
    main()
