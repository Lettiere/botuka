from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from apps.core.services.images import optimize_uploaded_image


def uploaded_image(fmt='JPEG', size=(3000, 2000), mode='RGB'):
    stream = BytesIO()
    Image.new(mode, size, (120, 80, 30, 120) if mode == 'RGBA' else (120, 80, 30)).save(stream, fmt)
    return SimpleUploadedFile(f'teste.{fmt.lower()}', stream.getvalue(), content_type=f'image/{fmt.lower()}')


class ImageOptimizationTests(SimpleTestCase):
    def test_jpeg_grande_vira_webp_redimensionado(self):
        original = uploaded_image()
        result = optimize_uploaded_image(original, policy='card')
        self.assertEqual(result.content_type, 'image/webp')
        self.assertLess(result.size, original.size)
        with Image.open(result) as image:
            self.assertLessEqual(max(image.size), 900)

    def test_png_transparente_preserva_alpha(self):
        result = optimize_uploaded_image(uploaded_image('PNG', (1200, 1600), 'RGBA'), policy='story')
        with Image.open(result) as image:
            self.assertEqual(image.mode, 'RGBA')

    def test_imagem_pequena_nao_sofre_upscale(self):
        result = optimize_uploaded_image(uploaded_image(size=(120, 80)), policy='hero')
        with Image.open(result) as image:
            self.assertEqual(image.size, (120, 80))

    def test_arquivo_invalido_e_rejeitado(self):
        invalid = SimpleUploadedFile('falso.jpg', b'not-image', content_type='image/jpeg')
        with self.assertRaises(ValidationError):
            optimize_uploaded_image(invalid)

    def test_upload_acima_do_limite_e_rejeitado(self):
        invalid = SimpleUploadedFile('grande.jpg', b'x' * (8 * 1024 * 1024 + 1), content_type='image/jpeg')
        with self.assertRaises(ValidationError):
            optimize_uploaded_image(invalid)
