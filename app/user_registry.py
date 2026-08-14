"""Registro de usuarios y control de sesión por WhatsApp (Firestore).

Gestiona la colección `users`: alta/consulta/edición/baja de usuarios finales del
chatbot (nombre, apellido, dirección, rubro económico, WhatsApp y correo) y genera
un **código interno** estable de 8 caracteres por usuario.

El código interno es la clave de control de cada **sesión individual de WhatsApp**:
al llegar un mensaje, el webhook resuelve el número entrante a su código y usa ese
código (no el teléfono) como identificador de sesión/memoria del orquestador. Así
la conversación queda anclada a un identificador estable e interno aunque el usuario
cambie de número o se quiera anonimizar el teléfono.

Documento de usuario (id del documento = `code`):
    {
      "code":        str,   # código interno de 8 caracteres (PK)
      "nombre":      str,
      "apellido":    str,
      "direccion":   str,
      "rubro":       str,   # uno de ECONOMIC_SECTORS
      "whatsapp":    str,   # E.164 normalizado, p. ej. "+51987654321"
      "email":       str,
      "active":      bool,  # sesión habilitada
      "created_at":  timestamp,
      "updated_at":  timestamp,
      "last_seen_at": timestamp | None,  # último mensaje procesado por WhatsApp
    }

Cumplimiento (Ley 29733 / GDPR): datos personales mínimos y con finalidad declarada
(operación del asistente). `delete()` implementa el derecho de supresión.
"""
from __future__ import annotations

import functools
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Rubros económicos admitidos (lista cerrada expuesta también por la Admin UI).
ECONOMIC_SECTORS: tuple[str, ...] = (
    "Agroindustrial",
    "Maderero",
    "Pesquero",
    "Calzado y Cuero",
    "Textil",
    "Ganadero",
    "Acuícola",
    "Comercio",
    "Industria",
)

# Prefijo de 2 letras por rubro: da semántica al código interno sin romper los
# 8 caracteres (2 de prefijo + 6 aleatorios). Todos los prefijos son únicos.
_SECTOR_PREFIX: dict[str, str] = {
    "Agroindustrial": "AG",
    "Maderero": "MA",
    "Pesquero": "PE",
    "Calzado y Cuero": "CC",
    "Textil": "TX",
    "Ganadero": "GA",
    "Acuícola": "AC",
    "Comercio": "CO",
    "Industria": "IN",
}

# Alfabeto sin caracteres ambiguos (sin 0/O, 1/I/L) para dictar el código por voz
# o teclearlo sin error.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_RANDOM_LEN = 6  # 2 (prefijo) + 6 = 8 caracteres

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _as_dt(value: Any) -> Optional[datetime]:
    """Normaliza un timestamp de Firestore a datetime UTC tz-aware; None si no aplica."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


class UserRegistryError(ValueError):
    """Error de validación o de reglas de negocio del registro de usuarios."""


@dataclass
class UserRecord:
    code: str
    nombre: str
    apellido: str
    direccion: str
    rubro: str
    whatsapp: str
    email: str
    active: bool = True
    # Preferencia: recibir por WhatsApp el resumen automático del contenido nuevo
    # ingestado desde la carga de contenidos (novedades de la base de conocimiento).
    send_kb_summary: bool = True
    created_at: Any = None
    updated_at: Any = None
    last_seen_at: Any = None
    # Última vez que se le envió un mensaje de reenganche proactivo (enfriamiento).
    last_reengaged_at: Any = None

    @property
    def full_name(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserRecord":
        return cls(
            code=data.get("code", ""),
            nombre=data.get("nombre", ""),
            apellido=data.get("apellido", ""),
            direccion=data.get("direccion", ""),
            rubro=data.get("rubro", ""),
            whatsapp=data.get("whatsapp", ""),
            email=data.get("email", ""),
            active=bool(data.get("active", True)),
            send_kb_summary=bool(data.get("send_kb_summary", True)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_seen_at=data.get("last_seen_at"),
            last_reengaged_at=data.get("last_reengaged_at"),
        )


def normalize_whatsapp(number: str) -> str:
    """Normaliza un número a formato E.164 (`+` y dígitos).

    Acepta el prefijo 'whatsapp:' de Twilio, espacios, guiones y paréntesis.
    Si no trae código de país, asume Perú (+51). Lanza si no quedan dígitos.
    """
    raw = (number or "").strip()
    raw = raw.replace("whatsapp:", "")
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        digits = "+" + re.sub(r"\D", "", digits[1:])
    else:
        only = re.sub(r"\D", "", digits)
        if not only:
            raise UserRegistryError("El número de WhatsApp no contiene dígitos.")
        # Perú por defecto: 9 dígitos -> anteponer +51.
        digits = f"+51{only}" if len(only) == 9 else f"+{only}"
    if len(re.sub(r"\D", "", digits)) < 8:
        raise UserRegistryError("El número de WhatsApp es demasiado corto.")
    return digits


def _validate_email(email: str) -> str:
    email = (email or "").strip()
    if not _EMAIL_RE.match(email):
        raise UserRegistryError(f"Correo electrónico inválido: {email!r}")
    return email


class UserRegistry:
    """Acceso a la colección de usuarios registrados en Firestore."""

    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        db = settings.firestore_database
        self._client = client or firestore.Client(
            project=settings.gcp_project_id,
            database=None if db in ("(default)", "", None) else db,
        )
        self._collection_name = settings.firestore_users_collection

    @property
    def collection(self):
        return self._client.collection(self._collection_name)

    # --------------------------- Código interno ----------------------------
    def _generate_code(self, rubro: str) -> str:
        """Genera un código único de 8 caracteres: prefijo de rubro + 6 aleatorios."""
        prefix = _SECTOR_PREFIX.get(rubro, "XX")
        for _ in range(12):  # margen amplio; colisión es altamente improbable
            body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_RANDOM_LEN))
            code = f"{prefix}{body}"
            if not self.collection.document(code).get().exists:
                return code
        raise UserRegistryError("No se pudo generar un código interno único.")

    # ------------------------------- Altas ---------------------------------
    def create(
        self,
        *,
        nombre: str,
        apellido: str,
        direccion: str,
        rubro: str,
        whatsapp: str,
        email: str,
        send_kb_summary: bool = True,
    ) -> UserRecord:
        """Registra un usuario nuevo. Valida campos y unicidad de WhatsApp."""
        nombre = (nombre or "").strip()
        apellido = (apellido or "").strip()
        direccion = (direccion or "").strip()
        if not nombre or not apellido:
            raise UserRegistryError("Nombre y apellido son obligatorios.")
        if rubro not in ECONOMIC_SECTORS:
            raise UserRegistryError(f"Rubro económico inválido: {rubro!r}")
        whatsapp = normalize_whatsapp(whatsapp)
        email = _validate_email(email)

        existing = self.get_by_whatsapp(whatsapp)
        if existing is not None:
            raise UserRegistryError(
                f"Ya existe un usuario con ese WhatsApp (código {existing.code})."
            )

        code = self._generate_code(rubro)
        payload = {
            "code": code,
            "nombre": nombre,
            "apellido": apellido,
            "direccion": direccion,
            "rubro": rubro,
            "whatsapp": whatsapp,
            "email": email,
            "active": True,
            "send_kb_summary": send_kb_summary,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "last_seen_at": None,
        }
        self.collection.document(code).set(payload)
        logger.info("user_registered", code=code, rubro=rubro)
        return UserRecord.from_dict(payload)

    # ----------------------------- Consultas -------------------------------
    def get_by_code(self, code: str) -> Optional[UserRecord]:
        snap = self.collection.document((code or "").strip().upper()).get()
        return UserRecord.from_dict(snap.to_dict() or {}) if snap.exists else None

    def get_by_whatsapp(self, whatsapp: str) -> Optional[UserRecord]:
        try:
            number = normalize_whatsapp(whatsapp)
        except UserRegistryError:
            return None
        query = self.collection.where(
            filter=FieldFilter("whatsapp", "==", number)
        ).limit(1)
        for snap in query.stream():
            return UserRecord.from_dict(snap.to_dict() or {})
        return None

    def list_users(self) -> list[UserRecord]:
        users = [UserRecord.from_dict(s.to_dict() or {}) for s in self.collection.stream()]
        users.sort(key=lambda u: (u.apellido.lower(), u.nombre.lower()))
        return users

    def count(self) -> int:
        return self.collection.count().get()[0][0].value

    def kb_summary_recipients(self) -> list[UserRecord]:
        """Usuarios activos que aceptaron recibir el resumen de contenido nuevo.

        Es la lista de destinatarios a los que se debe enviar por WhatsApp el
        resumen automático de las novedades de la base de conocimiento.
        """
        return [u for u in self.list_users() if u.active and u.send_kb_summary]

    def reengagement_candidates(self, *, inactive_minutes: int,
                                cooldown_minutes: int,
                                limit: int = 50) -> list[UserRecord]:
        """Usuarios a reenganchar: activos, con opt-in, inactivos >= inactive_minutes
        (o que nunca escribieron) y sin reenganche en los últimos cooldown_minutes.

        En MINUTOS (antes eran días): el reenganche persigue retomar la
        conversación el mismo día, no al cabo de una semana.

        Reutiliza `send_kb_summary` como consentimiento de mensajes proactivos.
        """
        now = datetime.now(timezone.utc)
        inactive_before = now - timedelta(minutes=inactive_minutes)
        cooldown_before = now - timedelta(minutes=cooldown_minutes)
        out: list[UserRecord] = []
        for u in self.list_users():
            if not (u.active and u.send_kb_summary):
                continue
            seen = _as_dt(u.last_seen_at)
            if seen is not None and seen > inactive_before:
                continue  # tuvo actividad reciente
            reeng = _as_dt(u.last_reengaged_at)
            if reeng is not None and reeng > cooldown_before:
                continue  # ya se le reenganchó hace poco
            out.append(u)
            if len(out) >= limit:
                break
        return out

    def mark_reengaged(self, code: str) -> None:
        """Marca el instante del último reenganche (para el enfriamiento)."""
        self.collection.document((code or "").strip().upper()).set(
            {"last_reengaged_at": firestore.SERVER_TIMESTAMP}, merge=True)

    # ------------------------------ Edición --------------------------------
    def update(self, code: str, **fields: Any) -> UserRecord:
        """Actualiza campos editables de un usuario existente.

        El `code` es inmutable (es la identidad de la sesión). Se validan los
        campos que cambian igual que en el alta.
        """
        code = (code or "").strip().upper()
        current = self.get_by_code(code)
        if current is None:
            raise UserRegistryError(f"No existe un usuario con código {code}.")

        allowed = {"nombre", "apellido", "direccion", "rubro", "whatsapp", "email",
                   "active", "send_kb_summary"}
        updates: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in ("active", "send_kb_summary"):
                value = bool(value)
            if key == "rubro" and value not in ECONOMIC_SECTORS:
                raise UserRegistryError(f"Rubro económico inválido: {value!r}")
            if key == "email":
                value = _validate_email(value)
            if key == "whatsapp":
                value = normalize_whatsapp(value)
                other = self.get_by_whatsapp(value)
                if other is not None and other.code != code:
                    raise UserRegistryError(
                        f"Ese WhatsApp ya pertenece al usuario {other.code}."
                    )
            if key in ("nombre", "apellido", "direccion") and isinstance(value, str):
                value = value.strip()
            updates[key] = value

        if not updates:
            return current
        updates["updated_at"] = firestore.SERVER_TIMESTAMP
        self.collection.document(code).set(updates, merge=True)
        logger.info("user_updated", code=code, fields=list(updates))
        merged = {**asdict(current), **updates}
        return UserRecord.from_dict(merged)

    def set_active(self, code: str, active: bool) -> UserRecord:
        return self.update(code, active=active)

    def delete(self, code: str) -> None:
        """Baja definitiva del usuario (derecho de supresión, Ley 29733 / GDPR)."""
        code = (code or "").strip().upper()
        self.collection.document(code).delete()
        logger.info("user_deleted", code=code)

    # --------------------- Control de sesión WhatsApp ----------------------
    def resolve_session(self, whatsapp: str) -> str:
        """Devuelve la clave de sesión para un número entrante de WhatsApp.

        Si el número está registrado y activo, devuelve su **código interno** y
        marca `last_seen_at`. Si no está registrado (o está inactivo), devuelve un
        **token pseudonimizado** del número (HMAC-SHA256) en lugar del teléfono en
        claro, para no persistir PII como clave de memoria/rate-limit. El token es
        estable (conserva la continuidad de sesión) pero no reversible sin la sal.
        """
        from app.agent.guardrails import pseudonymize

        try:
            number = normalize_whatsapp(whatsapp)
        except UserRegistryError:
            raw = (whatsapp or "").replace("whatsapp:", "").strip()
            return pseudonymize(raw) if raw else raw

        user = self.get_by_whatsapp(number)
        if user is None or not user.active:
            return pseudonymize(number)
        try:
            self.collection.document(user.code).set(
                {"last_seen_at": firestore.SERVER_TIMESTAMP}, merge=True
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("user_last_seen_update_failed", code=user.code, error=str(exc))
        return user.code


@functools.lru_cache(maxsize=1)
def get_user_registry() -> UserRegistry:
    """Singleton del registro de usuarios (reutiliza el cliente Firestore)."""
    return UserRegistry()


# Un id de sesión es un código interno si tiene la forma «2 letras + 6 alfanum».
# Sirve para no consultar Firestore por sesiones que no son códigos (web:*, +51*,
# anon), evitando lecturas inútiles.
_CODE_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{6}$")


def looks_like_code(session_id: str) -> bool:
    return bool(_CODE_RE.match((session_id or "").strip()))


def registered_first_name(session_id: str) -> Optional[str]:
    """Nombre de pila del usuario si el id de sesión es un código interno válido.

    Devuelve None para sesiones que no son códigos (web/anónimas/teléfono sin
    registrar) sin tocar Firestore, y None ante cualquier error de acceso.
    """
    if not looks_like_code(session_id):
        return None
    try:
        user = get_user_registry().get_by_code(session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("registered_name_lookup_failed", error=str(exc))
        return None
    return user.nombre if user else None
