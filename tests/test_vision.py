"""Tests de la comprensión de imágenes (#visión) — sin GCP ni Vertex (fakes)."""
import app.agent.models as models
from app.vision.describe import describe_image


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self._c = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return _FakeResp(self._c)


def _patch_llm(monkeypatch, factory):
    """Intercepta la llamada al modelo que hace `describe_image`.

    `describe_image` invoca vía `models.invoke_with_failover` (failover de
    ubicación ante 429), que a su vez resuelve `get_llm` como global en cada
    intento — así que parchear `get_llm` basta para interceptar la llamada sin
    depender de la ubicación que se esté probando.
    """
    monkeypatch.setattr(models, "get_llm", factory)


def _prompt_text(fake):
    """Extrae el bloque de texto del HumanMessage enviado al modelo."""
    content = fake.calls[0][0].content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


def test_describe_image_returns_text(monkeypatch):
    fake = _FakeLLM("Planta de arandano con posible clorosis en las hojas.")
    _patch_llm(monkeypatch, lambda **kw: fake)
    out = describe_image(b"\xff\xd8\xff", mime_type="image/jpeg")
    assert "arandano" in out.lower()


def test_describe_image_includes_caption_in_prompt(monkeypatch):
    fake = _FakeLLM("ok")
    _patch_llm(monkeypatch, lambda **kw: fake)
    describe_image(b"x", mime_type="image/png",
                   caption="que le pasa a mi planta")
    assert "que le pasa a mi planta" in _prompt_text(fake)


def test_describe_image_sends_image_block(monkeypatch):
    fake = _FakeLLM("ok")
    _patch_llm(monkeypatch, lambda **kw: fake)
    describe_image(b"abc", mime_type="image/webp")
    blocks = fake.calls[0][0].content
    file_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") == "file"]
    assert file_blocks and file_blocks[0]["mime_type"] == "image/webp"
    assert file_blocks[0]["base64"]  # imagen adjunta en base64


def test_describe_image_is_fail_open(monkeypatch):
    def boom(**kw):
        raise RuntimeError("vertex down")

    _patch_llm(monkeypatch, boom)
    assert describe_image(b"x", mime_type="image/png") == ""
