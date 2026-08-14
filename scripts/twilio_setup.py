"""Utilidad de habilitación de Twilio (verificar / configurar / simular).

Lee credenciales SOLO de variables de entorno (que se cargan desde Secret
Manager en runtime); nunca las imprime. Sub-modos:

  verify    -> valida credenciales, lista números y senders de WhatsApp.
  configure -> si el número objetivo es propio, fija el webhook de mensajería.
  simulate  -> envía al webhook desplegado una petición firmada estilo Twilio
               (texto) y muestra la respuesta TwiML del agente (prueba E2E).

Uso:
    python scripts/twilio_setup.py verify
    python scripts/twilio_setup.py configure --webhook https://.../webhook/whatsapp
    python scripts/twilio_setup.py simulate --webhook https://.../webhook/whatsapp \
        --text "Que documentos necesito para exportar arandano"
"""
from __future__ import annotations

import argparse
import os
import sys


def _creds():
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    number = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
    if not (sid and token):
        print("ERROR: faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN en el entorno.")
        sys.exit(2)
    return sid, token, number


def verify():
    from twilio.rest import Client

    sid, token, number = _creds()
    client = Client(sid, token)

    acct = client.api.accounts(sid).fetch()
    print(f"Cuenta: status={acct.status}  type={acct.type}")

    target = (number or "").replace("whatsapp:", "").strip()
    print(f"Número objetivo (de Secret Manager): {target or '(no definido)'}")

    print("\n-- Números de teléfono en la cuenta --")
    owned = client.incoming_phone_numbers.list(limit=20)
    found = None
    if not owned:
        print("  (ninguno: cuenta probablemente en modo Sandbox de WhatsApp)")
    for n in owned:
        caps = n.capabilities
        print(f"  {n.phone_number}  sms={caps.get('sms')}  "
              f"voice={caps.get('voice')}  sms_url={n.sms_url or '(vacío)'}")
        if n.phone_number == target:
            found = n

    # Senders de WhatsApp (API moderna), si están disponibles.
    try:
        senders = client.messaging.v2.channels_senders.list(limit=20)
        print("\n-- WhatsApp senders --")
        for s in senders:
            print(f"  {getattr(s, 'sender_id', s.sid)}  status={getattr(s, 'status', '?')}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n(Senders API no disponible: {exc})")

    print("\nRESULTADO:",
          "número PROPIO (configurable por API)" if found
          else "número NO propio -> WhatsApp Sandbox (webhook por consola)")
    return 0 if found else 10


def configure(webhook: str):
    from twilio.rest import Client

    sid, token, number = _creds()
    client = Client(sid, token)
    target = (number or "").replace("whatsapp:", "").strip()
    owned = {n.phone_number: n for n in client.incoming_phone_numbers.list(limit=50)}
    if target not in owned:
        print("El número no es propio; el webhook del Sandbox se configura en consola.")
        return 10
    n = owned[target]
    n.update(sms_url=webhook, sms_method="POST")
    print(f"Webhook de mensajería configurado en {target} -> {webhook}")
    return 0


def simulate(webhook: str, text: str):
    import httpx
    from twilio.request_validator import RequestValidator

    sid, token, number = _creds()
    from_number = number if number.startswith("whatsapp:") else f"whatsapp:{number}"
    params = {
        "From": "whatsapp:+51999000111",
        "To": from_number,
        "Body": text,
        "NumMedia": "0",
        "MessageSid": "SMtest0000000000000000000000000000",
        "AccountSid": sid,
    }
    signature = RequestValidator(token).compute_signature(webhook, params)
    print("Enviando petición firmada al webhook desplegado...")
    resp = httpx.post(webhook, data=params,
                      headers={"X-Twilio-Signature": signature}, timeout=90)
    print(f"HTTP {resp.status_code}")
    print("--- Respuesta TwiML ---")
    print(resp.text)
    return 0 if resp.status_code == 200 else 1


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    c = sub.add_parser("configure")
    c.add_argument("--webhook", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("--webhook", required=True)
    s.add_argument("--text", default="Hola, que requisitos necesito para exportar arandano a China")
    args = p.parse_args()

    if args.cmd == "verify":
        return verify()
    if args.cmd == "configure":
        return configure(args.webhook)
    if args.cmd == "simulate":
        return simulate(args.webhook, args.text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
