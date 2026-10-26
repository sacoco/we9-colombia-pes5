"""Build the complete WE9 Colombia -> PES5 PC patch package from the original game files.

The package is copy-and-replace: rebuilt dat/*.afs files plus the Colombian option file.

Usage:
  python -I tools/build_patch.py --xbox <WE9 Xbox folder> --pc-dat <original PES5 dat folder>
                                 --option-file <Colombian option file> --out <dist folder>
"""
import argparse
import csv
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).parent
sys.path.insert(0, str(TOOLS))
from afs_rebuild import rebuild, verify  # noqa: E402
from pes_unobf import is_protected, reprotect, tamper_ok  # noqa: E402

OPTION_FILE_DIR = Path("Documentos/KONAMI/Pro Evolution Soccer 5/save/folder1")
README = """WE9 Colombia 2006 para PES5 PC
==============================

Parche colombiano de Winning Eleven 9 (Xbox) portado a Pro Evolution Soccer 5 de PC.
Incluye musica, escudos, kits, miniaturas, menus, Liga Colombiana / Copa mustang II,
nombres de equipos, jugadores, estadisticas y plantillas.

Instalacion (sobre una instalacion limpia de PES5, sin KitServer):
  1. Copia los 3 archivos de PES5/dat/ dentro de la carpeta dat del juego y reemplaza.
  2. Copia KONAMI-WIN32PES5OPT dentro de
       Documentos\\KONAMI\\Pro Evolution Soccer 5\\save\\folder1\\
     (en Linux/Raspberry Pi con Wine: <WINEPREFIX>/drive_c/users/<usuario>/Documents/...)
     Si ya habia uno, hace una copia antes: ahi se guardan tus opciones y datos editados.
  3. Abri el juego.

Para volver a PES5 original: restaura los 3 .afs originales y tu option file anterior.
CHECKSUMS.sha256 permite verificar que los archivos se copiaron bien.

Uso personal: contiene contenido del juego. No publicar.
"""

TEXT_REPLACEMENTS = {
    "Serie A": "Liga Italiana",
    "Eredivisie": "Liga Colombiana",
    "Copa de Holanda": "Copa mustang II",
}
TEXT_TABLES = [2, 148]
SOUND_EXCLUDE_0TEXT = [9007, 9011, 9023, 9077, 9080, 9081, 9084, 9087, 9088, 9970, 9971]


def run(*args):
    print("  $ " + " ".join(Path(a).name if i == 1 else str(a) for i, a in enumerate(args)))
    subprocess.run([sys.executable, "-I", *map(str, args)], check=True)


def safe_pc_indices(csv_path):
    return [int(r["pc_index"]) for r in csv.DictReader(open(csv_path, encoding="utf-8")) if r["kind"] == "safe"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xbox", required=True, type=Path)
    ap.add_argument("--pc-dat", required=True, type=Path)
    ap.add_argument("--option-file", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    work = a.out.parent / (a.out.name + "-work")
    reports, overrides = work / "reports", work / "overrides"
    for p in (work, a.out):
        if p.exists():
            shutil.rmtree(p)
    reports.mkdir(parents=True)
    overrides.mkdir(parents=True)

    print("[1/6] Comparando y alineando archivos AFS")
    run(TOOLS / "afs_compare.py", a.xbox, a.pc_dat, reports, "0_sound.afs")
    for name in ("0_text", "s_text"):
        x, p = a.xbox / f"{name}.afs", a.pc_dat / f"{name}.afs"
        run(TOOLS / "afs_align.py", x, p, reports / f"{name}.align.csv")
        run(TOOLS / "tex_diff.py", x, p, reports / f"{name}.align.csv", reports / f"{name}.classified.csv")
    (reports / "0_text.exclude.txt").write_text(" ".join(map(str, SOUND_EXCLUDE_0TEXT)))
    run(TOOLS / "select_safe.py", a.xbox / "0_text.afs", a.pc_dat / "0_text.afs", reports / "0_text.classified.csv",
        "data_diff", reports / "0_text.exclude.txt", reports / "0_text.safe.csv")
    run(TOOLS / "select_safe.py", a.xbox / "s_text.afs", a.pc_dat / "s_text.afs", reports / "s_text.classified.csv",
        "images_changed", "", reports / "s_text.safe.csv")

    print("[2/6] Musica (0_sound.afs)")
    run(TOOLS / "build_afs2fs.py", a.xbox / "0_sound.afs", reports / "0_sound.afs.csv",
        overrides / "we9-musica", "different", ".adx")

    print("[3/6] Kits, escudos y base de datos (0_text.afs) + checksum anti-modificacion")
    run(TOOLS / "build_afs2fs.py", a.xbox / "0_text.afs", reports / "0_text.safe.csv",
        overrides / "we9-kits", "safe", ".bin")
    fixed = 0
    for f in sorted((overrides / "we9-kits" / "0_text.afs").glob("*.bin")):
        d = f.read_bytes()
        if is_protected(d) and not tamper_ok(d):
            f.write_bytes(reprotect(d))
            fixed += 1
    print(f"  checksums corregidos: {fixed}")

    print("[4/6] Graficos de menu y miniaturas (s_text.afs) con IDs de textura de PC")
    ids = ",".join(map(str, safe_pc_indices(reports / "s_text.safe.csv")))
    run(TOOLS / "fix_tex_ids.py", a.xbox / "s_text.afs", a.pc_dat / "s_text.afs", reports / "s_text.safe.csv",
        ids, overrides / "we9-menus")

    print("[5/6] Textos (Liga Colombiana / Copa mustang II)")
    run(TOOLS / "str_patch.py", a.pc_dat / "s_text.afs", overrides / "we9-textos" / "s_text.afs",
        ",".join(map(str, TEXT_TABLES)), *[f"{k}={v}" for k, v in TEXT_REPLACEMENTS.items()])

    print("[6/6] Reconstruyendo los .afs de PC con el contenido incluido + option file")
    dat = a.out / "PES5" / "dat"
    dat.mkdir(parents=True)
    plan = {
        "0_sound.afs": [overrides / "we9-musica" / "0_sound.afs"],
        "0_text.afs": [overrides / "we9-kits" / "0_text.afs"],
        "s_text.afs": [overrides / "we9-menus" / "s_text.afs", overrides / "we9-textos" / "s_text.afs"],
    }
    for name, dirs in plan.items():
        n, k = rebuild(a.pc_dat / name, dat / name, dirs)
        print(f"  {name}: {n} entradas, {k} reemplazadas, verificacion: {verify(a.pc_dat / name, dat / name, dirs)}")
    (a.out / OPTION_FILE_DIR).mkdir(parents=True)
    shutil.copy2(a.option_file, a.out / OPTION_FILE_DIR / "KONAMI-WIN32PES5OPT")
    (a.out / "LEEME.txt").write_text(README, encoding="utf-8")

    lines = []
    for f in sorted(p for p in a.out.rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256"):
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {f.relative_to(a.out).as_posix()}")
    (a.out / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n")
    print(f"Listo: {a.out}")


if __name__ == "__main__":
    main()
