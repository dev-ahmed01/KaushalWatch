#!/usr/bin/env python3
"""Phase 3U local frame-accurate GUI for Phase 3T *blinded* worksheets.

Run on a machine containing the original recorded AVI videos. No server,
network, model, reference re-enrolment, video export, image save, or scene
notification. Only reviewer answers are written to a DIFFERENT local CSV.
The reviewer never sees the sealed model comparison key or event labels.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

from phase3t_review_viewer_core import (
    CHOICES, NOTES, REVIEW_COLUMNS, FrameBounds, ReviewSession,
    format_video_time, read_exact_frame, read_sequential_frame,
)

QUESTION_LABELS = (
    ("footage_available_yes_no_unknown", "Is the original footage available?"),
    ("visible_focus_loss_yes_no_uncertain", "Visible focus loss?"),
    ("lighting_transition_yes_no_uncertain", "Lighting transition?"),
    ("physical_camera_displacement_yes_no_uncertain", "Camera displaced?"),
    ("foreground_occlusion_yes_no_uncertain", "Camera view obstructed?"),
    ("image_usable_for_human_observation_yes_no_uncertain",
     "Image usable for observation?"),
    ("reviewer_confidence_low_medium_high", "Review confidence"),
)


class BlindReviewApp:
    def __init__(self, root, *, tk, ttk, messagebox, cv2, session: ReviewSession,
                 video_paths: dict[str, Path], reviewer_id: str = ""):
        self.root = root
        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.cv2 = cv2
        self.session = session
        self.video_paths = video_paths
        self.reviewer_default = reviewer_id
        self.case_index = -1
        self.cap = None
        self.fps = None
        self.bounds = None
        self.current_frame = None
        self.photo = None
        self.playing = False
        self.after_id = None
        self.loading = False
        self._build()
        self._open_case(0)
        root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        tk, ttk = self.tk, self.ttk
        self.root.title("KaushalWatch | Independent camera review — BLINDED / LOCAL")
        self.root.geometry("1480x920")
        self.root.minsize(1120, 740)
        self.root.configure(bg="#f5f7f7")
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        heading = ttk.Frame(outer)
        heading.pack(fill="x", pady=(0, 10))
        ttk.Label(
            heading, text="Independent camera review",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")
        ttk.Label(
            heading, text="LOCAL ONLY  |  BLINDED  |  No model predictions",
            font=("Segoe UI", 10),
        ).pack(side="right")
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=188)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0, minsize=355)
        body.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(body, padding=(2, 0, 10, 0))
        sidebar.grid(row=0, column=0, sticky="nsew")
        ttk.Label(sidebar, text="Review cases", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        self.case_list = tk.Listbox(
            sidebar, width=21, font=("Consolas", 10),
            activestyle="none", exportselection=False,
        )
        scrollbar = ttk.Scrollbar(sidebar, command=self.case_list.yview)
        self.case_list.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.case_list.pack(side="left", fill="both", expand=True)
        self.case_list.bind("<<ListboxSelect>>", self._select_from_list)

        middle = ttk.Frame(body, padding=(0, 0, 10, 0))
        middle.grid(row=0, column=1, sticky="nsew")
        top = ttk.Frame(middle)
        top.pack(fill="x", pady=(0, 8))
        self.case_label = ttk.Label(top, font=("Segoe UI", 12, "bold"))
        self.case_label.pack(side="left")
        ttk.Button(top, text="Previous case", command=self._previous_case).pack(
            side="right", padx=(4, 0)
        )
        ttk.Button(top, text="Next case", command=self._next_case).pack(
            side="right", padx=4
        )
        self.video_label = tk.Label(
            middle, text="Opening local video…",
            font=("Segoe UI", 12), bg="#101820", fg="#e5e7eb",
            compound="center", justify="center", padx=10, pady=8,
        )
        self.video_label.pack(fill="both", expand=True)
        self.position_label = ttk.Label(
            middle, text="Video time (relative, not wall clock) · Frame —",
        )
        self.position_label.pack(fill="x", pady=(8, 0))
        self.frame_scale = tk.Scale(
            middle, from_=1, to=2, orient="horizontal",
            showvalue=False, sliderlength=22, resolution=1,
            highlightthickness=0, state="disabled",
        )
        self.frame_scale.pack(fill="x")
        self.frame_scale.bind("<ButtonRelease-1>", self._seek_scale)
        self.frame_scale.bind("<Return>", self._seek_scale)
        controls = ttk.Frame(middle)
        controls.pack(fill="x")
        ttk.Button(controls, text="|< Start", command=self._start).pack(
            side="left", padx=2
        )
        ttk.Button(controls, text="< Frame", command=lambda: self._step(-1)).pack(
            side="left", padx=2
        )
        self.play_button = ttk.Button(
            controls, text="▶ Play", command=self._toggle_play
        )
        self.play_button.pack(side="left", padx=2)
        ttk.Button(controls, text="Frame >", command=lambda: self._step(1)).pack(
            side="left", padx=2
        )
        ttk.Button(controls, text="End >|", command=self._end).pack(
            side="left", padx=2
        )
        ttk.Label(
            middle,
            text="Use playback controls or drag the slider. Seeking verifies exact "
                 "decoded frame position; if a codec cannot seek exactly, review stops.",
            wraplength=750, foreground="#52616b",
        ).pack(anchor="w", pady=(8, 0))
        self.video_status = ttk.Label(middle, text="")
        self.video_status.pack(anchor="w", pady=(5, 0))

        review = ttk.Frame(body, padding=10, relief="groove")
        review.grid(row=0, column=2, sticky="nsew")
        ttk.Label(review, text="Reviewer observations",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            review, text="Do not view the sealed model key. Use uncertain "
                         "when the physical condition cannot be established.",
            wraplength=330,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(review, text="Reviewer identifier").pack(anchor="w")
        self.reviewer_var = tk.StringVar(value=self.reviewer_default)
        ttk.Entry(review, textvariable=self.reviewer_var, width=34).pack(
            fill="x", pady=(2, 8)
        )
        self.questions = {}
        for key, question in QUESTION_LABELS:
            ttk.Label(review, text=question, wraplength=320).pack(
                anchor="w", pady=(7, 2)
            )
            variable = tk.StringVar(value="")
            picker = ttk.Combobox(
                review, textvariable=variable,
                values=CHOICES[key][1:], state="readonly", width=32,
            )
            picker.pack(fill="x")
            self.questions[key] = variable
        ttk.Label(
            review, text="Notes (avoid personal identifiers)"
        ).pack(anchor="w", pady=(12, 3))
        self.notes = tk.Text(review, height=5, wrap="word", font=("Segoe UI", 10))
        self.notes.pack(fill="both", expand=True, pady=(0, 8))
        ttk.Button(
            review, text="Save review progress", command=self._manual_save
        ).pack(fill="x", pady=(4, 6))
        self.progress_label = ttk.Label(review, text="0 reviewed")
        self.progress_label.pack(anchor="w")
        ttk.Label(
            review,
            text="Answers are saved in a separate local CSV. "
                 "The original assignment is never overwritten.",
            wraplength=320, foreground="#52616b",
        ).pack(anchor="w", pady=(8, 0))
        self._refresh_list()

    def _refresh_list(self):
        self.case_list.delete(0, "end")
        for i, row in enumerate(self.session.rows):
            marker = "✓" if self.session.completed(i) else "·"
            self.case_list.insert("end", f"{marker} {row['case_id']}")
        self.progress_label.config(
            text=f"{self.session.completed_count}/{len(self.session.rows)} "
                 f"cases complete"
        )

    def _select_from_list(self, _event):
        if self.loading:
            return
        selection = self.case_list.curselection()
        if selection and selection[0] != self.case_index:
            self._open_case(selection[0])

    def _sync_answers(self) -> bool:
        if self.case_index < 0:
            return True
        values = {key: var.get() for key, var in self.questions.items()}
        values[NOTES] = self.notes.get("1.0", "end-1c").strip()
        values["reviewer_id"] = self.reviewer_var.get().strip()
        try:
            self.session.update(self.case_index, values)
            self.session.save()
        except (OSError, ValueError) as exc:
            self.messagebox.showerror(
                "Review could not be saved", str(exc)
            )
            return False
        self._refresh_list()
        return True

    def _manual_save(self):
        if self._sync_answers():
            self.video_status.config(text=f"Saved to {self.session.output}")

    def _stop(self):
        self.playing = False
        self.play_button.config(text="▶ Play")
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def _release_capture(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.fps = None
        self.bounds = None
        self.current_frame = None

    def _open_case(self, index: int):
        if index < 0 or index >= len(self.session.rows):
            return
        if index != self.case_index and not self._sync_answers():
            return
        self._stop()
        self._release_capture()
        self.case_index = index
        row = self.session.rows[index]
        self.loading = True
        try:
            self._refresh_list()
            self.case_list.selection_clear(0, "end")
            self.case_list.selection_set(index)
            self.case_list.see(index)
            self.case_label.config(
                text=f"{row['case_id']}  ·  {row['video_alias']}  ·  "
                     f"Frames {row['start_frame']}–{row['end_frame']}"
            )
            self.reviewer_var.set(row["reviewer_id"] or self.reviewer_default)
            for key, var in self.questions.items():
                var.set(row[key])
            self.notes.delete("1.0", "end")
            self.notes.insert("1.0", row[NOTES])
            self.bounds = FrameBounds(
                int(row["start_frame"]), int(row["end_frame"])
            )
            self.frame_scale.config(
                from_=self.bounds.start, to=self.bounds.end,
                state="normal",
            )
            self.frame_scale.set(self.bounds.start)
            self.position_label.config(text=f"Video: {row['video_alias']}")
            self.video_status.config(text="")
            path = self.video_paths[row["video_alias"]]
            if not path.is_file():
                raise OSError(f"Original video does not exist: {path}")
            self.cap = self.cv2.VideoCapture(str(path))
            if not self.cap.isOpened():
                raise OSError(f"Cannot open original video: {path}")
            self.fps = self.cap.get(self.cv2.CAP_PROP_FPS)
            if not isinstance(self.fps, (int, float)) or not math.isfinite(self.fps) or self.fps <= 0:
                raise ValueError("Video FPS is missing or invalid")
            count = self.cap.get(self.cv2.CAP_PROP_FRAME_COUNT)
            if (isinstance(count, (int, float)) and math.isfinite(count)
                    and count > 0 and count + 0.5 < self.bounds.end):
                raise ValueError(
                    f"Selected frame {self.bounds.end} exceeds the "
                    f"local video frame count {count}"
                )
            self._seek_to(self.bounds.start)
        except (OSError, ValueError, RuntimeError) as exc:
            self._stop()
            self._release_capture()
            self.video_label.config(
                image="", text="Local video unavailable\n\n" + str(exc)
            )
            self.photo = None
            self.video_status.config(
                text="No footage shown; you can still mark availability unknown/no."
            )
        finally:
            self.loading = False

    def _display_frame(self, frame, index: int):
        # Purely in-memory RGB -> portable pixelmap -> Tk PhotoImage.
        # No frame/crop/image is written, logged, uploaded or persisted.
        h, w = frame.shape[:2]
        target_w = max(320, min(1100, self.video_label.winfo_width()-12))
        target_h = max(220, min(690, self.video_label.winfo_height()-12))
        ratio = min(1.0, target_w/w, target_h/h)
        if ratio < 1:
            frame = self.cv2.resize(
                frame, (max(1, round(w*ratio)), max(1, round(h*ratio))),
                interpolation=self.cv2.INTER_AREA,
            )
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        hh, ww = rgb.shape[:2]
        ppm = f"P6\n{ww} {hh}\n255\n".encode("ascii") + rgb.tobytes()
        image = self.tk.PhotoImage(data=ppm, format="PPM")
        self.photo = image
        self.video_label.config(image=image, text="")
        self.current_frame = index
        self.frame_scale.set(index)
        self.position_label.config(
            text=f"Frame {index:,} / {self.bounds.end:,}  ·  "
                 f"Source time {format_video_time(index, self.fps)} "
                 "(relative to start of video)"
        )

    def _seek_to(self, index: int):
        if self.cap is None or self.bounds is None:
            return
        n = self.bounds.clamp(index)
        frame = read_exact_frame(self.cap, n, self.cv2)
        self._display_frame(frame, n)

    def _step(self, amount: int):
        if self.cap is None:
            return
        self._stop()
        target = self.bounds.advance(
            self.current_frame or self.bounds.start, amount
        )
        try:
            self._seek_to(target)
        except (ValueError, OSError, RuntimeError) as exc:
            self.video_status.config(text=f"Stopped: {exc}")

    def _start(self):
        self._stop()
        if self.bounds is not None:
            try:
                self._seek_to(self.bounds.start)
            except (ValueError, OSError) as exc:
                self.video_status.config(text=str(exc))

    def _end(self):
        self._stop()
        if self.bounds is not None:
            try:
                self._seek_to(self.bounds.end)
            except (ValueError, OSError) as exc:
                self.video_status.config(text=str(exc))

    def _seek_scale(self, _event=None):
        if self.cap is not None:
            self._stop()
            try:
                self._seek_to(int(self.frame_scale.get()))
            except (ValueError, OSError) as exc:
                self.video_status.config(text=str(exc))

    def _toggle_play(self):
        if self.cap is None or self.bounds is None:
            return
        if self.playing:
            self._stop()
            return
        if self.current_frame is None:
            return
        if self.current_frame == self.bounds.end:
            try:
                self._seek_to(self.bounds.start)
            except (ValueError, OSError) as exc:
                self.video_status.config(text=str(exc))
                return
        self.playing = True
        self.play_button.config(text="Ⅱ Pause")
        self._tick()

    def _tick(self):
        self.after_id = None
        if not self.playing or self.cap is None or self.bounds is None:
            return
        next_frame = self.current_frame + 1
        if not self.bounds.allows(next_frame):
            self._stop()
            return
        try:
            image = read_sequential_frame(self.cap, next_frame, self.cv2)
            self._display_frame(image, next_frame)
        except (ValueError, OSError, RuntimeError) as exc:
            self._stop()
            self.video_status.config(text=f"Playback stopped: {exc}")
            return
        delay = max(25, round(1000 / self.fps))
        self.after_id = self.root.after(delay, self._tick)

    def _previous_case(self):
        self._open_case(self.case_index - 1)

    def _next_case(self):
        self._open_case(self.case_index + 1)

    def _close(self):
        self._stop()
        if not self._sync_answers():
            return  # Keep editor open if it cannot preserve review answers.
        self._release_capture()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worksheet", type=Path, help="Original reviewer_01.csv or reviewer_02.csv")
    parser.add_argument("--day3-video", type=Path, help="Original Day3 video.avi")
    parser.add_argument("--day4-video", type=Path, help="Original Day4 video.avi")
    parser.add_argument("--out", type=Path, help="Different local completed CSV path")
    parser.add_argument("--reviewer-id", default="", help="Non-identifying ID, e.g. reviewer01")
    args = parser.parse_args()

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        parser.error("Tkinter unavailable; install official Python with Tcl/Tk support")
    try:
        import cv2
    except ImportError:
        parser.error("OpenCV missing; run: python -m pip install opencv-python")
    root = tk.Tk()
    root.withdraw()
    try:
        worksheet = args.worksheet or filedialog.askopenfilename(
            title="Choose BLINDED reviewer assignment CSV (not sealed JSON)",
            filetypes=[("Review worksheet CSV", "*.csv")],
        )
        if not worksheet:
            root.destroy()
            return
        day3 = args.day3_video or filedialog.askopenfilename(
            title="Choose original DAY3 video.avi",
            filetypes=[("Video files", "*.avi *.mp4 *.mov"), ("All files", "*.*")],
        )
        day4 = args.day4_video or filedialog.askopenfilename(
            title="Choose original DAY4 video.avi",
            filetypes=[("Video files", "*.avi *.mp4 *.mov"), ("All files", "*.*")],
        )
        if not day3 or not day4:
            root.destroy()
            return
        file = Path(worksheet).expanduser()
        output = args.out or file.with_name(file.stem + "_completed_local.csv")
        session = ReviewSession(file, Path(output).expanduser())
        if args.reviewer_id:
            from phase3t_review_viewer_core import ID_RE
            if not ID_RE.fullmatch(args.reviewer_id):
                raise ValueError("Reviewer ID may contain only letters, numbers, dots, underscores or hyphens")
        app = BlindReviewApp(
            root, tk=tk, ttk=ttk, messagebox=messagebox, cv2=cv2,
            session=session,
            video_paths={
                "DAY3": Path(day3).expanduser(),
                "DAY4": Path(day4).expanduser(),
            },
            reviewer_id=args.reviewer_id,
        )
    except (ValueError, OSError, csv.Error) as exc:
        messagebox.showerror("Unable to load blind review", str(exc))
        root.destroy()
        return
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    import csv
    main()
