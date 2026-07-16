"""
Shared test utilities for pawn-mcp.
"""


# ── Spanish test words that must survive CP1252 round-trips ──────────

SPANISH_WORDS = [
    "Contraseña",
    "Último",
    "Información",
    "Vehículo",
    "Niño",
    "Acción",
]

# Additional Spanish characters
SPANISH_PUNCTUATION = "¿Cómo estás? ¡Hola!"


def make_pawn_source(words=None):
    """Build a realistic Pawn source file using Spanish words."""
    if words is None:
        words = SPANISH_WORDS

    lines = [
        '// Pawn test gamemode',
        '#include <a_samp>',
        '',
        f'new gPlayerPassword[32] = "{words[0]}";',
        f'new gLastAccess[32] = "{words[1]}";',
        f'new gInfo[64] = "{words[2]}";',
        f'new gVehicleName[32] = "{words[3]}";',
        f'new gChildName[32] = "{words[4]}";',
        f'new gAction[32] = "{words[5]}";',
        '',
        f'new gGreeting[] = "{SPANISH_PUNCTUATION}";',
        '',
        'main()',
        '{',
        f'    printf("Modo cargado: {words[0]}");',
        '    return 1;',
        '}',
    ]
    return '\r\n'.join(lines) + '\r\n'


def make_cp1252_file(content_str, line_ending='CRLF'):
    """
    Encode a string as CP1252 bytes with specified line endings.
    """
    # Normalize to the desired line ending
    text = content_str.replace('\r\n', '\n').replace('\r', '\n')
    if line_ending == 'CRLF':
        text = text.replace('\n', '\r\n')
    elif line_ending == 'CR':
        text = text.replace('\n', '\r')

    return text.encode('cp1252')
