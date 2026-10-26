"""Validacion, compresion y almacenamiento de imagenes subidas al admin."""

import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

from shared.protocol import MAX_PAYLOAD_BYTES


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_SIZE = (1920, 1080)

load_dotenv()


def directorio_almacenamiento() -> Path:
    """Devuelve el almacenamiento configurado o admin/storage por defecto."""
    valor = os.getenv("HERMES_STORAGE_DIR", "").strip() or "admin/storage"
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = Path(__file__).resolve().parents[2] / ruta
    return ruta


def preparar_imagen(datos: bytes) -> bytes:
    """Valida, orienta, reduce y codifica una imagen como JPEG comprimido."""
    if len(datos) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen supera el máximo permitido de 20 MB")
    if not datos:
        raise ValueError("El archivo de imagen está vacío")

    try:
        with Image.open(BytesIO(datos)) as imagen:
            ancho, alto = imagen.size
            if ancho * alto > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"La imagen excede el límite de {MAX_IMAGE_PIXELS} píxeles "
                    f"({ancho}x{alto})"
                )
            imagen.verify()

        with Image.open(BytesIO(datos)) as original:
            imagen = ImageOps.exif_transpose(original)
            tiene_transparencia = (
                imagen.mode in ("RGBA", "LA")
                or (imagen.mode == "P" and "transparency" in imagen.info)
            )
            if tiene_transparencia:
                rgba = imagen.convert("RGBA")
                aplanada = Image.new("RGB", rgba.size, "white")
                aplanada.paste(rgba, mask=rgba.getchannel("A"))
                imagen = aplanada
            else:
                imagen = imagen.convert("RGB")

            imagen.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
            salida = BytesIO()
            imagen.save(salida, format="JPEG", quality=85)
            comprimida = salida.getvalue()
    except ValueError:
        raise
    except Image.DecompressionBombError as exc:
        raise ValueError(
            f"La imagen excede el límite de {MAX_IMAGE_PIXELS} píxeles"
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("El archivo recibido no contiene una imagen válida") from exc

    if len(comprimida) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"La imagen comprimida excede el límite TCP de {MAX_PAYLOAD_BYTES} bytes"
        )
    return comprimida


def guardar_imagen_comprimida(datos: bytes, image_id: str) -> Path:
    """Guarda bytes JPEG bajo un identificador generado por el servidor."""
    carpeta = directorio_almacenamiento()
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{image_id}.jpg"
    creado = False
    try:
        with ruta.open("xb") as archivo:
            creado = True
            escritos = archivo.write(datos)
            if escritos != len(datos):
                raise OSError(
                    f"Escritura incompleta: {escritos} de {len(datos)} bytes"
                )
            archivo.flush()
            os.fsync(archivo.fileno())
    except Exception:
        if creado:
            try:
                ruta.unlink()
            except OSError:
                pass
        raise
    return ruta


def buscar_imagen_comprimida(image_id: str) -> Path | None:
    """Resuelve exclusivamente IDs UUID hexadecimales generados por el admin."""
    if (
        len(image_id) != 32
        or any(caracter not in "0123456789abcdef" for caracter in image_id)
    ):
        return None
    ruta = directorio_almacenamiento() / f"{image_id}.jpg"
    return ruta if ruta.is_file() else None
