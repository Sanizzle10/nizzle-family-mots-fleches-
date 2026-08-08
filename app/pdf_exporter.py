from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QMarginsF
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPageLayout,
    QPageSize,
    QPdfWriter,
)


def _draw_page(
    painter: QPainter,
    page: QRectF,
    title: str,
    grid_widget,
    show_answers: bool,
    illustration_path: str = "",
) -> None:
    painter.fillRect(page, QColor("#173783"))

    outer_margin = page.width() * 0.045
    red_frame = page.adjusted(
        outer_margin,
        outer_margin,
        -outer_margin,
        -outer_margin,
    )
    painter.fillRect(red_frame, QColor("#EF3340"))

    frame_width = page.width() * 0.018
    white_page = red_frame.adjusted(
        frame_width,
        frame_width,
        -frame_width,
        -frame_width,
    )
    painter.fillRect(white_page, QColor("#FFFFFF"))

    content_margin = page.width() * 0.025
    content = white_page.adjusted(
        content_margin,
        content_margin,
        -content_margin,
        -content_margin,
    )

    header_height = page.height() * 0.105
    header = QRectF(
        content.x(),
        content.y(),
        content.width(),
        header_height,
    )

    if illustration_path and Path(illustration_path).exists():
        image = QImage(illustration_path)
        if not image.isNull():
            image_rect = QRectF(
                header.x(),
                header.y(),
                header.width(),
                header.height(),
            )
            painter.drawImage(image_rect, image)
            painter.fillRect(image_rect, QColor(255, 255, 255, 125))

    painter.setPen(QColor("#EF3340"))
    title_font = QFont("Segoe UI")
    title_font.setBold(True)
    title_font.setPixelSize(max(28, int(page.width() * 0.027)))
    painter.setFont(title_font)
    painter.drawText(
        header,
        Qt.AlignCenter | Qt.TextWordWrap,
        title,
    )

    gap = page.height() * 0.012
    grid_top = header.bottom() + gap
    grid_height = content.bottom() - grid_top
    grid_rect = QRectF(
        content.x(),
        grid_top,
        content.width(),
        grid_height,
    )

    grid_widget.render_grid(
        painter,
        grid_rect,
        show_answers=show_answers,
    )


def export_grid_pdf(
    path: str,
    title: str,
    grid_widget,
    show_answers: bool,
    illustration_path: str = "",
) -> None:
    """Une seule page : la grille vide, ou sa solution."""
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(300)

    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError("Impossible de créer le document PDF.")

    page = QRectF(0, 0, writer.width(), writer.height())
    _draw_page(
        painter,
        page,
        title.strip() or "Mots fléchés",
        grid_widget,
        show_answers=show_answers,
        illustration_path=illustration_path,
    )
    painter.end()


def export_book_pdf(
    path: str,
    title: str,
    grid_widget,
    illustration_path: str = "",
) -> None:
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(300)

    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError("Impossible de créer le document PDF.")

    page = QRectF(0, 0, writer.width(), writer.height())
    puzzle_title = title.strip() or "Mots fléchés"

    _draw_page(
        painter,
        page,
        puzzle_title,
        grid_widget,
        show_answers=False,
        illustration_path=illustration_path,
    )

    writer.newPage()
    _draw_page(
        painter,
        page,
        f"{puzzle_title} — Corrigé",
        grid_widget,
        show_answers=True,
        illustration_path=illustration_path,
    )

    painter.end()
