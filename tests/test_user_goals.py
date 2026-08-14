"""Tests del tracking de objetivos del usuario (#B) — sin GCP (fakes)."""
from app.user_goals import GoalStore, record_goal


class _FakeSnap:
    def __init__(self, data):
        self._d = data
        self.exists = data is not None

    def to_dict(self):
        return self._d


class _FakeDocRef:
    def __init__(self, store, key):
        self._s = store
        self._k = key

    def set(self, data, merge=False):
        if merge:
            self._s.setdefault(self._k, {}).update(data)
        else:
            self._s[self._k] = dict(data)

    def get(self):
        return _FakeSnap(self._s.get(self._k))


class _FakeColl:
    def __init__(self, store):
        self._s = store

    def document(self, key):
        return _FakeDocRef(self._s, key)


class _FakeClient:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return _FakeColl(self.store)


def test_upsert_and_get_roundtrip():
    gs = GoalStore(client=_FakeClient())
    gs.upsert("AGBXMBMQ", "exportar a China")
    assert gs.get("AGBXMBMQ") == "exportar a China"


def test_get_missing_returns_none():
    assert GoalStore(client=_FakeClient()).get("NOPE") is None


def test_record_goal_redacts_and_stores():
    ups = []

    class _S:
        def upsert(self, uid, obj):
            ups.append((uid, obj))

    record_goal("AGBXMBMQ", "  exportar a China  ", store=_S())
    assert ups == [("AGBXMBMQ", "exportar a China")]


def test_record_goal_empty_noop():
    ups = []

    class _S:
        def upsert(self, uid, obj):
            ups.append((uid, obj))

    record_goal("AGBXMBMQ", "   ", store=_S())
    assert ups == []


def test_record_goal_is_fail_open():
    class _S:
        def upsert(self, uid, obj):
            raise RuntimeError("firestore down")

    # No debe propagar.
    record_goal("AGBXMBMQ", "meta valida", store=_S())
