from ui.output_window import RichOutputWindow


def test_rich_output_window_instantiates(qtbot):
    window = RichOutputWindow()
    qtbot.addWidget(window)
    assert window is not None
