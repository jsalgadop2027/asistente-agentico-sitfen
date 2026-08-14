"""Tests del parseo de mensajes entrantes de Twilio (no requieren GCP)."""
from app.channels.twilio_whatsapp import parse_incoming


def test_parse_text_message():
    form = {"From": "whatsapp:+51999888777", "Body": "Hola", "NumMedia": "0"}
    msg = parse_incoming(form)
    assert msg.user_id == "+51999888777"
    assert msg.body == "Hola"
    assert msg.is_voice is False


def test_parse_voice_message():
    form = {
        "From": "whatsapp:+51999888777",
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/media/abc",
        "MediaContentType0": "audio/ogg",
    }
    msg = parse_incoming(form)
    assert msg.is_voice is True
    assert msg.media_url.endswith("/abc")


def test_parse_image_not_voice():
    form = {
        "From": "whatsapp:+51999888777",
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/media/img",
        "MediaContentType0": "image/jpeg",
    }
    msg = parse_incoming(form)
    assert msg.is_voice is False
    assert msg.is_image is True
    assert msg.media_url.endswith("/img")


def test_parse_image_with_caption():
    form = {
        "From": "whatsapp:+51999888777",
        "Body": "¿Qué le pasa a mi planta?",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/media/img",
        "MediaContentType0": "image/png",
    }
    msg = parse_incoming(form)
    assert msg.is_image is True and msg.is_voice is False
    assert msg.body == "¿Qué le pasa a mi planta?"


def test_text_message_is_not_image():
    form = {"From": "whatsapp:+51999888777", "Body": "Hola", "NumMedia": "0"}
    assert parse_incoming(form).is_image is False
