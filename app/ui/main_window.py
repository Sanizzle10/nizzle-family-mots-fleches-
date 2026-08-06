from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF, QThread, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import random

from app.dictionary import load_dictionary
from app.generator import CLUE_CELL
from app.parallel import generate_best, worker_count
from app.models import (
    ARROW_DOWN,
    ARROW_DOWN_RIGHT,
    ARROW_RIGHT,
    ARROW_RIGHT_DOWN,
    Placement,
)

BLUE = QColor("#15317E")
RED = QColor("#EF3340")
CLUE_BG = QColor("#FDE9E9")
TEXT_DARK = QColor("#17191F")


class GridWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.grid: list[list[str | None]] = []
        self.placements: list[Placement] = []
        self.show_answers = True
        self.setMinimumSize(520, 640)

    def set_grid(
        self,
        grid: list[list[str | None]],
        placements: list[Placement] | None = None,
    ) -> None:
        self.grid = grid
        self.placements = placements or []
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self.render_grid(painter, QRectF(self.rect()), self.show_answers)

    def render_grid(
        self,
        painter: QPainter,
        target: QRectF,
        show_answers: bool,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(target, QColor("#F4F6FA"))

        if not self.grid:
            painter.setPen(QColor("#6B7280"))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(
                target,
                Qt.AlignCenter,
                "Importez un dictionnaire puis générez une grille",
            )
            painter.restore()
            return

        clue_map: dict[tuple[int, int], list[Placement]] = defaultdict(list)
        for placement in self.placements:
            clue_map[(placement.clue_row, placement.clue_col)].append(placement)
        for values in clue_map.values():
            values.sort(key=lambda p: (p.row, p.col, not p.horizontal))

        rows = len(self.grid)
        cols = len(self.grid[0])
        margin = 14
        cell = min(
            (target.width() - 2 * margin) / cols,
            (target.height() - 2 * margin) / rows,
        )
        left = target.x() + (target.width() - cell * cols) / 2
        top = target.y() + (target.height() - cell * rows) / 2

        arrow_jobs: list[tuple[QRectF, QRectF, str]] = []
        for row in range(rows):
            for col in range(cols):
                rect = QRectF(left + col * cell, top + row * cell, cell, cell)
                value = self.grid[row][col]

                if value == CLUE_CELL:
                    clues = clue_map.get((row, col), [])
                    zones = self._draw_clue_cell(painter, rect, clues, cell)
                    for placement, zone in zip(clues[:2], zones):
                        arrow_jobs.append((rect, zone, placement.arrow))
                    continue

                painter.setPen(QPen(BLUE, max(1.0, cell * 0.022)))
                painter.setBrush(QColor("#FFFFFF"))
                painter.drawRect(rect)

                if value and show_answers:
                    painter.setPen(TEXT_DARK)
                    letter_font = QFont("Segoe UI")
                    letter_font.setBold(True)
                    # Taille en pixels : indépendante du DPI (écran ou PDF).
                    letter_font.setPixelSize(max(8, int(cell * 0.52)))
                    painter.setFont(letter_font)
                    painter.drawText(rect, Qt.AlignCenter, value)

        # Les flèches débordent sur les cases voisines : deuxième passe pour
        # qu'elles ne soient pas recouvertes.
        for rect, zone, arrow in arrow_jobs:
            self._draw_arrow(painter, rect, zone, arrow, cell)

        painter.restore()

    # ------------------------------------------------------- cases définitions

    def _draw_clue_cell(
        self,
        painter: QPainter,
        rect: QRectF,
        clues: list[Placement],
        cell: float,
    ) -> list[QRectF]:
        painter.setPen(QPen(RED, max(1.0, cell * 0.025)))
        if not clues:
            painter.setBrush(BLUE)
            painter.drawRect(rect)
            return []
        painter.setBrush(CLUE_BG)
        painter.drawRect(rect)

        halves: list[QRectF]
        if len(clues) >= 2:
            half = rect.height() / 2
            halves = [
                QRectF(rect.x(), rect.y(), rect.width(), half),
                QRectF(rect.x(), rect.y() + half, rect.width(), half),
            ]
            painter.setPen(QPen(RED, max(0.8, cell * 0.015)))
            painter.drawLine(
                QPointF(rect.x(), rect.y() + half),
                QPointF(rect.right(), rect.y() + half),
            )
        else:
            halves = [rect]

        for placement, zone in zip(clues[:2], halves):
            self._draw_definition(painter, zone, placement.definition, cell)
        return halves

    def _draw_definition(
        self,
        painter: QPainter,
        zone: QRectF,
        text: str,
        cell: float,
    ) -> None:
        if not text:
            return
        painter.save()
        painter.setPen(QColor("#D71920"))

        pixel_size = max(6, int(cell * 0.17))
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(pixel_size)

        available = zone.adjusted(cell * 0.05, cell * 0.04, -cell * 0.09, -cell * 0.04)
        while pixel_size > 4:
            font.setPixelSize(pixel_size)
            metrics = QFontMetricsF(font)
            bounds = metrics.boundingRect(
                available,
                Qt.TextWordWrap | Qt.AlignCenter,
                text,
            )
            if (
                bounds.height() <= available.height()
                and bounds.width() <= available.width() + 0.5
            ):
                break
            pixel_size -= 1

        painter.setFont(font)
        painter.drawText(available, Qt.TextWordWrap | Qt.AlignCenter, text)
        painter.restore()

    def _draw_arrow(
        self,
        painter: QPainter,
        rect: QRectF,
        zone: QRectF,
        arrow: str,
        cell: float,
    ) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(RED)
        size = cell * 0.10

        def head(tip: QPointF, direction: str) -> None:
            if direction == "right":
                points = [
                    tip,
                    QPointF(tip.x() - size, tip.y() - size * 0.7),
                    QPointF(tip.x() - size, tip.y() + size * 0.7),
                ]
            else:  # down
                points = [
                    tip,
                    QPointF(tip.x() - size * 0.7, tip.y() - size),
                    QPointF(tip.x() + size * 0.7, tip.y() - size),
                ]
            painter.drawPolygon(QPolygonF(points))

        pen = QPen(RED, max(1.2, cell * 0.03))

        if arrow == ARROW_RIGHT:
            head(QPointF(rect.right() + size, zone.center().y()), "right")
        elif arrow == ARROW_DOWN:
            head(QPointF(rect.center().x(), rect.bottom() + size), "down")
        elif arrow == ARROW_DOWN_RIGHT:
            # sort par le bas, puis tourne vers la droite
            painter.setPen(pen)
            x = rect.x() + rect.width() * 0.22
            y = rect.bottom() + cell * 0.28
            painter.drawLine(QPointF(x, rect.bottom()), QPointF(x, y))
            painter.drawLine(QPointF(x, y), QPointF(x + cell * 0.2, y))
            painter.setPen(Qt.NoPen)
            head(QPointF(x + cell * 0.2 + size, y), "right")
        elif arrow == ARROW_RIGHT_DOWN:
            # sort par la droite, puis tourne vers le bas
            painter.setPen(pen)
            y = rect.y() + rect.height() * 0.22
            x = rect.right() + cell * 0.28
            painter.drawLine(QPointF(rect.right(), y), QPointF(x, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + cell * 0.2))
            painter.setPen(Qt.NoPen)
            head(QPointF(x, y + cell * 0.2 + size), "down")
        painter.restore()


class GenerationWorker(QThread):
    finished_with_result = Signal(object, object, object)
    failed = Signal(str)

    def __init__(
        self,
        entries: list,
        width: int,
        height: int,
        seconds: float,
        seed: int,
    ) -> None:
        super().__init__()
        self.entries = entries
        self.width = width
        self.height = height
        self.seconds = seconds
        self.seed = seed

    def run(self) -> None:
        try:
            grid, placements, stats = generate_best(
                self.entries,
                width=self.width,
                height=self.height,
                seconds=self.seconds,
                seed_base=self.seed,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_with_result.emit(grid, placements, stats)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.entries = []
        self.placements: list[Placement] = []
        self.illustration_path = ""
        self.worker: GenerationWorker | None = None

        self.setWindowTitle("Mots Fléchés Studio")
        self.resize(1380, 860)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)

        header = QHBoxLayout()
        self.title_edit = QLineEdit("Mots Fléchés Studio")
        self.title_edit.setMinimumWidth(240)
        header.addWidget(self.title_edit)
        header.addStretch()

        image_button = QPushButton("Ajouter illustration")
        image_button.clicked.connect(self.choose_illustration)
        header.addWidget(image_button)

        import_button = QPushButton("Importer dictionnaire")
        import_button.clicked.connect(self.import_dictionary)
        header.addWidget(import_button)

        header.addWidget(QLabel("Colonnes"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(6, 16)
        self.width_spin.setValue(8)
        header.addWidget(self.width_spin)

        header.addWidget(QLabel("Lignes"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(6, 20)
        self.height_spin.setValue(13)
        header.addWidget(self.height_spin)

        self.generate_button = QPushButton("Générer")
        self.generate_button.clicked.connect(self.generate)
        header.addWidget(self.generate_button)

        toggle_button = QPushButton("Afficher / masquer réponses")
        toggle_button.clicked.connect(self.toggle_answers)
        header.addWidget(toggle_button)

        pdf_button = QPushButton("Télécharger PDF")
        pdf_button.clicked.connect(self.export_pdf)
        header.addWidget(pdf_button)
        root.addLayout(header)

        self.illustration_preview = QLabel("Aucune illustration")
        self.illustration_preview.setAlignment(Qt.AlignCenter)
        self.illustration_preview.setMaximumHeight(110)
        self.illustration_preview.setStyleSheet(
            "background:white;border:1px dashed #BFC5D2;border-radius:12px;color:#6B7280;"
        )
        root.addWidget(self.illustration_preview)

        splitter = QSplitter(Qt.Horizontal)

        self.words_list = QListWidget()
        self.words_list.setMinimumWidth(250)
        splitter.addWidget(self.words_list)

        self.grid_widget = GridWidget()
        splitter.addWidget(self.grid_widget)

        self.definitions_list = QListWidget()
        self.definitions_list.setMinimumWidth(350)
        splitter.addWidget(self.definitions_list)

        splitter.setSizes([250, 760, 370])
        root.addWidget(splitter, 1)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background:#F4F6FA; color:#202124; font-family:'Segoe UI'; }
            QListWidget { background:white; border:1px solid #E2E6EE; border-radius:14px; padding:8px; }
            QListWidget::item { padding:5px 3px; }
            QPushButton { background:#5B5BD6; color:white; border:none; border-radius:9px; padding:9px 14px; font-weight:600; }
            QPushButton:hover { background:#4949BF; }
            QPushButton:disabled { background:#B9B9E3; }
            QSpinBox, QLineEdit { background:white; border:1px solid #D6DAE3; border-radius:8px; padding:7px; }
            """
        )

    def choose_illustration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une illustration",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return

        self.illustration_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.illustration_preview.setPixmap(
                pixmap.scaled(
                    900,
                    100,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self.illustration_preview.setText("")

    def import_dictionary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un dictionnaire",
            "",
            "Dictionnaires (*.csv *.xlsx)",
        )
        if not path:
            return

        try:
            self.entries = load_dictionary(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'import", str(exc))
            return

        self.refresh_word_list()
        self.definitions_list.clear()
        definitions = sum(len(entry.definitions) for entry in self.entries)
        self.statusBar().showMessage(
            f"{len(self.entries)} mots importés ({definitions} définitions)"
        )

    def refresh_word_list(self) -> None:
        self.words_list.clear()
        for entry in sorted(self.entries, key=lambda e: (-e.placed, e.word)):
            mark = "✓" if entry.placed else "•"
            count = len(entry.definitions)
            self.words_list.addItem(f"{mark}  {entry.word}  ({count} déf.)")

    def generate(self) -> None:
        if not self.entries:
            QMessageBox.information(
                self,
                "Dictionnaire requis",
                "Importez d'abord un dictionnaire (CSV ou Excel).",
            )
            return
        if self.worker is not None:
            return

        self.generate_button.setEnabled(False)
        cores = worker_count()
        self.statusBar().showMessage(
            f"Génération en cours… ({cores} recherche(s) en parallèle)"
        )
        self.worker = GenerationWorker(
            self.entries,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            # Plafond, pas un coût : la recherche s'arrête dès qu'une grille
            # est pleine. Être généreux ne ralentit pas les machines rapides
            # et sauve les lentes.
            seconds=25.0,
            seed=random.randrange(1_000_000),
        )
        self.worker.finished_with_result.connect(self.on_generated)
        self.worker.failed.connect(self.on_generation_failed)
        self.worker.finished.connect(self.on_worker_done)
        self.worker.start()

    def on_generation_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Échec de la génération : {message}")

    def on_generated(self, grid, placements, stats) -> None:
        self.placements = placements
        self.grid_widget.set_grid(grid, placements)
        self.refresh_word_list()

        self.definitions_list.clear()
        for placement in sorted(
            placements,
            key=lambda item: (item.clue_row, item.clue_col, not item.horizontal),
        ):
            arrow = "→" if placement.horizontal else "↓"
            self.definitions_list.addItem(
                f"{arrow}  {placement.definition}  [{placement.word}]"
            )

        if stats.get("complete"):
            message = (
                f"Grille pleine : {stats['words']} mots, "
                f"remplissage {stats['fill']}%"
            )
        else:
            message = (
                f"Grille partielle : {stats.get('words', 0)} mots, "
                f"remplissage {stats.get('fill', 0)}% — "
                "réessayez ou enrichissez le dictionnaire"
            )
        self.statusBar().showMessage(message)

    def on_worker_done(self) -> None:
        self.worker = None
        self.generate_button.setEnabled(True)

    def toggle_answers(self) -> None:
        self.grid_widget.show_answers = not self.grid_widget.show_answers
        self.grid_widget.update()

    def export_pdf(self) -> None:
        from app.pdf_exporter import export_book_pdf

        if not self.grid_widget.grid or not self.placements:
            QMessageBox.information(
                self,
                "Grille requise",
                "Générez d'abord une grille.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le PDF",
            f"{self.title_edit.text().strip() or 'mots-fleches'}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        export_book_pdf(
            path,
            self.title_edit.text().strip(),
            self.grid_widget,
            self.illustration_path,
        )
        self.statusBar().showMessage(f"PDF enregistré : {path}")


def run_app() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
