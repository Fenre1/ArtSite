from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from PySide6.QtCore import QDateTime, Qt, Signal
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDateTimeEdit,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
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

TYPE_OPTIONS = [
    ("Schilderij", "painting"),
    ("Mozaiek", "mosaic"),
    ("Sculptuur", "sculpture"),
    ("Overig", "other"),
]
AVAILABILITY_OPTIONS = [
    ("Beschikbaar", "available"),
    ("Verkocht", "sold"),
]


@dataclass
class ArtworkRecord:
    folder: Path
    title: str
    slug: str
    type_key: str
    availability_key: str
    featured: bool
    date_added: datetime
    price: float | None
    price_label: str
    dimensions: str
    description: str
    cover_image: str
    additional_images: list[str]
    sort_order: int


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


def discover_folder_images(folder: Path) -> list[str]:
    return sorted(
        [
            item.name
            for item in folder.iterdir()
            if item.is_file()
            and item.suffix.lower() in IMAGE_SUFFIXES
            and item.name.lower() != "artwork.json"
        ],
        key=str.lower,
    )


def parse_datetime(value: object, fallback: datetime | None = None) -> datetime:
    raw_value = str(value or "").strip()
    if raw_value:
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError:
            pass

    if fallback is not None:
        return fallback

    return datetime.now().replace(second=0, microsecond=0)


def format_datetime_for_list(value: datetime) -> str:
    return value.strftime("%d-%m-%Y %H:%M")


def to_qdatetime(value: datetime) -> QDateTime:
    qt_value = QDateTime.fromString(
        value.isoformat(timespec="seconds"),
        Qt.DateFormat.ISODate,
    )
    return qt_value if qt_value.isValid() else QDateTime.currentDateTime()


def combo_index_for_data(combo: QComboBox, value: str, fallback_index: int) -> int:
    index = combo.findData(value)
    return index if index >= 0 else fallback_index


def parse_price(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    return float(text)


def load_artwork_record(folder: Path) -> ArtworkRecord:
    metadata_path = folder / "artwork.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    folder_modified = datetime.fromtimestamp(folder.stat().st_mtime)
    available_images = discover_folder_images(folder)

    title = str(payload.get("title") or f"Zonder titel {folder.name}").strip()
    slug = slugify(str(payload.get("slug") or title or folder.name))
    type_key = str(payload.get("type") or "other").strip().lower() or "other"
    availability_key = (
        str(payload.get("availability") or "available").strip().lower() or "available"
    )
    if type_key not in {value for _, value in TYPE_OPTIONS}:
        type_key = "other"
    if availability_key not in {value for _, value in AVAILABILITY_OPTIONS}:
        availability_key = "available"

    cover_image = str(payload.get("cover_image") or "").strip()
    if not cover_image and available_images:
        cover_image = available_images[0]

    if payload.get("additional_images") is None:
        additional_images = [name for name in available_images if name != cover_image]
    else:
        additional_images = [
            str(image_name).strip()
            for image_name in payload.get("additional_images", [])
            if str(image_name).strip()
        ]

    try:
        price = parse_price(payload.get("price"))
    except (TypeError, ValueError):
        price = None

    try:
        sort_order = int(payload.get("sort_order", 0))
    except (TypeError, ValueError):
        sort_order = 0

    return ArtworkRecord(
        folder=folder,
        title=title,
        slug=slug,
        type_key=type_key,
        availability_key=availability_key,
        featured=bool(payload.get("featured", False)),
        date_added=parse_datetime(payload.get("date_added"), folder_modified),
        price=price,
        price_label=str(payload.get("price_label") or "").strip(),
        dimensions=str(payload.get("dimensions") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        cover_image=cover_image,
        additional_images=additional_images,
        sort_order=sort_order,
    )


def load_artwork_records() -> tuple[list[ArtworkRecord], list[str]]:
    records: list[ArtworkRecord] = []
    errors: list[str] = []

    for folder in sorted(ARTWORKS_DIR.iterdir(), key=lambda item: item.name.lower(), reverse=True):
        if not folder.is_dir():
            continue

        metadata_path = folder / "artwork.json"
        if not metadata_path.exists():
            errors.append(f"{folder.name}: artwork.json ontbreekt.")
            continue

        try:
            records.append(load_artwork_record(folder))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            errors.append(f"{folder.name}: {error}")

    return records, errors


def find_slug_conflict(slug: str, current_folder: Path | None = None) -> str | None:
    normalized_slug = slugify(slug)

    for folder in ARTWORKS_DIR.iterdir():
        if not folder.is_dir() or folder == current_folder:
            continue

        metadata_path = folder / "artwork.json"
        if not metadata_path.exists():
            continue

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        other_slug = slugify(str(payload.get("slug") or payload.get("title") or folder.name))
        if other_slug == normalized_slug:
            return folder.name

    return None


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


class ImagePreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._original_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(280)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel {"
            "border: 1px solid #bcbcbc;"
            "border-radius: 6px;"
            "background: #fafafa;"
            "padding: 12px;"
            "}"
        )
        self.show_placeholder("Nog geen afbeelding geselecteerd.")

    def show_placeholder(self, message: str) -> None:
        self._original_pixmap = None
        self.clear()
        self.setText(message)

    def show_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.show_placeholder(f"Voorvertoning niet beschikbaar voor:\n{path.name}")
            return

        self._original_pixmap = pixmap
        self.setText("")
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._original_pixmap is None:
            return

        scaled = self._original_pixmap.scaled(
            max(self.width() - 24, 1),
            max(self.height() - 24, 1),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class ArtworkEditor(QWidget):
    artwork_saved = Signal(str)

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.image_paths: list[Path] = []
        self.main_image_path: Path | None = None
        self.preview_image_path: Path | None = None
        self.slug_was_edited = False
        self.current_folder: Path | None = None
        self.current_sort_order: int | None = None

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
        self.preview_label = ImagePreviewLabel()
        self.status_label = QLabel()
        self.folder_preview_label = QLabel()

        self.build_ui()
        self.connect_signals()
        self.reset_form()

    @property
    def is_edit_mode(self) -> bool:
        return self.mode == "edit"

    def build_ui(self) -> None:
        self.title_input.setPlaceholderText("Bijvoorbeeld: Zomerlicht")
        self.slug_input.setPlaceholderText("Wordt automatisch ingevuld")

        for label, value in TYPE_OPTIONS:
            self.type_combo.addItem(label, value)
        self.type_combo.setCurrentIndex(combo_index_for_data(self.type_combo, "other", 0))

        for label, value in AVAILABILITY_OPTIONS:
            self.availability_combo.addItem(label, value)

        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yyyy HH:mm")

        self.price_spin.setRange(0, 1000000)
        self.price_spin.setDecimals(2)
        self.price_spin.setSingleStep(10)
        self.price_spin.setPrefix("EUR ")

        self.description_input.setPlaceholderText(
            "Korte beschrijving van het werk, materiaal of verhaal..."
        )
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
        form_layout.addRow("Map", self.folder_preview_label)

        form_group = QGroupBox("Kunstwerkgegevens")
        form_group.setLayout(form_layout)

        images_info = QLabel(
            "Sleep afbeeldingen hierheen, of kies bestanden via Verkenner. "
            "Klik op een afbeelding om die groot te bekijken en selecteer daarna "
            "welke afbeelding de hoofdafbeelding moet zijn."
        )
        images_info.setWordWrap(True)

        add_button = QPushButton("Afbeeldingen kiezen...")
        remove_button = QPushButton("Verwijder selectie")
        main_button = QPushButton("Maak hoofdafbeelding")
        save_button = QPushButton(
            "Wijzigingen opslaan" if self.is_edit_mode else "Kunstwerk opslaan"
        )
        reset_button = QPushButton(
            "Herlaad kunstwerk" if self.is_edit_mode else "Leeg formulier"
        )

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
        images_layout.addWidget(self.preview_label)
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
        self.image_list.currentItemChanged.connect(self.handle_current_image_changed)
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
        start_dir = str(self.current_folder or Path.home())
        selected_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Kies een of meer afbeeldingen",
            start_dir,
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
            self.preview_image_path = self.main_image_path

        self.update_image_list()

    def update_image_list(self) -> None:
        self.image_list.clear()

        for path in self.image_paths:
            tags: list[str] = []
            if path == self.main_image_path:
                tags.append("Hoofd")
            if self.current_folder and path.parent != self.current_folder:
                tags.append("Nieuw")
            if not path.exists():
                tags.append("Ontbreekt")

            label = path.name
            if tags:
                label = f"[{' / '.join(tags)}] {label}"

            item = QListWidgetItem(label)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.image_list.addItem(item)

        if self.preview_image_path not in self.image_paths:
            self.preview_image_path = self.main_image_path or (self.image_paths[0] if self.image_paths else None)

        self.sync_list_selection_to_preview()
        self.update_preview()

        if not self.image_paths:
            self.status_label.setText("Nog geen afbeeldingen geselecteerd.")
        elif self.main_image_path is None:
            self.status_label.setText(f"{len(self.image_paths)} afbeelding(en) geselecteerd.")
        else:
            self.status_label.setText(
                f"{len(self.image_paths)} afbeelding(en) geselecteerd. "
                f"Hoofdafbeelding: {self.main_image_path.name}"
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

        self.main_image_path = Path(selected[0].data(Qt.ItemDataRole.UserRole))
        self.preview_image_path = self.main_image_path
        self.update_image_list()

    def handle_item_double_click(self, item: QListWidgetItem) -> None:
        self.main_image_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.preview_image_path = self.main_image_path
        self.update_image_list()

    def handle_current_image_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous

        if current is None:
            self.preview_image_path = self.main_image_path
        else:
            self.preview_image_path = Path(current.data(Qt.ItemDataRole.UserRole))

        self.update_preview()

    def sync_list_selection_to_preview(self) -> None:
        if self.preview_image_path is None:
            self.image_list.clearSelection()
            return

        for row in range(self.image_list.count()):
            item = self.image_list.item(row)
            if item is None:
                continue
            if Path(item.data(Qt.ItemDataRole.UserRole)) == self.preview_image_path:
                self.image_list.setCurrentItem(item)
                return

    def update_preview(self) -> None:
        if self.preview_image_path is None:
            self.preview_label.show_placeholder("Nog geen afbeelding geselecteerd.")
            return

        if not self.preview_image_path.exists():
            self.preview_label.show_placeholder(
                f"Afbeelding niet gevonden:\n{self.preview_image_path.name}"
            )
            return

        self.preview_label.show_image(self.preview_image_path)

    def refresh_folder_info(self) -> None:
        if self.is_edit_mode:
            if self.current_folder is None:
                self.folder_preview_label.setText("Selecteer links een kunstwerk.")
            else:
                self.folder_preview_label.setText(
                    f"{self.current_folder.name} (sort_order {self.current_sort_order or 0})"
                )
            return

        self.folder_preview_label.setText(
            f"{next_folder_name()} (sort_order {next_sort_order()})"
        )

    def validate(self) -> bool:
        if self.is_edit_mode and self.current_folder is None:
            QMessageBox.warning(
                self,
                "Geen kunstwerk geselecteerd",
                "Selecteer eerst een bestaand kunstwerk.",
            )
            return False

        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Titel ontbreekt", "Vul eerst een titel in.")
            return False

        if not self.slug_input.text().strip():
            QMessageBox.warning(self, "Slug ontbreekt", "Vul eerst een slug in.")
            return False

        slug_conflict = find_slug_conflict(self.slug_input.text().strip(), self.current_folder)
        if slug_conflict is not None:
            QMessageBox.warning(
                self,
                "Slug bestaat al",
                f"De slug bestaat al in map {slug_conflict}. Kies een unieke slug.",
            )
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

        missing_paths = [path.name for path in self.image_paths if not path.exists()]
        if missing_paths:
            QMessageBox.warning(
                self,
                "Afbeelding ontbreekt",
                "De volgende afbeeldingen zijn niet gevonden:\n\n"
                + "\n".join(f"- {name}" for name in missing_paths),
            )
            return False

        if not self.price_on_request_checkbox.isChecked() and self.price_spin.value() <= 0:
            QMessageBox.warning(self, "Prijs ontbreekt", "Vul een prijs groter dan nul in.")
            return False

        return True

    def build_metadata(
        self,
        copied_names: dict[Path, str],
        sort_order: int,
    ) -> dict[str, object]:
        price_on_request = self.price_on_request_checkbox.isChecked()
        price_label = self.price_label_input.text().strip() if price_on_request else ""
        main_image_name = copied_names[self.main_image_path]
        additional_images = [
            copied_names[path]
            for path in self.image_paths
            if path != self.main_image_path
        ]

        return {
            "title": self.title_input.text().strip(),
            "slug": slugify(self.slug_input.text().strip()),
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
            "sort_order": sort_order,
        }

    def copy_images_to_folder(self, destination_folder: Path) -> dict[Path, str]:
        copied_names: dict[Path, str] = {}

        for path in self.image_paths:
            if self.is_edit_mode and path.parent == destination_folder and path.exists():
                copied_names[path] = path.name
                continue

            destination_name = unique_destination_name(destination_folder, path.name)
            shutil.copy2(path, destination_folder / destination_name)
            copied_names[path] = destination_name

        return copied_names

    def save_artwork(self) -> None:
        if self.is_edit_mode:
            self.save_existing_artwork()
            return

        self.save_new_artwork()

    def save_new_artwork(self) -> None:
        if not self.validate():
            return

        destination_folder = ARTWORKS_DIR / next_folder_name()
        destination_folder.mkdir(parents=True, exist_ok=False)

        try:
            copied_names = self.copy_images_to_folder(destination_folder)
            metadata = self.build_metadata(copied_names, next_sort_order())
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
        self.artwork_saved.emit(destination_folder.name)
        self.reset_form()

    def save_existing_artwork(self) -> None:
        if not self.validate() or self.current_folder is None:
            return

        try:
            copied_names = self.copy_images_to_folder(self.current_folder)
            metadata = self.build_metadata(
                copied_names,
                self.current_sort_order if self.current_sort_order is not None else next_sort_order(),
            )
            metadata_path = self.current_folder / "artwork.json"
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Opslaan mislukt",
                f"De wijzigingen konden niet worden opgeslagen:\n\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Wijzigingen opgeslagen",
            f"Het kunstwerk in map {self.current_folder.name} is bijgewerkt.",
        )
        saved_folder = self.current_folder.name
        self.load_artwork_from_folder(self.current_folder)
        self.artwork_saved.emit(saved_folder)

    def clear_form_fields(self) -> None:
        self.title_input.clear()
        self.slug_input.clear()
        self.type_combo.setCurrentIndex(combo_index_for_data(self.type_combo, "other", 0))
        self.availability_combo.setCurrentIndex(
            combo_index_for_data(self.availability_combo, "available", 0)
        )
        self.featured_checkbox.setChecked(False)
        self.date_input.setDateTime(QDateTime.currentDateTime())
        self.price_on_request_checkbox.setChecked(True)
        self.price_spin.setValue(0)
        self.price_label_input.setText(DEFAULT_PRICE_LABEL)
        self.dimensions_input.clear()
        self.description_input.clear()
        self.image_paths = []
        self.main_image_path = None
        self.preview_image_path = None
        self.update_image_list()

    def clear_loaded_artwork(self) -> None:
        self.current_folder = None
        self.current_sort_order = None
        self.slug_was_edited = True
        self.clear_form_fields()
        self.status_label.setText("Selecteer links een kunstwerk om te bewerken.")
        self.refresh_folder_info()

    def load_record(self, record: ArtworkRecord) -> None:
        ordered_paths: list[Path] = []
        if record.cover_image:
            ordered_paths.append(record.folder / record.cover_image)
        for image_name in record.additional_images:
            candidate = record.folder / image_name
            if candidate not in ordered_paths:
                ordered_paths.append(candidate)

        self.current_folder = record.folder
        self.current_sort_order = record.sort_order
        self.clear_form_fields()

        self.title_input.setText(record.title)
        self.slug_input.setText(record.slug)
        self.type_combo.setCurrentIndex(
            combo_index_for_data(self.type_combo, record.type_key, 0)
        )
        self.availability_combo.setCurrentIndex(
            combo_index_for_data(self.availability_combo, record.availability_key, 0)
        )
        self.featured_checkbox.setChecked(record.featured)
        self.date_input.setDateTime(to_qdatetime(record.date_added))
        self.price_on_request_checkbox.setChecked(record.price is None)
        self.price_spin.setValue(0 if record.price is None else record.price)
        self.price_label_input.setText(
            record.price_label or DEFAULT_PRICE_LABEL if record.price is None else record.price_label
        )
        self.dimensions_input.setText(record.dimensions)
        self.description_input.setPlainText(record.description)
        self.image_paths = ordered_paths
        self.main_image_path = ordered_paths[0] if ordered_paths else None
        self.preview_image_path = self.main_image_path
        self.slug_was_edited = True
        self.refresh_folder_info()
        self.update_image_list()
        self.title_input.setFocus()

    def load_artwork_from_folder(self, folder: Path) -> None:
        self.load_record(load_artwork_record(folder))

    def reset_form(self) -> None:
        if self.is_edit_mode:
            if self.current_folder is None:
                self.clear_loaded_artwork()
            else:
                self.load_artwork_from_folder(self.current_folder)
            return

        self.current_folder = None
        self.current_sort_order = None
        self.slug_was_edited = False
        self.clear_form_fields()
        self.refresh_folder_info()
        self.title_input.setFocus()


class ArtworkLibraryTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.records_by_folder: dict[str, ArtworkRecord] = {}
        self.refreshing_table = False

        self.table = QTableWidget(0, 3)
        self.status_label = QLabel()
        self.editor = ArtworkEditor(mode="edit")
        self.refresh_button = QPushButton("Vernieuwen")

        self.build_ui()
        self.connect_signals()
        self.refresh_artwork_list()

    def build_ui(self) -> None:
        self.table.setHorizontalHeaderLabels(["Map", "Titel", "Datum toegevoegd"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )

        list_intro = QLabel(
            "Selecteer een bestaand kunstwerk om alle gegevens en afbeeldingen te laden."
        )
        list_intro.setWordWrap(True)

        list_layout = QVBoxLayout()
        list_layout.addWidget(list_intro)
        list_layout.addWidget(self.table)
        list_layout.addWidget(self.status_label)
        list_layout.addWidget(self.refresh_button)

        list_group = QGroupBox("Bestaande kunstwerken")
        list_group.setLayout(list_layout)

        root_layout = QGridLayout()
        root_layout.addWidget(list_group, 0, 0)
        root_layout.addWidget(self.editor, 0, 1)
        root_layout.setColumnStretch(0, 4)
        root_layout.setColumnStretch(1, 8)
        self.setLayout(root_layout)

        self.editor.setEnabled(False)

    def connect_signals(self) -> None:
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.refresh_button.clicked.connect(self.refresh_artwork_list)
        self.editor.artwork_saved.connect(self.handle_artwork_saved)

    def selected_folder_name(self) -> str | None:
        current_row = self.table.currentRow()
        if current_row < 0:
            return None

        item = self.table.item(current_row, 0)
        if item is None:
            return None

        return item.text().strip() or None

    def refresh_artwork_list(self, selected_folder: str | None = None) -> None:
        target_folder = selected_folder or self.selected_folder_name()
        records, errors = load_artwork_records()
        self.records_by_folder = {record.folder.name: record for record in records}

        self.refreshing_table = True
        self.table.setRowCount(0)
        for row, record in enumerate(records):
            self.table.insertRow(row)

            folder_item = QTableWidgetItem(record.folder.name)
            title_item = QTableWidgetItem(record.title)
            date_item = QTableWidgetItem(format_datetime_for_list(record.date_added))
            date_item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )

            self.table.setItem(row, 0, folder_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, date_item)
        self.refreshing_table = False

        if not records:
            self.status_label.setText("Nog geen kunstwerken gevonden.")
            self.status_label.setToolTip("\n".join(errors))
            self.editor.clear_loaded_artwork()
            self.editor.setEnabled(False)
            return

        message = f"{len(records)} kunstwerk(en) geladen."
        if errors:
            message += f" {len(errors)} map(pen) overgeslagen."
        self.status_label.setText(message)
        self.status_label.setToolTip("\n".join(errors))

        if target_folder and target_folder in self.records_by_folder:
            self.select_folder(target_folder)
        else:
            self.select_folder(records[0].folder.name)

    def select_folder(self, folder_name: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == folder_name:
                self.table.setCurrentCell(row, 0)
                return

    def handle_selection_changed(self) -> None:
        if self.refreshing_table:
            return

        folder_name = self.selected_folder_name()
        if folder_name is None:
            self.editor.clear_loaded_artwork()
            self.editor.setEnabled(False)
            return

        record = self.records_by_folder.get(folder_name)
        if record is None:
            return

        self.editor.setEnabled(True)
        self.editor.load_record(record)

    def handle_artwork_saved(self, folder_name: str) -> None:
        self.refresh_artwork_list(selected_folder=folder_name)


class ArtworkManager(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scheeper Art beheer")
        self.resize(1320, 820)

        self.new_editor = ArtworkEditor(mode="new")
        self.library_tab = ArtworkLibraryTab()

        tabs = QTabWidget()
        tabs.addTab(self.new_editor, "Nieuw kunstwerk")
        tabs.addTab(self.library_tab, "Bestaande kunstwerken")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

        self.new_editor.artwork_saved.connect(self.handle_new_artwork_saved)

    def handle_new_artwork_saved(self, folder_name: str) -> None:
        self.library_tab.refresh_artwork_list(selected_folder=folder_name)


def main() -> int:
    if not ARTWORKS_DIR.exists():
        raise SystemExit(f"Map niet gevonden: {ARTWORKS_DIR}")

    app = QApplication(sys.argv)
    window = ArtworkManager()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
