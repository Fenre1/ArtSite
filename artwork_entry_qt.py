from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from PySide6.QtCore import QDateTime, Qt, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDateTimeEdit,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as error:
    raise SystemExit(
        "PySide6 is niet geinstalleerd. Installeer eerst: pip install PySide6"
    ) from error


ROOT = Path(__file__).parent
ARTWORKS_DIR = ROOT / "artworks"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
IMAGE_FILTER = "Afbeeldingen (*.jpg *.jpeg *.png *.webp *.gif *.avif)"
DEFAULT_PRICE_LABEL = "Prijs op aanvraag"


def slugify(value: str) -> str:
    cleaned = []
    previous_dash = False

    for character in value.lower().strip():
        if character.isalnum():
            cleaned.append(character)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True

    slug = "".join(cleaned).strip("-")
    return slug or "nieuw-kunstwerk"


def next_folder_name() -> str:
    highest = 0
    for folder in ARTWORKS_DIR.iterdir():
        if folder.is_dir() and folder.name.isdigit():
            highest = max(highest, int(folder.name))
    return f"{highest + 1:05d}"


def next_sort_order() -> int:
    highest = 0
    for metadata_file in ARTWORKS_DIR.glob("*/artwork.json"):
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        highest = max(highest, int(payload.get("sort_order", 0)))
    return highest + 1


def unique_destination_name(destination_folder: Path, source_name: str) -> str:
    candidate = Path(source_name).name
    stem = Path(candidate).stem
    suffix = Path(candidate).suffix
    counter = 2

    while (destination_folder / candidate).exists():
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1

    return candidate


class ImageDropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(260)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        dropped_files: list[Path] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                dropped_files.append(path)

        if dropped_files:
            self.files_dropped.emit(dropped_files)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


class ArtworkForm(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nieuw kunstwerk toevoegen")
        self.resize(1040, 680)

        self.image_paths: list[Path] = []
        self.main_image_path: Path | None = None
        self.slug_was_edited = False

        self.title_input = QLineEdit()
        self.slug_input = QLineEdit()
        self.type_combo = QComboBox()
        self.availability_combo = QComboBox()
        self.featured_checkbox = QCheckBox("Uitgelicht op de homepage")
        self.date_input = QDateTimeEdit(QDateTime.currentDateTime())
        self.price_on_request_checkbox = QCheckBox("Prijs op aanvraag")
        self.price_spin = QDoubleSpinBox()
        self.price_label_input = QLineEdit(DEFAULT_PRICE_LABEL)
        self.dimensions_input = QLineEdit()
        self.description_input = QTextEdit()
        self.image_list = ImageDropList()
        self.status_label = QLabel()
        self.folder_preview_label = QLabel()

        self.build_ui()
        self.connect_signals()
        self.refresh_preview()
        self.update_price_mode(self.price_on_request_checkbox.isChecked())
        self.update_image_list()

    def build_ui(self) -> None:
        self.title_input.setPlaceholderText("Bijvoorbeeld: Zomerlicht")
        self.slug_input.setPlaceholderText("Wordt automatisch ingevuld")

        self.type_combo.addItem("Schilderij", "painting")
        self.type_combo.addItem("Mozaiek", "mosaic")
        self.type_combo.addItem("Sculptuur", "sculpture")
        self.type_combo.addItem("Overig", "other")
        self.type_combo.setCurrentIndex(3)

        self.availability_combo.addItem("Beschikbaar", "available")
        self.availability_combo.addItem("Verkocht", "sold")

        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yyyy HH:mm")

        self.price_spin.setRange(0, 1000000)
        self.price_spin.setDecimals(2)
        self.price_spin.setSingleStep(10)
        self.price_spin.setPrefix("EUR ")

        self.description_input.setPlaceholderText("Korte beschrijving van het werk, materiaal of verhaal...")
        self.description_input.setMinimumHeight(160)

        form_layout = QFormLayout()
        form_layout.addRow("Titel", self.title_input)
        form_layout.addRow("Slug", self.slug_input)
        form_layout.addRow("Type", self.type_combo)
        form_layout.addRow("Status", self.availability_combo)
        form_layout.addRow("Datum en tijd", self.date_input)
        form_layout.addRow("Prijs op aanvraag", self.price_on_request_checkbox)
        form_layout.addRow("Prijs", self.price_spin)
        form_layout.addRow("Prijslabel", self.price_label_input)
        form_layout.addRow("Afmetingen", self.dimensions_input)
        form_layout.addRow("Uitgelicht", self.featured_checkbox)
        form_layout.addRow("Beschrijving", self.description_input)
        form_layout.addRow("Nieuwe map", self.folder_preview_label)

        form_group = QGroupBox("Kunstwerkgegevens")
        form_group.setLayout(form_layout)

        images_info = QLabel(
            "Sleep afbeeldingen hierheen, of kies bestanden via Verkenner. "
            "Selecteer daarna welke afbeelding de hoofdafbeelding moet zijn."
        )
        images_info.setWordWrap(True)

        add_button = QPushButton("Afbeeldingen kiezen...")
        remove_button = QPushButton("Verwijder selectie")
        main_button = QPushButton("Maak hoofdafbeelding")
        save_button = QPushButton("Kunstwerk opslaan")
        reset_button = QPushButton("Leeg formulier")

        self.add_button = add_button
        self.remove_button = remove_button
        self.main_button = main_button
        self.save_button = save_button
        self.reset_button = reset_button

        image_button_row = QHBoxLayout()
        image_button_row.addWidget(add_button)
        image_button_row.addWidget(remove_button)
        image_button_row.addWidget(main_button)
        image_button_row.addStretch(1)

        images_layout = QVBoxLayout()
        images_layout.addWidget(images_info)
        images_layout.addWidget(self.image_list)
        images_layout.addLayout(image_button_row)
        images_layout.addWidget(self.status_label)
        images_layout.addStretch(1)
        images_layout.addWidget(save_button)
        images_layout.addWidget(reset_button)

        images_group = QGroupBox("Afbeeldingen")
        images_group.setLayout(images_layout)

        root_layout = QGridLayout()
        root_layout.addWidget(form_group, 0, 0)
        root_layout.addWidget(images_group, 0, 1)
        root_layout.setColumnStretch(0, 7)
        root_layout.setColumnStretch(1, 5)
        self.setLayout(root_layout)

    def connect_signals(self) -> None:
        self.title_input.textChanged.connect(self.handle_title_changed)
        self.slug_input.textEdited.connect(self.handle_slug_edited)
        self.price_on_request_checkbox.toggled.connect(self.update_price_mode)
        self.add_button.clicked.connect(self.choose_images)
        self.remove_button.clicked.connect(self.remove_selected_images)
        self.main_button.clicked.connect(self.mark_selected_as_main)
        self.save_button.clicked.connect(self.save_artwork)
        self.reset_button.clicked.connect(self.reset_form)
        self.image_list.files_dropped.connect(self.add_images)
        self.image_list.itemDoubleClicked.connect(self.handle_item_double_click)

    def handle_title_changed(self, value: str) -> None:
        if not self.slug_was_edited:
            self.slug_input.setText(slugify(value))

    def handle_slug_edited(self) -> None:
        self.slug_was_edited = True

    def update_price_mode(self, checked: bool) -> None:
        self.price_spin.setEnabled(not checked)
        self.price_label_input.setEnabled(checked)

        if checked and not self.price_label_input.text().strip():
            self.price_label_input.setText(DEFAULT_PRICE_LABEL)

        if not checked and self.price_label_input.text().strip() == DEFAULT_PRICE_LABEL:
            self.price_label_input.clear()

    def choose_images(self) -> None:
        selected_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Kies een of meer afbeeldingen",
            str(Path.home()),
            IMAGE_FILTER,
        )
        if selected_files:
            self.add_images([Path(path) for path in selected_files])

    def add_images(self, paths: list[Path]) -> None:
        known_paths = {str(path).lower() for path in self.image_paths}

        for path in paths:
            normalized = Path(path)
            if not normalized.exists() or normalized.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            key = str(normalized).lower()
            if key in known_paths:
                continue
            self.image_paths.append(normalized)
            known_paths.add(key)

        if self.image_paths and self.main_image_path is None:
            self.main_image_path = self.image_paths[0]

        self.update_image_list()

    def update_image_list(self) -> None:
        self.image_list.clear()

        for path in self.image_paths:
            label = path.name
            if path == self.main_image_path:
                label = f"[Hoofd] {label}"
            item = QListWidgetItem(label)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.image_list.addItem(item)

        if not self.image_paths:
            self.status_label.setText("Nog geen afbeeldingen geselecteerd.")
        elif self.main_image_path is None:
            self.status_label.setText(f"{len(self.image_paths)} afbeelding(en) geselecteerd.")
        else:
            self.status_label.setText(
                f"{len(self.image_paths)} afbeelding(en) geselecteerd. Hoofdafbeelding: {self.main_image_path.name}"
            )

    def remove_selected_images(self) -> None:
        selected = self.image_list.selectedItems()
        if not selected:
            return

        selected_paths = {
            Path(item.data(Qt.ItemDataRole.UserRole))
            for item in selected
            if item.data(Qt.ItemDataRole.UserRole)
        }
        self.image_paths = [path for path in self.image_paths if path not in selected_paths]

        if self.main_image_path in selected_paths:
            self.main_image_path = self.image_paths[0] if self.image_paths else None

        self.update_image_list()

    def mark_selected_as_main(self) -> None:
        selected = self.image_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Geen selectie", "Selecteer eerst een afbeelding.")
            return

        main_path = Path(selected[0].data(Qt.ItemDataRole.UserRole))
        self.main_image_path = main_path
        self.update_image_list()

    def handle_item_double_click(self, item: QListWidgetItem) -> None:
        self.main_image_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.update_image_list()

    def refresh_preview(self) -> None:
        self.folder_preview_label.setText(
            f"{next_folder_name()} (sort_order {next_sort_order()})"
        )

    def validate(self) -> bool:
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Titel ontbreekt", "Vul eerst een titel in.")
            return False

        if not self.slug_input.text().strip():
            QMessageBox.warning(self, "Slug ontbreekt", "Vul eerst een slug in.")
            return False

        if not self.image_paths:
            QMessageBox.warning(self, "Geen afbeeldingen", "Voeg minstens een afbeelding toe.")
            return False

        if self.main_image_path is None:
            QMessageBox.warning(
                self,
                "Geen hoofdafbeelding",
                "Kies welke afbeelding de hoofdafbeelding moet zijn.",
            )
            return False

        if not self.price_on_request_checkbox.isChecked() and self.price_spin.value() <= 0:
            QMessageBox.warning(self, "Prijs ontbreekt", "Vul een prijs groter dan nul in.")
            return False

        return True

    def build_metadata(self, destination_folder: Path, copied_names: dict[Path, str]) -> dict[str, object]:
        title = self.title_input.text().strip()
        slug = slugify(self.slug_input.text().strip())
        price_on_request = self.price_on_request_checkbox.isChecked()
        price_label = self.price_label_input.text().strip() if price_on_request else ""
        main_image_name = copied_names[self.main_image_path]
        additional_images = [
            copied_names[path]
            for path in self.image_paths
            if path != self.main_image_path
        ]

        return {
            "title": title,
            "slug": slug,
            "type": self.type_combo.currentData(),
            "price": None if price_on_request else round(float(self.price_spin.value()), 2),
            "price_label": price_label or DEFAULT_PRICE_LABEL if price_on_request else "",
            "dimensions": self.dimensions_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "cover_image": main_image_name,
            "additional_images": additional_images,
            "featured": self.featured_checkbox.isChecked(),
            "availability": self.availability_combo.currentData(),
            "date_added": self.date_input.dateTime().toString(Qt.DateFormat.ISODate),
            "sort_order": next_sort_order(),
        }

    def save_artwork(self) -> None:
        if not self.validate():
            return

        destination_folder = ARTWORKS_DIR / next_folder_name()
        destination_folder.mkdir(parents=True, exist_ok=False)

        copied_names: dict[Path, str] = {}
        try:
            for path in self.image_paths:
                destination_name = unique_destination_name(destination_folder, path.name)
                shutil.copy2(path, destination_folder / destination_name)
                copied_names[path] = destination_name

            metadata = self.build_metadata(destination_folder, copied_names)
            metadata_path = destination_folder / "artwork.json"
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Opslaan mislukt",
                f"Het kunstwerk kon niet worden opgeslagen:\n\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Kunstwerk opgeslagen",
            f"Het nieuwe kunstwerk is opgeslagen in:\n{destination_folder}",
        )
        self.reset_form()

    def reset_form(self) -> None:
        self.title_input.clear()
        self.slug_input.clear()
        self.slug_was_edited = False
        self.type_combo.setCurrentIndex(3)
        self.availability_combo.setCurrentIndex(0)
        self.featured_checkbox.setChecked(False)
        self.date_input.setDateTime(QDateTime.currentDateTime())
        self.price_on_request_checkbox.setChecked(True)
        self.price_spin.setValue(0)
        self.price_label_input.setText(DEFAULT_PRICE_LABEL)
        self.dimensions_input.clear()
        self.description_input.clear()
        self.image_paths = []
        self.main_image_path = None
        self.refresh_preview()
        self.update_image_list()
        self.title_input.setFocus()


def main() -> int:
    if not ARTWORKS_DIR.exists():
        raise SystemExit(f"Map niet gevonden: {ARTWORKS_DIR}")

    app = QApplication(sys.argv)
    window = ArtworkForm()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
