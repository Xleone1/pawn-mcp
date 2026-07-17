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


def make_multi_symbol_source():
    """Build a Pawn file with multiple symbol kinds."""
    lines = [
        "// Multi-symbol test file",
        "#include <a_samp>",
        "",
        "#define MAX_JUGADORES 100",
        "#define SERVER_NAME\\",
        "    \"Mi Servidor\\",
        "    de SA:MP\"",
        "",
        "forward OnPlayerConnect(playerid);",
        "forward OnPlayerDisconnect(playerid, reason);",
        "",
        "new gPlayerName[MAX_PLAYERS][MAX_PLAYER_NAME];",
        "new gPlayerScore[MAX_PLAYERS];",
        "new Float:gPlayerPos[MAX_PLAYERS][3];",
        "static gServerUptime = 0;",
        "",
        "enum PlayerState {",
        "    STATE_NONE,",
        "    STATE_SPAWNED,",
        "    STATE_DEAD",
        "}",
        "",
        "enum eVehicleType (<<= 1) {",
        "    VEHICLE_CAR = 1,",
        "    VEHICLE_BIKE,",
        "    VEHICLE_BOAT",
        "}",
        "",
        "stock GetPlayerName(playerid, name[], len)",
        "{",
        "    GetPlayerName(playerid, name, len);",
        "    return 1;",
        "}",
        "",
        "public OnPlayerConnect(playerid)",
        "{",
        '    printf("Jugador conectado: %d", playerid);',
        "    return 1;",
        "}",
        "",
        "stock Float:GetDistance(Float:x1, Float:y1, Float:z1, Float:x2, Float:y2, Float:z2)",
        "{",
        "    return floatsqroot((x2-x1)*(x2-x1) + (y2-y1)*(y2-y1) + (z2-z1)*(z2-z1));",
        "}",
        "",
        "main()",
        "{",
        '    printf("Modo cargado");',
        "    return 1;",
        "}",
    ]
    return "\r\n".join(lines) + "\r\n"


def make_ambiguous_source():
    """Build a Pawn file with symbols sharing names."""
    lines = [
        "// Ambiguous symbol test file",
        "#include <a_samp>",
        "",
        "forward OnGameModeInit();",
        "forward OnGameModeExit();",
        "",
        "public OnGameModeInit()",
        "{",
        "    return 1;",
        "}",
        "",
        "public OnGameModeExit()",
        "{",
        "    return 1;",
        "}",
    ]
    return "\r\n".join(lines) + "\r\n"

