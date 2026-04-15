import base64
import logging
import re
import zipfile
from io import BytesIO

logger = logging.getLogger(__name__)


def parse_file(file_storage):
    filename = file_storage.filename.lower()
    data = file_storage.read()
    logger.debug("Parsing file '%s' (%d bytes)", filename, len(data))
    if filename.endswith('.3mf'):
        return _parse_3mf(data)
    elif filename.endswith('.gcode') or filename.endswith('.gco'):
        return _parse_gcode(data.decode('utf-8', errors='replace'))
    logger.warning("Unsupported file format: '%s'", filename)
    return {'error': 'Unbekanntes Dateiformat'}


def _parse_3mf(data):
    result = {
        'printing_time_hours': None,
        'printing_time_minutes': None,
        'filament_weight_grams': None,
        'preview_image_base64': None,
        'filament_type': None,
    }
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except Exception as e:
        logger.error("Failed to open 3MF archive: %s", e)
        return result

    # Find thumbnail
    try:
        thumbnail_candidates = [
            'Metadata/plate_1.png',
            'Metadata/thumbnail.png',
            'Metadata/plate_1_small.png',
        ]
        for candidate in thumbnail_candidates:
            if candidate in zf.namelist():
                img_data = zf.read(candidate)
                result['preview_image_base64'] = base64.b64encode(img_data).decode('ascii')
                break
        if not result['preview_image_base64']:
            for name in sorted(zf.namelist()):
                if name.startswith('Metadata/') and name.lower().endswith('.png'):
                    img_data = zf.read(name)
                    result['preview_image_base64'] = base64.b64encode(img_data).decode('ascii')
                    break
    except Exception as e:
        logger.debug("Thumbnail extraction failed: %s", e)

    # Parse slice_info.config (Bambu Studio XML) first — most reliable
    if 'Metadata/slice_info.config' in zf.namelist():
        try:
            content = zf.read('Metadata/slice_info.config').decode('utf-8', errors='replace')
            _extract_bambu_xml(content, result)
        except Exception:
            pass

    # Parse all other metadata files
    for name in zf.namelist():
        try:
            if name.endswith(('.config', '.xml', '.gcode')):
                content = zf.read(name).decode('utf-8', errors='replace')
                _extract_metadata(content, result)
        except Exception:
            continue

    logger.debug("3MF parse result: time=%sh%sm, weight=%sg, type=%s, has_preview=%s",
                 result['printing_time_hours'], result['printing_time_minutes'],
                 result['filament_weight_grams'], result['filament_type'],
                 result['preview_image_base64'] is not None)
    return result


def _extract_bambu_xml(content, result):
    """Parse Bambu Studio slice_info.config XML format."""
    # Prediction (print time in seconds): <metadata key="prediction" value="33630"/>
    if result['printing_time_hours'] is None:
        m = re.search(r'<metadata\s+key="prediction"\s+value="(\d+)"', content)
        if m:
            total_sec = int(m.group(1))
            result['printing_time_hours'] = total_sec // 3600
            result['printing_time_minutes'] = (total_sec % 3600) // 60

    # Weight: <metadata key="weight" value="48.40"/>
    if result['filament_weight_grams'] is None:
        m = re.search(r'<metadata\s+key="weight"\s+value="([\d.]+)"', content)
        if m:
            result['filament_weight_grams'] = round(float(m.group(1)), 2)

    # Filament type: <filament ... type="PLA" .../> (but NOT volume_type)
    if result['filament_type'] is None:
        m = re.search(r'<filament\s[^>]*\stype="(\w+)"', content)
        if m:
            result['filament_type'] = m.group(1).upper()


def _extract_metadata(content, result):
    # Print time patterns (GCode comments and config files)
    time_patterns = [
        # BambuStudio GCode: ; total estimated time: 9h 20m 30s
        (r';\s*total estimated time:\s*(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?', 'hms'),
        # BambuStudio GCode: ; model printing time: 9h 12m 34s
        (r';\s*model printing time:\s*(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?', 'hms'),
        # PrusaSlicer: ; estimated printing time (normal mode) = 1h 23m 45s
        (r'estimated printing time.*?=\s*(?:(\d+)d\s*)?(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?', 'dhms'),
        # Generic: TIME: <seconds>
        (r';\s*TIME:\s*(\d+)', 'seconds'),
        # Config key=value: printing_time = <seconds>
        (r'printing_time\s*=\s*(\d+)', 'seconds'),
        (r'print_time\s*=\s*(\d+)', 'seconds'),
    ]
    if result['printing_time_hours'] is None:
        for pattern, fmt in time_patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                if fmt == 'hms':
                    result['printing_time_hours'] = int(m.group(1) or 0)
                    result['printing_time_minutes'] = int(m.group(2) or 0)
                elif fmt == 'dhms':
                    days = int(m.group(1) or 0)
                    hours = int(m.group(2) or 0)
                    minutes = int(m.group(3) or 0)
                    result['printing_time_hours'] = days * 24 + hours
                    result['printing_time_minutes'] = minutes
                elif fmt == 'seconds':
                    total_sec = int(m.group(1))
                    result['printing_time_hours'] = total_sec // 3600
                    result['printing_time_minutes'] = (total_sec % 3600) // 60
                break

    # Filament weight patterns
    weight_patterns = [
        r';\s*total filament weight \[g\]\s*:\s*([\d.]+)',
        r'total filament used \[g\]\s*=\s*([\d.]+)',
        r'filament used \[g\]\s*=\s*([\d.]+)',
        r'total filament weight\s*=\s*([\d.]+)',
        r'filament_weight\s*=\s*([\d.]+)',
        r'FilamentUsedG\s*=\s*([\d.]+)',
    ]
    if result['filament_weight_grams'] is None:
        for pattern in weight_patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                result['filament_weight_grams'] = round(float(m.group(1)), 2)
                break

    # Filament type patterns
    type_patterns = [
        r';\s*filament_type\s*=\s*(\w+)',
        r'filament_type\s*=\s*(\w+)',
        r'material_type\s*=\s*(\w+)',
        r'FilamentType\s*=\s*(\w+)',
    ]
    if result['filament_type'] is None:
        for pattern in type_patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                result['filament_type'] = m.group(1).upper()
                break


def _parse_gcode(content):
    result = {
        'printing_time_hours': None,
        'printing_time_minutes': None,
        'filament_weight_grams': None,
        'preview_image_base64': None,
        'filament_type': None,
    }

    # Extract thumbnail if present
    try:
        # Standard format: ; thumbnail begin WxH ...
        thumb_pattern = r';\s*thumbnail(?:\s+begin)?\s+\d+\s+\d+\s*\n((?:;[^\n]*\n)*?);\s*thumbnail end'
        thumb_matches = re.findall(thumb_pattern, content, re.IGNORECASE)
        if thumb_matches:
            raw = thumb_matches[-1]
            b64_data = ''.join(
                line.lstrip('; \t') for line in raw.strip().split('\n')
            )
            base64.b64decode(b64_data)
            result['preview_image_base64'] = b64_data
    except Exception:
        pass

    # Bambu Studio format: ; png begin ... ; png end
    if not result['preview_image_base64']:
        try:
            png_pattern = r';\s*png begin\s*\n((?:;[^\n]*\n)*?);\s*png end'
            png_matches = re.findall(png_pattern, content, re.IGNORECASE)
            if png_matches:
                raw = png_matches[-1]
                b64_data = ''.join(
                    line.lstrip('; \t') for line in raw.strip().split('\n')
                )
                base64.b64decode(b64_data)
                result['preview_image_base64'] = b64_data
        except Exception:
            pass

    _extract_metadata(content, result)
    logger.debug("GCode parse result: time=%sh%sm, weight=%sg, type=%s, has_preview=%s",
                 result['printing_time_hours'], result['printing_time_minutes'],
                 result['filament_weight_grams'], result['filament_type'],
                 result['preview_image_base64'] is not None)
    return result
