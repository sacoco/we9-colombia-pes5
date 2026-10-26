# WE9 Colombia → PES5 PC

Port a **Pro Evolution Soccer 5 (PC)** de un parche antiguo de **Winning Eleven 9 para Xbox**:
Liga Colombiana / Copa Mustang, temporada 2006.

Incluye música, escudos, kits, miniaturas, menús, textos de liga y copa, nombres de equipos,
jugadores, estadísticas y plantillas. El resultado son 3 archivos `.afs` para reemplazar más un
option file. No requiere KitServer.

**Este repositorio no contiene archivos del juego**, solo herramientas y documentación. Para generar
el parche hacen falta los archivos del parche de Xbox y la carpeta `dat` original de PES5 PC.

Los detalles técnicos están en [docs/NOTAS-TECNICAS.md](docs/NOTAS-TECNICAS.md).

## Generar

Requiere Python 3.10+ y `pillow`.

```bash
python -I tools/build_patch.py --xbox <carpeta del parche Xbox> --pc-dat <dat original de PES5> --option-file <option file> --out dist
```

El option file con los jugadores lo genera el propio juego:

1. Instalá los `.afs` generados.
2. Borrá o mové `KONAMI-WIN32PES5OPT`, abrí el juego y guardá. El juego lo vuelve a crear desde la base de datos nueva.
3. Aplicale los nombres de equipos con `tools/team_names.py <default.xbe> <option file> <salida>`.
4. Volvé a correr el build con ese option file.

## Instalar

1. Copiá `PES5/dat/*.afs` a la carpeta `dat` del juego, reemplazando los existentes.
2. Copiá `KONAMI-WIN32PES5OPT` a `Documentos\KONAMI\Pro Evolution Soccer 5\save\folder1\`.

## Herramientas

| Script | Función |
|---|---|
| `build_patch.py` | Corre el proceso completo |
| `afs_align.py`, `tex_diff.py`, `select_safe.py` | Mapeo Xbox → PC y selección de entradas compatibles |
| `afs_compare.py`, `text_diff.py` | Comparación de AFS y de tablas de texto |
| `build_afs2fs.py` | Extrae entradas con nombres de AFS2FS |
| `fix_tex_ids.py` | Corrige los IDs de textura de Xbox |
| `str_patch.py` | Reemplaza textos en las tablas `.str` |
| `afs_rebuild.py` | Reconstruye un AFS de PC con las entradas reemplazadas |
| `team_names.py` | Copia los nombres de clubes del `.xbe` al option file |
| `pes_unobf.py`, `pes_tex.py`, `pes_db.py`, `pes5_of.py` | Entradas protegidas, texturas, base de datos y option file |
| `adx_preview.py`, `adx_headers.py`, `xbox_hdd.py`, `find_db.py` | Investigación: audio ADX, discos FATX y búsqueda de la base |

## Créditos

- [KitServer 5](https://github.com/kitserver/kitserver5) (Juce y colaboradores): AFS2FS y las direcciones de sus hooks.
- [PES5_WE9_LE_OF_Team_Editor](https://github.com/moth1995/PES5_WE9_LE_OF_Team_Editor) (moth1995, MIT): cifrado del option file.
- [PES5Editor](https://github.com/PeterC10/PES5Editor) (PeterC10): offsets de clubes.

## Licencia

MIT. `tools/vendor/moth1995` mantiene su propia licencia MIT. Pro Evolution Soccer y Winning Eleven son
marcas de Konami.
