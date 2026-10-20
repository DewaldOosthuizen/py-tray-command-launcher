from unittest.mock import MagicMock


def test_probe_full_stub():
    from ui.quick_launch_pin_manager import QuickLaunchPinManager

    svc = MagicMock()
    svc.get_all_commands.return_value = []
    settings = {"quick_launch_bar": {"pinned": []}}
    pm = QuickLaunchPinManager(svc, settings)
    pm._available_list.clear.reset_mock()
    pm._available_list.addItem.reset_mock()
    pm._pinned_list.clear.reset_mock()
    pm._pinned_list.addItem.reset_mock()
    pm._refresh_pins_list()
    print("DEBUG full-stub available_list type:", type(pm._available_list).__name__)
    print(
        "DEBUG available_list.clear type:",
        type(pm._available_list.clear).__name__,
        "call_count:",
        pm._available_list.clear.call_count,
    )
    print(
        "DEBUG available_list.addItem type:",
        type(pm._available_list.addItem).__name__,
        "call_count:",
        pm._available_list.addItem.call_count,
    )
    print("DEBUG pins_committed type:", type(pm.pins_committed).__name__)
