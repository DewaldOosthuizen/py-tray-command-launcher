from ui.quick_launch_bar import QuickLaunchBar


def test_quick_launch_bar_instantiates(mock_services, qtbot):
    bar = QuickLaunchBar(services=mock_services)
    qtbot.addWidget(bar)
    assert bar is not None
