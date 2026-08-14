"""Tests del envío saliente de WhatsApp: división de mensajes largos.

Bug real de producción: `send_whatsapp_message` truncaba la respuesta a 1550
caracteres (`body[:1550]`) en vez de dividirla, cortando respuestas largas del
agente a mitad de frase sin avisar. Ver `app.channels.twilio_whatsapp`.
"""
import app.channels.twilio_whatsapp as tw
from app.channels.twilio_whatsapp import _split_message, send_whatsapp_message


def test_split_message_short_text_unchanged():
    assert _split_message("Hola, ¿en qué te ayudo?") == ["Hola, ¿en qué te ayudo?"]


def test_split_message_empty():
    assert _split_message("") == [""]


def test_split_message_splits_on_paragraphs_without_cutting_words():
    long_text = ("Primer párrafo. " * 60).strip() + "\n\n" + ("Segundo párrafo. " * 60).strip()
    chunks = _split_message(long_text, max_len=200)
    assert len(chunks) > 1
    # Nada se pierde: unir los fragmentos reconstruye todo el contenido.
    assert " ".join(chunks).replace("  ", " ").count("Primer párrafo.") == 60
    assert " ".join(chunks).replace("  ", " ").count("Segundo párrafo.") == 60
    for c in chunks:
        assert len(c) <= 200
        assert not c.endswith(" ")


def test_split_message_single_long_paragraph_splits_by_word():
    long_text = "palabra " * 500  # un solo párrafo, muy largo
    chunks = _split_message(long_text, max_len=100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 100
    # Ninguna palabra se corta a la mitad.
    for c in chunks:
        assert all(w == "palabra" for w in c.split())


def test_split_message_real_cutoff_case_preserves_full_answer():
    """Reproduce el caso real: una respuesta de ~1950 caracteres que antes se
    cortaba a mitad de frase en el caracter 1550."""
    body = ("Aquí te explico los puntos clave. " * 60).strip()
    assert len(body) > 1550
    chunks = _split_message(body)
    reconstructed = " ".join(chunks)
    assert reconstructed.count("puntos clave.") == body.count("puntos clave.")
    assert reconstructed.rstrip().endswith("puntos clave.")


class _FakeMessages:
    def __init__(self, calls):
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs)

        class _Msg:
            sid = f"SM{len(self._calls)}"

        return _Msg()


class _FakeClient:
    def __init__(self, sid, token):
        self.calls: list[dict] = []
        self.messages = _FakeMessages(self.calls)


def test_send_whatsapp_message_short_body_sends_one_message(monkeypatch):
    monkeypatch.setattr(tw, "get_twilio_credentials", lambda: {
        "account_sid": "AC1", "auth_token": "tok",
        "whatsapp_number": "whatsapp:+10000000000",
    })
    fake_clients: list[_FakeClient] = []

    def _client_factory(sid, token):
        c = _FakeClient(sid, token)
        fake_clients.append(c)
        return c

    import twilio.rest
    monkeypatch.setattr(twilio.rest, "Client", _client_factory)

    ok = send_whatsapp_message("whatsapp:+51999888777", "Hola, todo listo.")
    assert ok is True
    assert len(fake_clients[0].calls) == 1
    assert fake_clients[0].calls[0]["body"] == "Hola, todo listo."


def test_send_whatsapp_message_long_body_sends_multiple_messages_and_preserves_content(monkeypatch):
    monkeypatch.setattr(tw, "get_twilio_credentials", lambda: {
        "account_sid": "AC1", "auth_token": "tok",
        "whatsapp_number": "whatsapp:+10000000000",
    })
    fake_clients: list[_FakeClient] = []

    def _client_factory(sid, token):
        c = _FakeClient(sid, token)
        fake_clients.append(c)
        return c

    import twilio.rest
    monkeypatch.setattr(twilio.rest, "Client", _client_factory)

    long_body = ("Aquí te explico los puntos clave. " * 60).strip()
    ok = send_whatsapp_message("whatsapp:+51999888777", long_body,
                               image_url="https://example.com/chart.png")
    assert ok is True
    calls = fake_clients[0].calls
    assert len(calls) > 1
    # El contenido completo se preserva a través de todos los fragmentos.
    reconstructed = " ".join(c["body"] for c in calls)
    assert reconstructed.count("puntos clave.") == long_body.count("puntos clave.")
    # El media solo se adjunta al último fragmento.
    from twilio.base import values
    for c in calls[:-1]:
        assert c["media_url"] is values.unset
    assert calls[-1]["media_url"] == ["https://example.com/chart.png"]
