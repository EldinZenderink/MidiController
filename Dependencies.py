"""Install dependencies when blender fails todo so.
"""

import os
import sys
import platform


class MidiController_Dependencies:
    """Help with installing the dependencies needed, but let the user decide.
    """
    required_packages_installed = True
    finished_installing_package = False
    progress_printer = []

    def wrap(width, text):
        lines = []

        arr = text.splitlines()
        lengthSum = 0

        strSum = ""

        for var in arr:
            lengthSum += len(var) + 1
            if lengthSum <= width:
                strSum += " " + var
            else:
                lines.append(strSum)
                lengthSum = 0
                strSum = var

        lines.append(" " + arr[len(arr) - 1])

        return lines

    def get_plugin_install_dir():
        return os.path.dirname(os.path.realpath(__file__))

    def select_system_package():
        script_path = MidiController_Dependencies.get_plugin_install_dir()
        python_version = ""
        if sys.version_info[1] == 11:
            python_version = "cp311-cp311"
        elif sys.version_info[1] == 10:
            python_version = "cp310-cp310"
        else:
            raise Exception(
                f"Python version: {sys.version} currently unsupported!")

        if platform.system() == "Windows":
            if platform.machine() in ['AMD64', 'x86_64']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-win_amd64.whl'))
        elif platform.system() == "Darwin":
            if platform.machine() in ['AMD64', 'x86_64']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-macosx_10_9_x86_64.whl'))
            if platform.machine() in ['aarch64_be', 'aarch64', 'armv8b', 'armv8l']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-macosx_11_0_arm64.whl'))
        else:  # possibly linux, just gotta try
            if platform.machine() in ['AMD64', 'x86_64']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-manylinux_2_28_x86_64.whl'))
            if platform.machine() in ['aarch64_be', 'aarch64', 'armv8b', 'armv8l']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-manylinux_2_28_aarch64.whl'))
        return None

    def get_python_executable():
        python_path = ""
        for path in sys.path:
            if '\\\\' in path:
                splitpath = path.split('\\\\')
                last_in_path = splitpath[-1]
                if last_in_path == "python":
                    python_path = path
            if '\\' in path:
                splitpath = path.split('\\')
                last_in_path = splitpath[-1]
                if last_in_path == "python":
                    python_path = path
            if '/' in path:
                splitpath = path.split('/')
                last_in_path = splitpath[-1]
                if last_in_path == "python":
                    python_path = path

        python_path = os.path.join(python_path, 'bin')

        if 'python.exe' in os.listdir(python_path):
            return os.path.join(python_path, 'python.exe')

        return None

    def get_packages_dir():
        script_path = MidiController_Dependencies.get_plugin_install_dir()
        site_packages_dir = os.path.join(script_path, 'site-packages')
        if not os.path.exists(site_packages_dir):
            MidiController_Dependencies.progress_printer += [
                "Creating site package dir in plugin directory:"]
            MidiController_Dependencies.progress_printer += [site_packages_dir]
            os.makedirs(site_packages_dir)
        return site_packages_dir
