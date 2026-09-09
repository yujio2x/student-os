import io
import json
import struct
import zlib
from types import SimpleNamespace

import pytest
from PIL import Image

from app.schedule_import import (
    IMAGE_TILE_HEIGHT,
    IMAGE_TILE_OVERLAP,
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_TILES,
    ScheduleImportError,
    ScheduleImportService,
)


def image_bytes(width=1080, height=1800, *, fmt="PNG", orientation=None):
    image = Image.new("RGB", (width, height), "white")
    output = io.BytesIO()
    exif = image.getexif()
    if orientation:
        exif[274] = orientation
    image.save(output, format=fmt, exif=exif)
    return output.getvalue()


def png_header_dimensions(width, height):
    data = bytearray(image_bytes(1, 1))
    data[16:24] = struct.pack(">II", width, height)
    data[29:33] = struct.pack(">I", zlib.crc32(data[12:29]) & 0xFFFFFFFF)
    return bytes(data)


def lesson(subject="Алгоритмизация", weekday=0, start="08:00", room="613 Б", end="08:50"):
    return {
        "weekday": weekday,
        "subject": subject,
        "starts_at": start,
        "ends_at": end,
        "room": room,
        "location": "Байзак центр",
        "teacher": "Балғабек А.А.",
        "lesson_type": "Л",
        "group_name": "",
        "notes": "",
    }


class Responses:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(output_text=json.dumps({"lessons": result}, ensure_ascii=False))


def service(results):
    importer = ScheduleImportService("", "fixture")
    importer.client = SimpleNamespace(responses=Responses(results))
    return importer


def test_normal_screenshot_still_uses_one_recognition_tile():
    importer = service([[lesson()]])
    rows = importer.extract("schedule.png", "image/png", image_bytes())
    assert len(rows) == 1
    assert len(importer.client.responses.calls) == 1


def test_tall_screenshot_tiles_with_overlap_and_imports_in_order():
    data = image_bytes(height=7000)
    prepared = ScheduleImportService._prepare_image(".png", data)
    assert len(prepared.tiles) == 3
    assert prepared.original_size == prepared.decoded_size == (1080, 7000)
    assert prepared.tiles[0].bottom - prepared.tiles[1].top == IMAGE_TILE_OVERLAP
    importer = service([
        [lesson("Позднее", 2, "12:00", end="12:50")],
        [],
        [lesson("Раньше", 0)],
    ])
    rows = importer.extract("schedule.png", "image/png", data)
    assert [row["subject"] for row in rows] == ["Раньше", "Позднее"]


def test_lesson_crossing_boundary_is_wholly_visible_in_an_overlapping_tile():
    prepared = ScheduleImportService._prepare_image(".png", image_bytes(height=5000))
    boundary = IMAGE_TILE_HEIGHT
    card_top, card_bottom = boundary - 100, boundary + 100
    assert any(tile.top <= card_top and tile.bottom >= card_bottom for tile in prepared.tiles)


def test_overlap_keeps_day_heading_with_a_boundary_lesson():
    prepared = ScheduleImportService._prepare_image(".png", image_bytes(height=5000))
    boundary = IMAGE_TILE_HEIGHT
    day_heading_top = boundary - 550
    lesson_bottom = boundary + 40
    assert any(
        tile.top <= day_heading_top and tile.bottom >= lesson_bottom
        for tile in prepared.tiles
    )


def test_overlap_duplicate_is_removed_but_different_room_survives():
    same = lesson()
    importer = service([[same], [dict(same)], [lesson(room="614 Б")]])
    rows = importer.extract("schedule.png", "image/png", image_bytes(height=7000))
    assert [row["room"] for row in rows] == ["613 Б", "614 Б"]


def test_very_long_valid_screenshot_stays_bounded():
    height = IMAGE_TILE_HEIGHT + (MAX_IMAGE_TILES - 1) * (IMAGE_TILE_HEIGHT - IMAGE_TILE_OVERLAP)
    ScheduleImportService._validate_geometry(800, height)
    assert len(ScheduleImportService._tile_ranges(height)) == MAX_IMAGE_TILES


@pytest.mark.parametrize("size", [(1000, MAX_IMAGE_HEIGHT + 1), (6000, 9000), (200, 12000)])
def test_absurd_geometry_is_rejected_before_recognition(size):
    importer = service([[lesson()]])
    with pytest.raises(ScheduleImportError, match="слишком большое|слишком вытянутое"):
        importer.extract("schedule.png", "image/png", png_header_dimensions(*size))
    assert importer.client.responses.calls == []


def test_rotated_image_is_normalized_before_tiling():
    prepared = ScheduleImportService._prepare_image(
        ".jpg", image_bytes(800, 1800, fmt="JPEG", orientation=6)
    )
    assert prepared.original_size == (800, 1800)
    assert prepared.decoded_size == (1800, 800)
    assert len(prepared.tiles) == 1


def test_invalid_tile_does_not_destroy_valid_lessons_from_another_tile():
    importer = service([ValueError("invalid synthetic tile"), [lesson()], []])
    rows = importer.extract("schedule.png", "image/png", image_bytes(height=5000))
    assert [row["subject"] for row in rows] == ["Алгоритмизация"]


def test_empty_recognition_and_parser_rejection_have_distinct_messages():
    with pytest.raises(ScheduleImportError, match="не удалось найти занятия"):
        service([[]]).extract("schedule.png", "image/png", image_bytes())
    with pytest.raises(ScheduleImportError, match="распознано частично"):
        service([[{"subject": "Без времени"}]]).extract(
            "schedule.png", "image/png", image_bytes()
        )
