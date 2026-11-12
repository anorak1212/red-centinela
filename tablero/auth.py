"""Acceso al tablero con usuario y contraseña.

Sin dependencias nuevas (solo la biblioteca estándar) y sin secretos en el
repositorio: los usuarios viven en la variable de entorno
`REDCENTINELA_TABLERO_USUARIOS`, una entrada por usuario separada por comas:

    usuario:rol:pbkdf2_sha256$iteraciones$sal$hash

Roles:
- `admin`  puede todo, incluido predecir (escribe en el historial) y enviar
  el mensaje de prueba de Telegram.
- `lector` ve todas las vistas, pero los controles que escriben quedan
  deshabilitados y explican por qué.

El hash se genera sin que la contraseña quede en el historial de la terminal:

    python -m tablero.auth

También se acepta `usuario:rol:contraseña` en texto plano para una demo
rápida; el tablero lo marca como inseguro en la barra lateral.

Si la variable no existe, el tablero queda en acceso abierto (como antes) y
lo avisa. En Streamlit Community Cloud, una clave de primer nivel en los
secretos de la app se expone como variable de entorno con el mismo nombre.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

VARIABLE = "REDCENTINELA_TABLERO_USUARIOS"
ROLES = ("admin", "lector")
PREFIJO = "pbkdf2_sha256"
ITERACIONES = 240_000
INTENTOS_MAXIMOS = 5
BLOQUEO_SEGUNDOS = 60
SESION_HORAS = 8


@dataclass(frozen=True)
class Usuario:
    nombre: str
    rol: str
    secreto: str

    @property
    def texto_plano(self) -> bool:
        return not self.secreto.startswith(PREFIJO + "$")


def generar_hash(contrasena: str, iteraciones: int = ITERACIONES) -> str:
    sal = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)
    return "$".join([
        PREFIJO, str(iteraciones),
        base64.b64encode(sal).decode(), base64.b64encode(digest).decode(),
    ])


def verificar(contrasena: str, secreto: str) -> bool:
    """Compara en tiempo constante, tanto con hash como en texto plano."""
    if not secreto.startswith(PREFIJO + "$"):
        return hmac.compare_digest(contrasena.encode("utf-8"), secreto.encode("utf-8"))
    try:
        _, iteraciones, sal, esperado = secreto.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"),
                                     base64.b64decode(sal), int(iteraciones))
        return hmac.compare_digest(digest, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False


def cargar_usuarios(texto: str | None = None) -> dict[str, Usuario]:
    """Lee la variable de entorno. Las entradas mal formadas se ignoran."""
    texto = os.environ.get(VARIABLE, "") if texto is None else texto
    usuarios: dict[str, Usuario] = {}
    for entrada in texto.split(","):
        partes = entrada.strip().split(":", 2)
        if len(partes) != 3:
            continue
        nombre, rol, secreto = (p.strip() for p in partes)
        if nombre and secreto and rol in ROLES:
            usuarios[nombre.lower()] = Usuario(nombre.lower(), rol, secreto)
    return usuarios


def autenticar(usuarios: dict[str, Usuario], nombre: str, contrasena: str) -> Usuario | None:
    usuario = usuarios.get(nombre.strip().lower())
    if usuario is None:
        # Se verifica igual contra un hash ficticio para no revelar, por el
        # tiempo de respuesta, qué nombres de usuario existen.
        verificar(contrasena, _HASH_FICTICIO)
        return None
    return usuario if verificar(contrasena, usuario.secreto) else None


_HASH_FICTICIO = generar_hash(secrets.token_hex(8), iteraciones=ITERACIONES)


# --------------------------------------------------------------------------
# Estado de sesión (Streamlit)
# --------------------------------------------------------------------------
def configurado() -> bool:
    return bool(cargar_usuarios())


def usuario_actual(estado) -> dict | None:
    """Usuario de la sesión, o None si no hay sesión o expiró."""
    sesion = estado.get("auth_usuario")
    if not sesion:
        return None
    if time.time() - sesion.get("desde", 0) > SESION_HORAS * 3600:
        estado.pop("auth_usuario", None)
        return None
    return sesion


def puede_escribir(estado) -> bool:
    """Acceso abierto o rol admin: puede predecir y enviar pruebas."""
    if not configurado():
        return True
    sesion = usuario_actual(estado)
    return bool(sesion and sesion.get("rol") == "admin")


def segundos_bloqueado(estado) -> int:
    hasta = estado.get("auth_bloqueo_hasta", 0)
    return max(0, int(hasta - time.time()))


def registrar_fallo(estado) -> None:
    fallos = int(estado.get("auth_fallos", 0)) + 1
    estado["auth_fallos"] = fallos
    if fallos >= INTENTOS_MAXIMOS:
        estado["auth_bloqueo_hasta"] = time.time() + BLOQUEO_SEGUNDOS
        estado["auth_fallos"] = 0


def iniciar_sesion(estado, usuario: Usuario) -> None:
    estado["auth_usuario"] = {"nombre": usuario.nombre, "rol": usuario.rol,
                              "desde": time.time(), "texto_plano": usuario.texto_plano}
    estado["auth_fallos"] = 0


def cerrar_sesion(estado) -> None:
    estado.pop("auth_usuario", None)


if __name__ == "__main__":  # pragma: no cover - utilidad interactiva
    import getpass

    clave = getpass.getpass("Contraseña nueva: ")
    if clave != getpass.getpass("Repítela: "):
        raise SystemExit("Las contraseñas no coinciden.")
    if len(clave) < 8:
        raise SystemExit("Usa al menos 8 caracteres.")
    print(f"\nAgrega esto a {VARIABLE} (cambia usuario y rol):\n")
    print(f"usuario:admin:{generar_hash(clave)}")
