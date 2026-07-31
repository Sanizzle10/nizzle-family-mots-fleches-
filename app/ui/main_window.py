from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QPixmap
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

from app.excel_loader import load_dictionary
from app.generator import CLUE_CELL, GridGenerator
from app.models import Placement
from app.pdf_exporter import export_book_pdf


class GridWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.grid: list[list[str | None]] = []
        self.placements: list[Placement] = []
        self.show_answers = True
        self.setMinimumSize(600, 600)

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
                "Importez un fichier Excel puis générez une grille",
            )
            painter.restore()
            return

        clue_map: dict[tuple[int, int], list[Placement]] = defaultdict(list)
        for placement in self.placements:
            clue_map[(placement.clue_row, placement.clue_col)].append(placement)

        size = len(self.grid)
        margin = 18
        cell = min(
            (target.width() - 2 * margin) / size,
            (target.height() - 2 * margin) / size,
        )
        total = cell * size
        left = target.x() + (target.width() - total) / 2
        top = target.y() + (target.height() - total) / 2

        for row in range(size):
            for col in range(size):
                rect = QRectF(left + col * cell, top + row * cell, cell, cell)
                value = self.grid[row][col]

                if value == CLUE_CELL:
                    painter.setPen(QPen(QColor("#EF3340"), 1.2))
                    painter.setBrush(QColor("#FFE8E8"))
                    painter.drawRect(rect)
                    self._draw_definition(
                        painter,
                        rect,
                        clue_map.get((row, col), []),
                        cell,
                    )
                    continue

                painter.setPen(QPen(QColor("#15317E"), 1.1))
                painter.setBrush(QColor("#FFFFFF") if value else QColor("#FFFFFF"))
                painter.drawRect(rect)

                if value and show_answers:
                    painter.setPen(QColor("#17191F"))
                    painter.setFont(
                        QFont("Segoe UI", max(8, int(cell * 0.38)), QFont.Bold)
                    )
                    painter.drawText(rect, Qt.AlignCenter, value)

        painter.restore()

    def _draw_definition(
        self,
        painter: QPainter,
        rect: QRectF,
        placements: list[Placement],
        cell: float,
    ) -> None:
        if not placements:
            return

        parts = []
        for placement in placements[:2]:
            arrow = "→" if placement.horizontal else "↓"
            parts.append(f"{placement.definition}\n{arrow}")
        text = "\n".join(parts)

        painter.save()
        painter.setPen(QColor("#D71920"))

        pixel_size = max(5, int(cell * 0.16))
        font = QFont("Segoe UI")
        font.setBold(True)
        font.setPixelSize(pixel_size)
        painter.setFont(font)

        available = rect.adjusted(1.5, 1.5, -1.5, -1.5)
        while pixel_size > 4:
            metrics = QFontMetricsF(font)
            bounds = metrics.boundingRect(
                available,
                Qt.TextWordWrap | Qt.AlignCenter,
                text,
            )
            if bounds.height() <= available.height():
                break
            pixel_size -= 1
            font.setPixelSize(pixel_size)
            painter.setFont(font)

        painter.drawText(
            available,
            Qt.TextWordWrap | Qt.AlignCenter,
            text,
        )
        painter.restore()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.entries = []
        self.placements: list[Placement] = []
        self.illustration_path = ""

        self.setWindowTitle("Mots Fléchés Studio")
        self.resize(1380, 860)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)

        header = QHBoxLayout()
        self.title_edit = QLineEdit("Mots Fléchés Studio")
        self.title_edit.setMinimumWidth(260)
        header.addWidget(self.title_edit)
        header.addStretch()

        image_button = QPushButton("Ajouter illustration")
        image_button.clicked.connect(self.choose_illustration)
        header.addWidget(image_button)

        import_button = QPushButton("Importer Excel")
        import_button.clicked.connect(self.import_excel)
        header.addWidget(import_button)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(10, 40)
        self.size_spin.setValue(20)
        header.addWidget(self.size_spin)

        generate_button = QPushButton("Générer")
        generate_button.clicked.connect(self.generate)
        header.addWidget(generate_button)

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

    def import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un dictionnaire",
            "",
            "Excel (*.xlsx)",
        )
        if not path:
            return

        try:
            self.entries = load_dictionary(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'import", str(exc))
            return

        self.words_list.clear()
        self.definitions_list.clear()
        for entry in self.entries:
            self.words_list.addItem(entry.word)
            self.definitions_list.addItem(f"{entry.word} — {entry.definition}")
        self.statusBar().showMessage(f"{len(self.entries)} mots importés")

    def generate(self) -> None:
        if not self.entries:
            QMessageBox.information(
                self,
                "Dictionnaire requis",
                "Importez d'abord un fichier Excel.",
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            generator = GridGenerator(size=self.size_spin.value(), seconds=12.0)
            grid, self.placements = generator.generate(self.entries)
        finally:
            QApplication.restoreOverrideCursor()

        self.grid_widget.set_grid(grid, self.placements)

        self.words_list.clear()
        for entry in self.entries:
            self.words_list.addItem(f"{'✓' if entry.placed else '•'}  {entry.word}")

        self.definitions_list.clear()
        for placement in sorted(
            self.placements,
            key=lambda item: (item.clue_row, item.clue_col, not item.horizontal),
        ):
            arrow = "→" if placement.horizontal else "↓"
            self.definitions_list.addItem(f"{arrow}  {placement.definition}")

        placed = sum(entry.placed for entry in self.entries)
        self.statusBar().showMessage(
            f"{placed} mots placés sur {len(self.entries)}"
        )

    def toggle_answers(self) -> None:
        self.grid_widget.show_answers = not self.grid_widget.show_answers
        self.grid_widget.update()

    def export_pdf(self) -> None:
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
