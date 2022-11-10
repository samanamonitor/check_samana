import importlib

class SAMMTest:
    plugins = [
        {
            "name": "check_samana4",
            "plugin": importlib.import_module(".etcdcheck.SAMMEtcdCheck", package="sammcheck")
        }, {
            "name": "check_wmi3",
            "plugin": importlib.import_module(".wmicheck.SAMMWMICheck", package="sammcheck")
        }]

    def __init__(self):
        pass