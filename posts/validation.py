import io
import os
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MEDIA_TYPES = ('image', 'video', 'audio', 'document')

MEDIA_RULES = {
    'image': {
        'extensions': {'.jpg', '.jpeg', '.png', '.webp', '.gif'},
        'content_types': {
            'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
        },
        'limit_setting': 'NEXA_IMAGE_MAX_SIZE',
        'default_limit': 8 * 1024 * 1024,
    },
    'video': {
        'extensions': {'.mp4', '.webm', '.mov'},
        'content_types': {'video/mp4', 'video/webm', 'video/quicktime'},
        'limit_setting': 'NEXA_VIDEO_MAX_SIZE',
        'default_limit': 100 * 1024 * 1024,
    },
    'audio': {
        'extensions': {'.mp3', '.wav', '.m4a'},
        'content_types': {'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/mp4'},
        'limit_setting': 'NEXA_AUDIO_MAX_SIZE',
        'default_limit': 50 * 1024 * 1024,
    },
    'document': {
        'extensions': {'.pdf', '.docx', '.xlsx', '.txt', '.csv'},
        'content_types': {
            'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain', 'text/csv', 'application/csv', 'application/vnd.ms-excel',
        },
        'limit_setting': 'NEXA_DOCUMENT_MAX_SIZE',
        'default_limit': 25 * 1024 * 1024,
    },
}

DANGEROUS_EXTENSIONS = {
    '.apk', '.bat', '.bin', '.cmd', '.com', '.dll', '.dmg', '.exe', '.jar',
    '.js', '.msi', '.ps1', '.scr', '.sh', '.vbs', '.wsf',
}


def allowed_extensions(media_type):
    return MEDIA_RULES[media_type]['extensions']


def media_limit(media_type):
    rule = MEDIA_RULES[media_type]
    return getattr(settings, rule['limit_setting'], rule['default_limit'])


def _reset(uploaded):
    try:
        uploaded.seek(0)
    except (AttributeError, OSError):
        pass


def _read(uploaded, size=-1):
    _reset(uploaded)
    data = uploaded.read(size)
    _reset(uploaded)
    return data


def _is_iso_bmff(data):
    return len(data) >= 8 and data[4:8] == b'ftyp'


def _valid_document_content(extension, data, uploaded):
    if extension == '.pdf':
        return data.startswith(b'%PDF-')
    if extension in {'.docx', '.xlsx'}:
        if not data.startswith(b'PK'):
            return False
        try:
            with zipfile.ZipFile(uploaded) as archive:
                names = set(archive.namelist())
                if '[Content_Types].xml' not in names:
                    return False
                required_prefix = 'word/' if extension == '.docx' else 'xl/'
                return any(name.startswith(required_prefix) for name in names)
        except (OSError, zipfile.BadZipFile, ValueError):
            return False
    if extension in {'.txt', '.csv'}:
        if not data:
            return False
        if b'\x00' in data:
            return False
        try:
            _read(uploaded).decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return False
        return True
    return False


def _valid_media_content(media_type, extension, uploaded):
    data = _read(uploaded, 4096)
    if media_type == 'image':
        try:
            with Image.open(io.BytesIO(_read(uploaded))) as image:
                image.verify()
                detected = f'.{(image.format or "").lower()}'
        except (UnidentifiedImageError, OSError, ValueError):
            return False
        aliases = {'.jpg': {'.jpeg', '.jpg'}, '.jpeg': {'.jpeg', '.jpg'}}
        return extension in aliases.get(extension, {extension}) and detected in aliases.get(extension, {extension})
    if media_type == 'video':
        return data.startswith(b'\x1a\x45\xdf\xa3') or _is_iso_bmff(data)
    if media_type == 'audio':
        if extension == '.wav':
            return data[:4] == b'RIFF' and data[8:12] == b'WAVE'
        if extension == '.mp3':
            return data.startswith(b'ID3') or (
                len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
            )
        return _is_iso_bmff(data)
    return _valid_document_content(extension, data, uploaded)


def validate_media_upload(media_type, uploaded):
    """Validate an uploaded file using its extension and recognizable content."""
    if media_type not in MEDIA_RULES:
        raise ValidationError('Please select a supported media type.')
    if not uploaded:
        raise ValidationError(f'Please select a {media_type} file.')

    filename = os.path.basename(getattr(uploaded, 'name', '') or '')
    extension = Path(filename).suffix.lower()
    if extension in DANGEROUS_EXTENSIONS:
        raise ValidationError('Executable files are not allowed.')
    if extension not in allowed_extensions(media_type):
        readable = ', '.join(sorted(ext.lstrip('.').upper() for ext in allowed_extensions(media_type)))
        raise ValidationError(f'Unsupported file type. Accepted {media_type}s: {readable}.')

    size = getattr(uploaded, 'size', 0)
    if size <= 0:
        raise ValidationError('The selected file is empty.')
    if size > media_limit(media_type):
        limit_mb = media_limit(media_type) / (1024 * 1024)
        raise ValidationError(f'File is too large. {media_type.title()} files must be smaller than {limit_mb:g}MB.')

    content_type = (getattr(uploaded, 'content_type', '') or '').lower()
    if content_type in {
        'application/x-msdownload', 'application/x-msdos-program', 'application/x-sh',
        'text/javascript', 'application/javascript',
    }:
        raise ValidationError('Executable files are not allowed.')

    if not _valid_media_content(media_type, extension, uploaded):
        raise ValidationError('The selected file content does not match the selected media type.')
