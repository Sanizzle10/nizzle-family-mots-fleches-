from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPageSize, QPdfWriter


def export_book_pdf(
    path: str,
    title: str,
    grid_widget,
    illustration_path: str = "",
) -> None:
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setResolution(300)

    painter = QPainter(writer)
    page = QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))

    painter.fillRect(page, QColor("#15317E"))

    border = page.adjusted(130, 120, -130, -120)
    painter.fillRect(border, QColor("#EF3340"))

    inner = border.adjusted(55, 55, -55, -55)
    painter.fillRect(inner, QColor("#FFFFFF"))

    if illustration_path and Path(illustration_path).exists():
        image = QImage(illustration_path)
        if not image.isNull():
            banner = QRectF(inner.x(), inner.y(), inner.width(), 240)
            painter.drawImage(banner, image)

    painter.setPen(QColor("#EF3340"))
    painter.setFont(QFont("Segoe UI", 24, QFont.Bold))
    painter.drawText(
        QRectF(inner.x() + 35, inner.y() + 25, inner.width() - 70, 100),
        Qt.AlignCenter,
        title or "Mots fléchés",
    )

    grid_rect = QRectF(
        inner.x() + 35,
        inner.y() + 150,
        inner.width() - 70,
        inner.height() - 210,
    )
    grid_widget.render_grid(painter, grid_rect, show_answers=False)

    writer.newPage()
    painter.fillRect(page, QColor("#FFFFFF"))
    painter.setPen(QColor("#15317E"))
    painter.setFont(QFont("Segoe UI", 24, QFont.Bold))
    painter.drawText(
        QRectF(page.x() + 100, page.y() + 70, page.width() - 200, 100),
        Qt.AlignCenter,
        f"{title or 'Mots fléchés'} - Corrigé",
    )
    solution_rect = QRectF(
        page.x() + 120,
        page.y() + 190,
        page.width() - 240,
        page.height() - 310,
    )
    grid_widget.render_grid(painter, solution_rect, show_answers=True)

    painter.end()
