from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
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
from app.generator import GridGenerator


class GridWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.grid: list[list[str | None]] = []
        self.show_answers = True
        self.setMinimumSize(600, 600)

    def set_grid(self, grid: list[list[str | None]]) -> None:
        self.grid = grid
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#F4F6FA"))

        if not self.grid:
            painter.setPen(QColor("#6B7280"))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "Importez un fichier Excel puis générez une grille")
            return

        size = len(self.grid)
        margin = 24
        cell = min((self.width() - 2 * margin) / size, (self.height() - 2 * margin) / size)
        total = cell * size
        left = (self.width() - total) / 2
        top = (self.height() - total) / 2

        for row in range(size):
            for col in range(size):
                x = left + col * cell
                y = top + row * cell
                value = self.grid[row][col]

                painter.setPen(QPen(QColor("#D7DCE5"), 1))
                painter.setBrush(QColor("#FFFFFF") if value else QColor("#20242B"))
                painter.drawRect(x, y, cell, cell)

                if value and self.show_answers:
                    painter.setPen(QColor("#17191F"))
                    painter.setFont(QFont("Segoe UI", max(8, int(cell * 0.38)), QFont.Bold))
                    painter.drawText(x, y, cell, cell, Qt.AlignCenter, value)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.entries = []
        self.placements = []

        self.setWindowTitle("Mots Fléchés Studio")
        self.resize(1320, 820)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)

        header = QHBoxLayout()
        title = QLabel("Mots Fléchés Studio")
        title.setStyleSheet("font-size:26px;font-weight:700;")
        header.addWidget(title)
        header.addStretch()

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
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)

        self.words_list = QListWidget()
        self.words_list.setMinimumWidth(260)
        splitter.addWidget(self.words_list)

        self.grid_widget = GridWidget()
        splitter.addWidget(self.grid_widget)

        self.definitions_list = QListWidget()
        self.definitions_list.setMinimumWidth(300)
        splitter.addWidget(self.definitions_list)

        splitter.setSizes([280, 720, 320])
        root.addWidget(splitter, 1)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background:#F4F6FA; color:#202124; font-family:'Segoe UI'; }
            QListWidget { background:white; border:1px solid #E2E6EE; border-radius:14px; padding:8px; }
            QPushButton { background:#5B5BD6; color:white; border:none; border-radius:9px; padding:9px 14px; font-weight:600; }
            QPushButton:hover { background:#4949BF; }
            QSpinBox { background:white; border:1px solid #D6DAE3; border-radius:8px; padding:7px; }
            """
        )

    def import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importer un dictionnaire", "", "Excel (*.xlsx)")
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
            QMessageBox.information(self, "Dictionnaire requis", "Importez d'abord un fichier Excel.")
            return

        generator = GridGenerator(size=self.size_spin.value(), seconds=5.0)
        grid, self.placements = generator.generate(self.entries)
        self.grid_widget.set_grid(grid)

        self.words_list.clear()
        for entry in self.entries:
            self.words_list.addItem(f"{'✓' if entry.placed else '•'}  {entry.word}")

        placed = sum(entry.placed for entry in self.entries)
        self.statusBar().showMessage(f"{placed} mots placés sur {len(self.entries)}")

    def toggle_answers(self) -> None:
        self.grid_widget.show_answers = not self.grid_widget.show_answers
        self.grid_widget.update()


def run_app() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
