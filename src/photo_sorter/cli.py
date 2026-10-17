from datetime import datetime
from pathlib import Path
import argparse
import shutil

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".webp",
}


def capture_time(path: Path) -> datetime:
    """Return EXIF capture time, falling back to file modification time."""
    try:
        with Image.open(path) as image:
            exif = image.getexif()

            # DateTimeOriginal, DateTimeDigitized, then general DateTime
            for tag in (36867, 36868, 306):
                value = exif.get(tag)
                if value:
                    try:
                        return datetime.strptime(
                            str(value), "%Y:%m:%d %H:%M:%S"
                        )
                    except ValueError:
                        pass
    except Exception:
        pass

    return datetime.fromtimestamp(path.stat().st_mtime)


def to_rgb(image: Image.Image) -> Image.Image:
    """Convert an image to RGB, compositing transparency onto white."""
    image = ImageOps.exif_transpose(image)

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    return image.convert("RGB")


def _find_images(source: Path) -> list[Path]:
    files = [
        path for path in source.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda path: (capture_time(path), path.name.lower()))


def _write_image(path: Path, destination: Path, convert: bool) -> None:
    if convert:
        with Image.open(path) as image:
            to_rgb(image).save(
                destination,
                format="JPEG",
                quality=95,
                optimize=True,
            )
    else:
        shutil.copy2(path, destination)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sort pictures by capture time, rename them, and "
            "optionally convert them to JPEG."
        )
    )
    parser.add_argument("source", type=Path, help="Folder containing the pictures")
    parser.add_argument("base", help="Filename base, for example vacation")
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination folder (default: a 'converted' folder inside the source)",
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        help="Convert pictures to JPEG (default: preserve original formats)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = (
        args.output.expanduser().resolve()
        if args.output
        else source / "converted"
    )

    if not source.is_dir():
        parser.error(f"Source folder does not exist: {source}")

    # Process files directly in the source folder, not in subfolders.
    files = _find_images(source)

    if not files:
        print("No supported images found.")
        return

    output.mkdir(parents=True, exist_ok=True)

    digits = max(1, len(str(len(files))))

    for number, path in enumerate(files, start=1):
        extension = ".jpg" if args.convert else path.suffix.lower()
        destination = output / f"{args.base}_{number:0{digits}d}{extension}"

        try:
            _write_image(path, destination, args.convert)
            print(f"{path.name} -> {destination.name}")
        except Exception as error:
            print(f"Skipped {path.name}: {error}")

    print(f"Finished. Output folder: {output}")


if __name__ == "__main__":
    main()
