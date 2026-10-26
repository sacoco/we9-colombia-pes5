# Notas técnicas

Las direcciones corresponden a `PES5.exe` de PC (SHA-256 `12d99248…62d62`, base `0x400000`).

## AFS

- Formato: `AFS\0`, cantidad de entradas, tabla de `(offset, tamaño)`. Entradas alineadas a `0x800`.
- El puntero a la tabla de nombres del final no tiene sentido en los AFS de PC (apunta al medio de
  los datos), y el juego no lo usa.
- El juego pide archivos por índice: ID = `(AFS << 16) | índice`. **No se puede reemplazar un AFS de
  Xbox entero**: el orden y la cantidad de entradas cambian, y el juego se cae.
- Reconstruir el AFS de PC con el mismo orden y cantidad de entradas, cambiando solo el contenido,
  funciona sin problemas (`afs_rebuild.py`).

## Headers de entrada (32 bytes)

`+0x02 == 1` indica que está comprimido; `+0x04` es el tamaño comprimido, `+0x08` el descomprimido y
los datos zlib empiezan en `+0x20`.

| Bytes 0–3 | Uso |
|---|---|
| `00 06 01 00` | entrada comprimida |
| `00 01 01 00` | bloque comprimido suelto |
| `00 06 00 00` | contenedor de la base de datos |
| `00 02 00 00` | contenedor de texturas |
| `00 03 01 00` | textura comprimida dentro del contenedor |
| `00 00 01 00` | sección de la base de datos |
| `00 04 00 00` | sub-bloque de una tabla de texto |

Funciones: `sub_829260` (lee el header), `sub_8291A0` (zlib 1.1.4 `uncompress`), `sub_8D7E70` (`inflate`).

## Entradas protegidas y chequeo anti-modificación

Son las entradas `00 06 01 00` con bytes distintos de cero en `0x10..0x1F`. Las decodifica
`sub_84C4C0`, que llama a `0x829360` (`C_UNIDECODE` en KitServer). Con `w` = palabras u32:

```
w[8]  ^= (w[6] + w[7]) & 0x230AB3FE
w[10] ^=  w[4] + (w[5] & 0xFEA938F2)
w[11] ^= (w[7] - w[5]) & 0x8A10A67A
w[15] ^=  w[4] - (w[6] & 0x37AA3BEF)

checksum = (w[1] + w[9]) ^ 0x2332296E;  for v = 1; v < (w[1] >> 2) - 1; v += 32: checksum ^= w[v + 8]
```

Si `checksum != w[4]`, el juego activa `dword_1003794`, y desde ese momento **deja de cargar la textura
de menor detalle de todos los kits**. Hay kits de parches viejos que fallan este chequeo: hay que
recalcular `w[4]` y volver a ofuscar (`pes_unobf.reprotect`).

## Texturas

- Contenedor (offsets relativos a `+0x20`): cantidad, tabla de punteros a nombres, tabla de offsets de
  datos; bloques alineados a 16; `+0x04` = tamaño total − `0x20`.
- Textura (magic `94 72 85 29`): `+0x0C` ID, `+0x10` offset de píxeles, `+0x12` offset de paleta,
  `+0x14`/`+0x16` ancho y alto. Paleta RGBA de 16 o 256 colores con alfa de PS2 (`0x80` = opaco).
  Los píxeles están en orden "swizzled" de PS2 en ambas plataformas.
- **En Xbox el ID vale el de PC + 1.** Sin corregirlo, las texturas salen en blanco o el juego se cierra.

## Audio

- La música ADX de Xbox (v3, 44,1 kHz, sin loop) funciona tal cual en PC (v4, 24 kHz, con loop).
- Los bancos de sonido de `0_text.afs` en Xbox están en **Xbox ADPCM** (proporción de tamaño PC/Xbox
  de 3,55). Si se portan, se oye un pitido en los menús. Hay que excluirlos.

## Mapeo Xbox ↔ PC

- Alinear por hash (como un `diff`), refinar por tamaño exacto dentro de cada bloque distinto y emparejar
  por posición solo si coinciden el header y el tipo.
- Descartar las entradas cuyo tamaño descomprimido o estructura interna no coincida. Son probables
  modelos en formato Xbox, y emparejarlas mal provoca cierres.

## Base de datos de fábrica

- Cargador: `sub_8EDBE0`. Reparto de secciones por ID de archivo: `sub_8EF260`.

  | ID | Entrada de `0_text` (PC) | Secciones |
  |---|---|---|
  | `0x10016` | 22 | 0–6 (0 = jugadores) |
  | `0x10018` | 24 | 7–9 |
  | `0x10017` | 23 | 10–12 |
  | `0x10013` | 19 | 13–17 |
  | `0x10012` | 18 | 18 |
  | `0x10011` | 17 | 19–24 |

- Contenedor `00 06 00 00` → en `+0x20`: cantidad, `8`, offsets relativos a `+0x20` → secciones `00 00 01 00`.
- Sección 0: 4896 jugadores × 124 bytes. En memoria va a `0xC45AA8` (`sub_8EDD60`).
- `sub_4356E0` arma el option file desde la memoria. **La base de fábrica solo se usa cuando no existe
  option file**: para que tome efecto, hay que regenerarlo.
- `WEPLDATA` (`0_text` PC #25): nombres de camiseta.

## Option file de PC

- Cifrado: XOR con una clave de 256 bytes, más suma/resta por bloque con una clave de 367 palabras, más
  checksums (`pes5_of.py`).
- Jugadores: `36872 + id × 124` (nombre UTF-16 de 32 bytes; camiseta en `+32`).
- Plantillas de clubes: `667458 + club × 64`.
- Clubes: `803608 + i × 140`. Nombre en `+0` (49 bytes UTF-8), abreviatura en `+73` y bandera de editado en `+110`.
- Nombres de liga (`6558`): vacíos salvo que se editen. Si están vacíos, el juego usa las tablas de texto.

## Nombres de clubes

Están en el ejecutable (`default.xbe` / `PES5.exe`): nombre rellenado a 4 bytes + abreviatura de 4 bytes.
No están en la base de datos, así que en PC se escriben en el option file.

## Tablas de texto (`.str`)

Contenedor → sub-bloques `00 04 00 00` → `u32 cantidad, u32 ?, {u32 id, u16 bytes, u16 caracteres,
u32 offset} × cantidad`, seguido de los textos UTF-8. Los nombres de liga y copa están en `s_text` #2 y
#148. Las tablas de Xbox traen textos de botones y Memory Card de consola: hay que reemplazar textos
puntuales, no tablas completas.
