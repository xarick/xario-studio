"""
Image-processing worker — invoked as a subprocess:

    python -m app.workers._imaging_run <operation> <input> <output> [args...]

Runs in its own process so rembg / onnxruntime never import into the web app
(same isolation rationale as _tts_batch). Currently supports background removal.
"""
import sys


def _bg_remove(input_path: str, output_path: str) -> None:
    from rembg import remove
    from PIL import Image
    with Image.open(input_path) as img:
        result = remove(img.convert("RGB"))   # RGBA with transparent background
    result.save(output_path)


_OPS = {
    "bg_remove": _bg_remove,
}


def main(operation: str, input_path: str, output_path: str, *extra) -> None:
    fn = _OPS.get(operation)
    if fn is None:
        sys.stderr.write(f"[imaging] unknown operation: {operation}\n")
        sys.exit(2)
    fn(input_path, output_path, *extra)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.stderr.write("usage: python -m app.workers._imaging_run <operation> <input> <output> [args...]\n")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3], *sys.argv[4:])
