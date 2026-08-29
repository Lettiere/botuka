from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXEL_COUNT = 40_000_000
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


@dataclass(frozen=True)
class ImagePolicy:
    max_width: int
    max_height: int
    quality: int = 82
    preserve_transparency: bool = True


POLICIES = {
    'avatar': ImagePolicy(480, 480, 82),
    'card': ImagePolicy(900, 900, 82),
    'content': ImagePolicy(1600, 1600, 84),
    'story': ImagePolicy(1080, 1920, 84),
    'hero': ImagePolicy(1920, 1200, 84),
}


def optimize_uploaded_image(upload, *, policy='content'):
    """Valida e devolve upload WebP otimizado, sem alterar arquivos já armazenados."""
    if not upload:
        return upload
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('Esta imagem é grande demais para ser processada. Escolha outra imagem.')
    config = POLICIES[policy]
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            source.verify()
        upload.seek(0)
        with Image.open(upload) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ValidationError('Envie uma imagem JPG, PNG ou WebP.')
            width, height = source.size
            if width * height > MAX_PIXEL_COUNT:
                raise ValidationError('Esta imagem possui dimensões excessivas e não pôde ser processada.')
            image = ImageOps.exif_transpose(source)
            has_alpha = config.preserve_transparency and (
                image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
            )
            image = image.convert('RGBA' if has_alpha else 'RGB')
            image.thumbnail((config.max_width, config.max_height), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(
                output, format='WEBP', quality=config.quality, method=6,
                lossless=has_alpha,
            )
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValidationError('Esta imagem não pôde ser processada. Escolha outra imagem.') from exc
    output.seek(0)
    filename = f'{Path(upload.name).stem}.webp'
    return InMemoryUploadedFile(
        output, getattr(upload, 'field_name', None), filename,
        'image/webp', len(output.getbuffer()), None,
    )
