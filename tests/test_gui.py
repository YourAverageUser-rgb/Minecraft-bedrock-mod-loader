import pytest

tk = pytest.importorskip("tkinter")

from bedrock_mod_loader import gui
from bedrock_mod_loader.installer import install_pack
from bedrock_mod_loader.packs import read_pack_info

from .helpers import write_pack_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def app():
    try:
        instance = gui.App()
    except tk.TclError as exc:
        pytest.skip(f"no display available for Tk: {exc}")
    yield instance
    instance.destroy()


def test_app_has_expected_tabs(app):
    tabs = [app.notebook.tab(tab_id, "text") for tab_id in app.notebook.tabs()]
    assert tabs == ["Install", "Library", "Watch Folder", "Doctor"]


def test_app_title(app):
    assert app.title() == gui.APP_TITLE


def test_refresh_packs_lists_installed_packs(app, tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    app.game_dir_var.set(str(game_dir))
    app._refresh_packs()

    children = app.pack_tree.get_children()
    assert len(children) == 1
    assert app.pack_tree.item(children[0], "values")[1] == "Cool Pack"


def test_toggle_theme_does_not_raise(app):
    app._toggle_theme()


def test_launch_constructs_and_closes_immediately(monkeypatch):
    """Smoke-test launch() without blocking on mainloop()."""
    instances = []

    class FakeApp(gui.App):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

        def mainloop(self, *args, **kwargs):
            pass

    monkeypatch.setattr(gui, "App", FakeApp)
    try:
        gui.launch()
    except tk.TclError as exc:
        pytest.skip(f"no display available for Tk: {exc}")

    assert len(instances) == 1
    instances[0].destroy()
