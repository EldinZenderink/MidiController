# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option   ) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import traceback
import json
import copy
import bpy
import math
import site
import os
import sys
import platform
import subprocess

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
            lengthSum+=len(var) + 1
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
            raise Exception(f"Python version: {sys.version} currently unsupported!")


        if platform.system() == "Windows":
            if platform.machine() in ['AMD64', 'x86_64']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-win_amd64.whl'))
        elif platform.system() == "Darwin":
            if platform.machine() in ['AMD64', 'x86_64']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-macosx_10_9_x86_64.whl'))
            if platform.machine() in ['aarch64_be', 'aarch64', 'armv8b', 'armv8l']:
                return os.path.join(script_path, os.path.join('wheels', f'python_rtmidi-1.5.8-{python_version}-macosx_11_0_arm64.whl'))
        else: # possibly linux, just gotta try
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
            MidiController_Dependencies.progress_printer += ["Creating site package dir in plugin directory:"]
            MidiController_Dependencies.progress_printer += [site_packages_dir]
            os.makedirs(site_packages_dir)
        return site_packages_dir

try:
    site.addsitedir(MidiController_Dependencies.get_packages_dir())
    import rtmidi
    MidiController_Dependencies.finished_installing_package = False
    MidiController_Dependencies.required_packages_installed = True
    print("imported rtmidi")
except ImportError as e:
    print(e)
    MidiController_Dependencies.finished_installing_package = False
    MidiController_Dependencies.required_packages_installed = False
    print("failed importing midi")

bl_info = {
    "name": "MidiController",
    "author": "Eldin Zenderink",
    "description": "",
    "blender": (3, 00, 0),
    "version": (0, 0, 2),
    "location": "",
    "warning": "",
    "category": "Generic"
}


class MidiController_Midi():
    # to register and controlmidi
    connected_controller = ""
    connected_port = None
    available_ports = None
    midi_input = None
    midi_open = False
    midi = None
    midi_last_control_changed = 0
    midi_last_control_value = 0
    midi_last_control_velocity = 0
    midi_control_to_map = None

    # State machine stuff
    class State:
        NONE = 0
        REGISTER_CONTROL = 1
        CONFIGURE_MAPPING = 2

    # State machine stuff
    class EditState:
        NONE = 0
        EDIT = 1

    # State machine stuff
    class KeyFrameBindingState:
        NONE = 0
        PENDING = 1

    # The current mapping state
    current_mapping_state = State.NONE

    # To interact/update ui
    screens = None

    # To interact/update objects
    context = None

    # Map a midi control to a property somehow
    mapping_pending = None
    controller_property_mapping = {}
    properties_to_skip = []
    controller_names = {}

    # Controller to edit
    editting_controller = None
    editting_mapped = None
    editting_index = None
    edit_state = EditState.NONE

    # Controller to register keyframe(s) (note: all properties)
    key_frame_control = None
    bind_control_state = KeyFrameBindingState.NONE
    button_velocity_pressed = 0

    # midi update rate
    midi_update_rate = 0.08

    # class for usage in timer to read midi input
    class ParseMidiMessages():
        def parse_midi_messages():
            try:
                if MidiController_Midi.midi_input is not None and MidiController_Midi.midi_input.is_port_open():
                    last_data = None
                    data = MidiController_Midi.midi_input.get_message()
                    while data is not None and MidiController_Midi.midi_input.is_port_open():
                        last_data = data
                        data = MidiController_Midi.midi_input.get_message()
                    if last_data is not None:
                        MidiController_Midi.midi_callback(last_data)
            except Exception as e:
                print("Failed reading from midi controller!")
                print(traceback.format_exc())
                print(e)
            return MidiController_Midi.midi_update_rate

    class PropertyChangeProcess():

        previous_object = None
        current_object = None
        previous_object_data = {}
        current_object_data = {}
        accepted_types = ["<class 'int'>", "<class 'float'>",
                          "<class 'list'>", "<class 'Vector'>", "<class 'IDPropertyArray'>"]

        # Listen for a property change of a selected object to map to midi control
        def listen_for_property_changes():

            try:
                if bpy.context.screen.is_animation_playing:
                    return MidiController_Midi.midi_update_rate

                new_obj_template = {
                    "index": None,
                    "value": None,
                    "name": None,
                    "property": None,
                    "key": False,
                    "data": False,
                    "type": None,
                    "min": 0,
                    "max": 0
                }

                if MidiController_Midi.current_mapping_state != MidiController_Midi.State.NONE:
                    if len(bpy.context.selected_objects) == 0:
                        return MidiController_Midi.midi_update_rate

                    obj = bpy.context.selected_objects[0]
                    MidiController_Midi.PropertyChangeProcess.current_object = obj.name

                    if MidiController_Midi.PropertyChangeProcess.previous_object != MidiController_Midi.PropertyChangeProcess.current_object:
                        MidiController_Midi.PropertyChangeProcess.previous_object = obj.name
                        MidiController_Midi.PropertyChangeProcess.previous_object_data = {}
                        MidiController_Midi.PropertyChangeProcess.current_object_data = {}
                        return MidiController_Midi.midi_update_rate

                    # default props
                    # print("attr in obj:")
                    # print(len(dir(obj)))
                    if len(dir(obj)) < 200:
                        for prop in dir(obj):
                            if str(type(getattr(obj, prop))) in MidiController_Midi.PropertyChangeProcess.accepted_types:
                                if str(type(getattr(obj, prop))) in ["<class 'Vector'>"]:
                                    if len(getattr(obj, prop)) > 6:
                                        print("attribute way to large, skipping")
                                        continue
                                    for i, v in enumerate(getattr(obj, prop)):
                                        if f"{prop}_{i}" in MidiController_Midi.properties_to_skip:
                                            continue
                                        new_obj = copy.deepcopy(
                                            new_obj_template)
                                        new_obj["name"] = f"{prop}_{i}"
                                        new_obj["property"] = prop
                                        new_obj["data"] = False
                                        new_obj["type"] = str(
                                            type(getattr(obj, prop)))
                                        new_obj['index'] = i
                                        new_obj['value'] = v
                                        MidiController_Midi.PropertyChangeProcess.current_object_data[f"{prop}_{i}"] = copy.copy(
                                            new_obj)
                                elif str(type(getattr(obj, prop))) in ["<class 'IDPropertyArray'>"]:
                                    if len(getattr(obj, prop).to_list()) > 6:
                                        print("attribute way to large, skipping")
                                        continue
                                    for i, v in enumerate(getattr(obj, prop).to_list()):
                                        if f"{prop}_{i}" in MidiController_Midi.properties_to_skip:
                                            continue
                                        new_obj = copy.deepcopy(
                                            new_obj_template)
                                        new_obj["name"] = f"{prop}_{i}"
                                        new_obj["property"] = prop
                                        new_obj["data"] = False
                                        new_obj["type"] = str(
                                            type(getattr(obj, prop)))
                                        new_obj['index'] = i
                                        new_obj['value'] = v
                                        MidiController_Midi.PropertyChangeProcess.current_object_data[f"{prop}_{i}"] = copy.copy(
                                            new_obj)
                                else:
                                    if f"{prop}" in MidiController_Midi.properties_to_skip:
                                        continue
                                    new_obj = copy.deepcopy(new_obj_template)
                                    new_obj["name"] = f"{prop}"
                                    new_obj["property"] = prop
                                    new_obj["data"] = False
                                    new_obj["type"] = str(
                                        type(getattr(obj, prop)))
                                    new_obj['value'] = getattr(obj, prop)
                                    MidiController_Midi.PropertyChangeProcess.current_object_data[f"{prop}"] = copy.copy(
                                        new_obj)

                    # custom props
                    if len(obj.keys()) > 1 and len(obj.keys()) < 200:
                        # First item is _RNA_UI
                        for K in obj.keys():
                            if K not in '_RNA_UI':
                                value = obj[K]
                                prop = K
                                if str(type(value)) in MidiController_Midi.PropertyChangeProcess.accepted_types:
                                    if str(type(value)) in ["<class 'Vector'>"]:
                                        if len(value) > 6:
                                            print(
                                                "attribute way to large, skipping")
                                            continue
                                        for i, v in enumerate(value):
                                            if f"{prop}_{i}" in MidiController_Midi.properties_to_skip:
                                                continue
                                            new_obj = copy.deepcopy(
                                                new_obj_template)
                                            new_obj["name"] = f"{prop}_{i}"
                                            new_obj["property"] = prop
                                            new_obj["key"] = True
                                            new_obj["data"] = False
                                            new_obj['index'] = i
                                            new_obj['value'] = v
                                            new_obj["type"] = str(type(value))
                                            MidiController_Midi.PropertyChangeProcess.current_object_data[f"prop_{i}"] = copy.copy(
                                                new_obj)
                                    elif str(type(value)) in ["<class 'IDPropertyArray'>"]:
                                        if len(value.to_list()) > 6:
                                            print(
                                                "attribute way to large, skipping")
                                            continue
                                        for i, v in enumerate(value.to_list()):
                                            if f"{prop}_{i}" in MidiController_Midi.properties_to_skip:
                                                continue
                                            new_obj = copy.deepcopy(
                                                new_obj_template)
                                            new_obj["name"] = f"{prop}_{i}"
                                            new_obj["property"] = prop
                                            new_obj["key"] = True
                                            new_obj["data"] = False
                                            new_obj['index'] = i
                                            new_obj['value'] = v
                                            new_obj["type"] = str(type(value))
                                            MidiController_Midi.PropertyChangeProcess.current_object_data[f"prop_{i}"] = copy.copy(
                                                new_obj)
                                    else:
                                        if f"{prop}" in MidiController_Midi.properties_to_skip:
                                            continue
                                        new_obj = copy.deepcopy(
                                            new_obj_template)
                                        new_obj["name"] = f"{prop}"
                                        new_obj["property"] = prop
                                        new_obj["key"] = True
                                        new_obj["data"] = False
                                        new_obj['value'] = value
                                        new_obj["type"] = str(type(value))
                                        MidiController_Midi.PropertyChangeProcess.current_object_data[prop] = copy.copy(
                                            new_obj)

                    if MidiController_Midi.PropertyChangeProcess.previous_object == MidiController_Midi.PropertyChangeProcess.current_object:
                        for key, value in MidiController_Midi.PropertyChangeProcess.current_object_data.items():
                            if key in MidiController_Midi.PropertyChangeProcess.previous_object_data:
                                if value['value'] != MidiController_Midi.PropertyChangeProcess.previous_object_data[key]['value']:
                                    MidiController_Midi.mapping_pending = copy.copy(
                                        value)
                                    MidiController_Midi.current_mapping_state = MidiController_Midi.State.CONFIGURE_MAPPING
                            else:
                                print(f"Key: {key} not in previous object :(")
                                print(str(type(value)))

                    MidiController_Midi.PropertyChangeProcess.previous_object = copy.copy(
                        MidiController_Midi.PropertyChangeProcess.current_object)
                    MidiController_Midi.PropertyChangeProcess.previous_object_data = copy.copy(
                        MidiController_Midi.PropertyChangeProcess.current_object_data)

                    return MidiController_Midi.midi_update_rate
            except Exception as e:
                print("Failed detecting changes in object!")
                print(traceback.format_exc())
                print(e)

            return MidiController_Midi.midi_update_rate

    def redraw_ui():
        for screen in MidiController_Midi.screens:
            try:
                for area in screen.areas:
                    area.tag_redraw()
            except Exception as e:
                print(e)
                print("Screen error")

    def update_data(mapping, new_value):
        for obj in bpy.context.selected_objects:
            if mapping["key"]:
                if mapping["property"] not in obj:
                    continue
                if mapping["type"] in ["<class 'Vector'>"]:
                    obj[mapping["property"]][mapping["index"]
                                             ] = float(new_value)
                elif mapping["type"] in ["<class 'IDPropertyArray'>"]:
                    obj[mapping["property"]][mapping["index"]
                                             ] = float(new_value)
                elif mapping["type"] in ["<class 'int'>"]:
                    obj[mapping["property"]] = float(new_value)
                elif mapping["type"] in ["<class 'float'>"]:
                    obj[mapping["property"]] = float(new_value)

            else:
                if hasattr(obj, mapping["property"]) == False:
                    continue
                if mapping["type"] in ["<class 'Vector'>"]:
                    getattr(obj, mapping["property"])[
                        mapping["index"]] = float(new_value)
                elif mapping["type"] in ["<class 'IDPropertyArray'>"]:
                    getattr(obj, mapping["property"])[
                        mapping["index"]] = float(new_value)
                elif mapping["type"] in ["<class 'int'>"]:
                    setattr(obj, mapping["property"], int(new_value))
                elif mapping["type"] in ["<class 'float'>"]:
                    setattr(obj, mapping["property"], float(new_value))

            # changing the location of the object refreshes the object, which is hack AF
            getattr(obj, "location")[0] = copy.copy(
                getattr(obj, "location")[0])

    def insert_keyframes():
        for obj in bpy.context.selected_objects:
            for controller, mapping_array in MidiController_Midi.controller_property_mapping.items():
                for mapping in mapping_array:
                    try:
                        if mapping["type"] in ["<class 'Vector'>", "<class 'IDPropertyArray'>"]:
                            if mapping['key']:
                                obj.keyframe_insert(
                                    f'["{mapping["property"]}"]', index=mapping['index'])
                            else:
                                obj.keyframe_insert(
                                    mapping['property'], index=mapping['index'])
                        elif mapping["type"] in ["<class 'int'>", "<class 'float'>"]:
                            if mapping['key']:
                                obj.keyframe_insert(
                                    f'["{mapping["property"]}"]')
                            else:
                                obj.keyframe_insert(mapping['property'])
                    except Exception as e:
                        print(e)
                        print(
                            "Ugly but functional way to skip properties that are not part of the selected object")

    def midi_callback(midi_data):
        velocity = midi_data[0][0]
        control = midi_data[0][1]
        value = midi_data[0][2]

        if velocity != MidiController_Midi.midi_last_control_velocity:
            if MidiController_Midi.bind_control_state == MidiController_Midi.KeyFrameBindingState.PENDING:
                MidiController_Midi.key_frame_control = control

                if str(control) == str(MidiController_Midi.key_frame_control):
                    if MidiController_Midi.button_velocity_pressed == 0:
                        MidiController_Midi.button_velocity_pressed = velocity
                        MidiController_Midi.bind_control_state = MidiController_Midi.KeyFrameBindingState.NONE
                    elif velocity == MidiController_Midi.button_velocity_pressed:
                        MidiController_Midi.insert_keyframes()

            if str(control) == str(MidiController_Midi.key_frame_control) and velocity == MidiController_Midi.button_velocity_pressed:
                MidiController_Midi.insert_keyframes()

            MidiController_Midi.midi_last_control_velocity = velocity

        if value != MidiController_Midi.midi_last_control_value:
            MidiController_Midi.midi_last_control_changed = control
            MidiController_Midi.midi_last_control_value = value
            MidiController_Midi.redraw_ui()

            found = (
                str(control) in MidiController_Midi.controller_property_mapping.keys())
            if found == False:
                MidiController_Midi.midi_control_to_map = control
            else:

                for mapping in MidiController_Midi.controller_property_mapping[str(control)]:
                    min = mapping["min"]
                    max = mapping["max"]
                    new_value = (((max - min) / 127) * value) + min
                    MidiController_Midi.update_data(mapping, new_value)

                MidiController_Midi.midi_control_to_map = control

        MidiController_Midi.midi_last_control_changed = control
        MidiController_Midi.midi_last_control_value = value
        MidiController_Midi.redraw_ui()

    def close():
        if MidiController_Midi.midi_open:
            MidiController_Midi.midi_input.cancel_callback()
            MidiController_Midi.midi_input.close_port()
            MidiController_Midi.midi_input.delete()
            MidiController_Midi.connected_controller = ""
            MidiController_Midi.connected_port = None
            MidiController_Midi.available_ports = None
            MidiController_Midi.midi_input = None
            MidiController_Midi.midi_open = False
            MidiController_Midi.midi = None
            MidiController_Midi.midi_last_control_changed = 0
            MidiController_Midi.midi_control_to_map = None
            MidiController_Midi.current_mapping_state = MidiController_Midi.State.NONE

            MidiController_Midi.property_register = {}
            print(
                f"Closed midi controller: {MidiController_Midi.connected_controller}")


class MidiController_OP_FindMidi(bpy.types.Operator):
    bl_idname = "wm.find_midi"
    bl_label = "Find Midi Controllers"

    def execute(self, context):
        MidiController_Midi.midi_input = rtmidi.MidiIn()
        MidiController_Midi.available_ports = MidiController_Midi.midi_input.get_ports()
        return {"FINISHED"}


class MidiController_OP_ConnectMidi(bpy.types.Operator):
    bl_idname = "wm.connect_midi"
    bl_label = "Connect Midi Controller"

    midi_port: bpy.props.IntProperty(default=0)

    def execute(self, context):
        MidiController_Midi.connected_port = self.midi_port
        MidiController_Midi.connected_controller = MidiController_Midi.available_ports[
            self.midi_port]
        MidiController_Midi.midi_input.open_port(self.midi_port)
        MidiController_Midi.midi_open = MidiController_Midi.midi_input.is_port_open()

        return {"FINISHED"}


class MidiController_OP_DisconnectMidi(bpy.types.Operator):
    bl_idname = "wm.disconnect_midi"
    bl_label = "Disconnect Midi Controller"

    def execute(self, context):
        if MidiController_Midi.midi_open:
            MidiController_Midi.close()
        return {"FINISHED"}


class MidiController_OP_SavePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.register_control"
    bl_label = "Save Property Mapping"

    min: bpy.props.FloatProperty(default=0)
    max: bpy.props.FloatProperty(default=0)
    controller_name: bpy.props.StringProperty(default="")
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if MidiController_Midi.current_mapping_state == MidiController_Midi.State.CONFIGURE_MAPPING:
            if self.cancel:
                MidiController_Midi.mapping_pending = None
                MidiController_Midi.mapping_pending = None
                MidiController_Midi.midi_control_to_map = None
                MidiController_Midi.current_mapping_state = MidiController_Midi.State.NONE
                return {"FINISHED"}

            MidiController_Midi.mapping_pending["min"] = self.min
            MidiController_Midi.mapping_pending["max"] = self.max
            if str(MidiController_Midi.midi_control_to_map) not in MidiController_Midi.controller_property_mapping:
                MidiController_Midi.controller_property_mapping[str(MidiController_Midi.midi_control_to_map)] = [
                    copy.copy(MidiController_Midi.mapping_pending)]
            else:
                MidiController_Midi.controller_property_mapping[str(
                    MidiController_Midi.midi_control_to_map)] += [copy.copy(MidiController_Midi.mapping_pending)]

            if self.controller_name != "":
                MidiController_Midi.controller_names[str(
                    MidiController_Midi.midi_control_to_map)] = self.controller_name

            MidiController_Midi.mapping_pending = None
            MidiController_Midi.midi_control_to_map = None
            MidiController_Midi.current_mapping_state = MidiController_Midi.State.REGISTER_CONTROL

        return {"FINISHED"}


class MidiController_OP_UpdatePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.update_mapping_control"
    bl_label = "Update Control Mapping"

    midi_control: bpy.props.StringProperty(default="")
    mapped_property: bpy.props.StringProperty(default="")
    index: bpy.props.IntProperty(default=0)
    min: bpy.props.FloatProperty(default=0)
    max: bpy.props.FloatProperty(default=0)
    controller_name: bpy.props.StringProperty(default="")
    edit: bpy.props.BoolProperty(default=False)
    save: bpy.props.BoolProperty(default=False)
    delete: bpy.props.BoolProperty(default=False)
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        print(
            f"Updating control: {self.min}, {self.max}, {self.edit}, {self.delete},  {self.save}, {self.cancel}")

        if self.edit:
            MidiController_Midi.editting_controller = self.midi_control
            MidiController_Midi.editting_mapped = self.mapped_property
            MidiController_Midi.editting_index = self.index
            MidiController_Midi.edit_state = MidiController_Midi.EditState.EDIT

        if self.save:
            MidiController_Midi.controller_property_mapping[MidiController_Midi.editting_controller][
                MidiController_Midi.editting_index]['min'] = self.min
            MidiController_Midi.controller_property_mapping[MidiController_Midi.editting_controller][
                MidiController_Midi.editting_index]['max'] = self.max
            MidiController_Midi.controller_names[str(
                MidiController_Midi.editting_controller)] = self.controller_name
            MidiController_Midi.editting_controller = None
            MidiController_Midi.editting_mapped = None
            MidiController_Midi.editting_index = None
            MidiController_Midi.edit_state = MidiController_Midi.EditState.NONE

        if self.delete:
            if len(MidiController_Midi.controller_property_mapping[MidiController_Midi.editting_controller]) > 1:
                MidiController_Midi.controller_property_mapping[MidiController_Midi.editting_controller].pop(
                    MidiController_Midi.editting_index)
            else:
                MidiController_Midi.controller_property_mapping.pop(
                    MidiController_Midi.editting_controller, None)
            MidiController_Midi.editting_controller = None
            MidiController_Midi.editting_mapped = None
            MidiController_Midi.editting_index = None
            MidiController_Midi.edit_state = MidiController_Midi.EditState.NONE

        if self.cancel:
            MidiController_Midi.editting_controller = None
            MidiController_Midi.editting_mapped = None
            MidiController_Midi.editting_index = None
            MidiController_Midi.edit_state = MidiController_Midi.EditState.NONE

        return {"FINISHED"}


class MidiController_OP_UpdateKeyFrameMapping(bpy.types.Operator):
    bl_idname = "wm.update_keyframe_control"
    bl_label = "Update Keyframe Mapping"

    start: bpy.props.BoolProperty(default=False)
    reset: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if self.start:
            MidiController_Midi.bind_control_state = MidiController_Midi.KeyFrameBindingState.PENDING
        elif self.reset:
            MidiController_Midi.bind_control_state = MidiController_Midi.KeyFrameBindingState.NONE
            MidiController_Midi.key_frame_control = None
        return {"FINISHED"}


class MidiController_OP_Save(bpy.types.Operator):
    bl_label = "Export Mapping"
    bl_idname = "wm.save_dialog"

    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        to_save = {
            "controller_names": MidiController_Midi.controller_names,
            "controller_mapping": MidiController_Midi.controller_property_mapping,
            "controller_keyframe_bind": {"controller": MidiController_Midi.key_frame_control, "velocity": MidiController_Midi.button_velocity_pressed}
        }
        with open(self.filepath, "w") as outfile:
            outfile.write(json.dumps(to_save))
        return {'FINISHED'}

    def invoke(self, context, event):
        self.filename = MidiController_Midi.connected_controller + ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MidiController_OP_Load(bpy.types.Operator):
    bl_label = "Import Mapping"
    bl_idname = "wm.load_dialog"

    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        with open(self.filepath, "r") as openfile:
            # Reading from json file
            json_object = json.load(openfile)
            MidiController_Midi.controller_names = json_object["controller_names"]
            MidiController_Midi.controller_property_mapping = json_object["controller_mapping"]
            MidiController_Midi.key_frame_control = json_object[
                "controller_keyframe_bind"]["controller"]
            MidiController_Midi.button_velocity_pressed = json_object[
                "controller_keyframe_bind"]["velocity"]
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_Device(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Midi Device"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        MidiController_Midi.screens = bpy.data.screens
        """define the layout of the panel"""
        box = layout.box()
        row = box.row()

        if MidiController_Midi.midi_input is not None:
            row.operator(MidiController_OP_DisconnectMidi.bl_idname)
            row = box.row()
            row.label(text="Click To Connect Device:")

            for port, name in enumerate(MidiController_Midi.available_ports):
                row = box.row()
                op = row.operator(
                    MidiController_OP_ConnectMidi.bl_idname, text=name)
                op.midi_port = port
        else:
            # row.operator("mesh.primitive_cube_add", text="Add Cube")
            row.operator(MidiController_OP_FindMidi.bl_idname)


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_Status(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Status"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if MidiController_Midi.midi_open:
            box = layout.box()
            row = box.row()
            row.label(text=f"Connected Device:")
            row = box.row()
            row.label(text=f"{str(MidiController_Midi.connected_controller)}")
            row = box.row()
            row.label(
                text=f"Last changed control: {MidiController_Midi.midi_last_control_changed}")
            row = box.row()
            row.label(
                text=f"Last value: {MidiController_Midi.midi_last_control_value}")
            row = box.row()
            row.label(
                text=f"Last velocity: {MidiController_Midi.midi_last_control_velocity}")
        else:
            layout.label(text="Connect Midi Device First!")


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_BindKeyFrameInput(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Bind Keyframe Input"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if MidiController_Midi.midi_open:
            layout.label(text="Bind A Control To Insert Keyframes")
            box = layout.box()
            row = box.row()
            row.label(
                text=f"Bound To: {MidiController_Midi.key_frame_control}")
            row = box.row()
            if MidiController_Midi.key_frame_control is None:
                op = row.operator(
                    MidiController_OP_UpdateKeyFrameMapping.bl_idname, text="Start Binding")
                op.reset = False
                op.start = True

                if MidiController_Midi.bind_control_state == MidiController_Midi.KeyFrameBindingState.PENDING:
                    row = box.row()
                    row.label(text="Press a button to bind!")

            else:
                op = row.operator(
                    MidiController_OP_UpdateKeyFrameMapping.bl_idname, text="Reset Bind")
                op.reset = True
                op.start = False
        else:
            layout.label(text="Connect Midi Device First!")


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_RegisterControllerMapping(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Register Controller Mapping"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if MidiController_Midi.midi_open:
            layout.label(text=f"Follow the instruction:")
            if MidiController_Midi.midi_control_to_map is None:
                box = layout.box()
                row = box.row()
                row.label(text=f"1. Touch a Midi Control!")
            else:
                if MidiController_Midi.current_mapping_state == MidiController_Midi.State.NONE:
                    MidiController_Midi.current_mapping_state = MidiController_Midi.State.REGISTER_CONTROL
                elif MidiController_Midi.current_mapping_state == MidiController_Midi.State.REGISTER_CONTROL:
                    box = layout.box()
                    controller_name = MidiController_Midi.midi_control_to_map
                    if MidiController_Midi.midi_control_to_map in MidiController_Midi.controller_names:
                        controller_name = MidiController_Midi.controller_names[
                            MidiController_Midi.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({MidiController_Midi.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(text=f"2. Now change object property to map!")
                elif MidiController_Midi.current_mapping_state == MidiController_Midi.State.CONFIGURE_MAPPING:

                    box = layout.box()
                    controller_name = MidiController_Midi.midi_control_to_map
                    if MidiController_Midi.midi_control_to_map in MidiController_Midi.controller_names:
                        controller_name = MidiController_Midi.controller_names[
                            MidiController_Midi.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({MidiController_Midi.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(
                        text=f"Mapping Property: {MidiController_Midi.mapping_pending['name']}")
                    row = box.row()
                    row.label(text=f"Edit other property to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(text=f"3. Configure Mapping")
                    row = box.row()
                    row.prop(context.scene, 'control_name_input',
                             text="Controller Name")
                    row = box.row()
                    row.prop(context.scene, 'min_input', text="Min")
                    row = box.row()
                    row.prop(context.scene, 'max_input', text="Max")
                    row = box.row()
                    op = row.operator(
                        MidiController_OP_SavePropertyMapping.bl_idname, text="Save")
                    op.controller_name = context.scene.control_name_input
                    op.min = context.scene.min_input
                    op.max = context.scene.max_input
                    op.cancel = False
                    row = box.row()
                    op = row.operator(
                        MidiController_OP_SavePropertyMapping.bl_idname, text="Cancel")
                    op.cancel = True
        else:
            layout.label(text="Connect Midi Device First!")


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_MappedControls(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Mapped Controls"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if MidiController_Midi.midi_open:

            box = layout.box()
            if MidiController_Midi.edit_state == MidiController_Midi.EditState.NONE:
                for controller, mapping in MidiController_Midi.controller_property_mapping.items():
                    box.separator(type='LINE')
                    nbox = box.box()
                    controller_names = controller
                    if controller in MidiController_Midi.controller_names:
                        controller_names = MidiController_Midi.controller_names[controller]
                    nbox.label(text=f"Controller: {controller_names}")
                    for index, mapped in enumerate(mapping):
                        row = nbox.row()
                        op = row.operator(
                            MidiController_OP_UpdatePropertyMapping.bl_idname, text=f"{mapped['name']}")
                        op.edit = True
                        op.save = False
                        op.delete = False
                        op.cancel = False
                        op.index = index
                        op.midi_control = controller
                        op.mapped_property = mapped['name']

            elif MidiController_Midi.edit_state == MidiController_Midi.EditState.EDIT:
                box.separator()
                row = box.row()
                controller_names = MidiController_Midi.midi_control_to_map
                if MidiController_Midi.midi_control_to_map in MidiController_Midi.controller_names:
                    controller_names = MidiController_Midi.controller_names[
                        MidiController_Midi.midi_control_to_map]

                row.label(
                    text=f"Control: {controller_names}, Mapped: {MidiController_Midi.editting_mapped}")
                row = box.row()
                row.label(text=f"Index: {MidiController_Midi.editting_index}")
                box.row()
                box.prop(context.scene, 'control_name_input',
                         text="Controller Name")
                box.row()
                box.prop(context.scene, 'min_input')
                box.row()
                box.prop(context.scene, 'max_input')
                row = box.row()
                op = row.operator(
                    MidiController_OP_UpdatePropertyMapping.bl_idname, text="Save")
                op.min = context.scene.min_input
                op.max = context.scene.max_input
                op.controller_name = context.scene.control_name_input
                op.edit = False
                op.save = True
                op.delete = False
                op.cancel = False
                op = row.operator(
                    MidiController_OP_UpdatePropertyMapping.bl_idname, text="Delete")
                op.edit = False
                op.save = False
                op.delete = True
                op.cancel = False
                row = box.row()
                op = row.operator(
                    MidiController_OP_UpdatePropertyMapping.bl_idname, text="Cancel")
                op.edit = False
                op.save = False
                op.delete = False
                op.cancel = True
        else:
            layout.label(text="Connect Midi Device First!")


# class naming convention ‘CATEGORY_PT_name’
class MidiController_PT_Panel_ImportExport(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Import / Export"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if MidiController_Midi.midi_open:
            layout.label(text="Import/Export")
            box = layout.box()
            row = box.row()
            row.operator(MidiController_OP_Save.bl_idname)
            row = box.row()
            row.operator(MidiController_OP_Load.bl_idname)
        else:
            layout.label(text="Connect Midi Device First!")

class MidiController_PT_Panel_InstallRequiredPackages(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Install Dependencies"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout
        print(context.region.width)
        text = [
            "Missing python dependency: ",
            "python-rtmidi",
            "---",
            "Please install this package",
            "By pressing the following button.",
            "---",
            "Note: this button starts the",
            "installation process of the",
            "wheels package bundled with the",
            "plugin (part of the zip file),",
            "it does NOT connect to the",
            "internet.",
            "---",
            "The install of this dependency",
            "is normally handled by blender,",
            "however this can silently fail",
            "due to blender not having permission",
            "to install the dependency in its",
            "required location, or due to",
            "a unknown bug with the install",
            "procedure.",
            "---",
            "It is possible to install the",
            "plugin correctly, if you start ,",
            "blender with admin rights. And",
            "reinstall this plugin (NOT ",
            "RECOMMENDED!!!).",
            "If you press the button below",
            "this plugin will install the ",
            "dependency in the plugins",
            "installation directory: ",
            MidiController_Dependencies.get_plugin_install_dir(),
            "which does not require admin",
            "rights.",
            "---",
            "To installation process will do",
            "the following",
            "1. Create a 'site-packages' directory",
            "   within this plugins install directory",
            "2. Select the systems correct wheels package",
            "   for the dependency delivered with this",
            "   plugin.",
            "3. Install the .whl package there and let",
            "   you save and restart blender so that",
            "   the plugin can find the dependency",
            "---",
            "If you do not trust",
            "this, please do not continue!",
            "---",
            "If you do continue, this is at your",
            "own risk. I as a developer am not responsible",
            "for any damages or undesired behavior that",
            "may follow."
        ]

        text_finished =[
            "Finished installing dependencies!",
            "---",
            "Reload blender OR press the",
            "following button to load",
            "the plugin! You won't see",
            "this window next time :D."
        ]

        text_finished_failed = [
            "Could not finish installing",
            "plugin, perhaps its a permission",
            "thing. In that case (not recommended)",
            "you could start blender as",
            "administrator.. or wait for",
            "blender to fix their wheels install",
            "for plugins (recommended)...",
        ]
        if MidiController_Dependencies.required_packages_installed == False:
            for line in text:
                row = layout.row()
                row.ui_units_y -= 7
                row.label(text=line)

            row = layout.row()
            row.operator(MidiController_OP_InstallRequiredPackages.bl_idname)

        elif MidiController_Dependencies.finished_installing_package == True and MidiController_Dependencies.required_packages_installed == True:
            for line in text_finished:
                row = layout.row()
                row.ui_units_y -= 7
                row.label(text=line)

            row = layout.row()
            row.operator(MidiController_OP_LoadPlugin.bl_idname)
        elif MidiController_Dependencies.finished_installing_package == True and MidiController_Dependencies.required_packages_installed == False:
            for line in text_finished_failed:
                row = layout.row()
                row.ui_units_y -= 7
                row.label(text=line)


        row.separator()
        layout.row()
        box = layout.box()
        for line in MidiController_Dependencies.progress_printer:
            row = box.row()
            row.ui_units_y -= 7
            row.label(text=line)

class MidiController_OP_InstallRequiredPackages(bpy.types.Operator):
    bl_label = "Install Packages"
    bl_idname = "wm.install_packages"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        MidiController_Dependencies.progress_printer += ["Selecting wheels package:"]
        package = MidiController_Dependencies.select_system_package()
        print(f"Found wheel package to install: {package}")
        MidiController_Dependencies.progress_printer += [package]

        if package is None:
            raise Exception("Could not find correct included wheel package for system configuration!")


        MidiController_Dependencies.progress_printer += ["Finding plugin site-packages!"]
        site_packages_dir = MidiController_Dependencies.get_packages_dir()
        MidiController_Dependencies.progress_printer += ["Found:", site_packages_dir]

        MidiController_Dependencies.progress_printer += ["Finding blender's python binary!"]
        python_path = MidiController_Dependencies.get_python_executable()
        MidiController_Dependencies.progress_printer += ["Found:", python_path]


        if python_path is not None:

            MidiController_Dependencies.progress_printer += ["Installing wheels into: "]
            MidiController_Dependencies.progress_printer += [site_packages_dir]
            result = subprocess.run([python_path, '-m', 'pip', 'install', '-t', site_packages_dir, package])
            print(result.returncode)

            MidiController_Dependencies.progress_printer += [f"Return code: {result.returncode}"]

            try:
                import rtmidi
                MidiController_Dependencies.progress_printer += [f"Success!"]
                MidiController_Dependencies.required_packages_installed = True
                MidiController_Dependencies.finished_installing_package = True
            except Exception as e:
                print(e)
                print("Failed installing :(")
                MidiController_Dependencies.progress_printer += [f"Failed installing :("]
                MidiController_Dependencies.finished_installing_package = True
        else:
            raise Exception("Did not find python binary to use!")
        return {'FINISHED'}

class MidiController_OP_LoadPlugin(bpy.types.Operator):
    bl_label = "Save & Restart Blender"
    bl_idname = "wm.restart_blender"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):

        blender_exe = bpy.app.binary_path
        head, tail = os.path.split(blender_exe)
        blender_launcher = os.path.join(head,"blender-launcher.exe")
        try:
            bpy.ops.wm.save_mainfile()
        except Exception as e:
            bpy.ops.wm.save_mainfile('INVOKE_AREA')
        subprocess.run([blender_launcher, "-con", "--python-expr", "import bpy; bpy.ops.wm.recover_last_session()"])
        bpy.ops.wm.quit_blender()
        return {'FINISHED'}


classes = (MidiController_PT_Panel_Device,
           MidiController_PT_Panel_Status,
           MidiController_PT_Panel_BindKeyFrameInput,
           MidiController_PT_Panel_RegisterControllerMapping,
           MidiController_PT_Panel_MappedControls,
           MidiController_PT_Panel_ImportExport,
           MidiController_OP_FindMidi,
           MidiController_OP_ConnectMidi,
           MidiController_OP_DisconnectMidi,
           MidiController_OP_SavePropertyMapping,
           MidiController_OP_UpdatePropertyMapping,
           MidiController_OP_UpdateKeyFrameMapping,
           MidiController_OP_Save,
           MidiController_OP_Load)


def register():

    if MidiController_Dependencies.required_packages_installed == False:
        bpy.utils.register_class(MidiController_PT_Panel_InstallRequiredPackages)
        bpy.utils.register_class(MidiController_OP_InstallRequiredPackages)
        bpy.utils.register_class(MidiController_OP_LoadPlugin)
        return


    MidiController_Midi.context = bpy.context
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.min_input = bpy.props.FloatProperty(name='Min')
    bpy.types.Scene.max_input = bpy.props.FloatProperty(name='Max')
    bpy.types.Scene.control_name_input = bpy.props.StringProperty(
        name='Controller Name')
    bpy.app.timers.register(
        MidiController_Midi.PropertyChangeProcess.listen_for_property_changes)
    bpy.app.timers.register(
        MidiController_Midi.ParseMidiMessages.parse_midi_messages)


def unregister():

    if MidiController_Dependencies.required_packages_installed == False or MidiController_Dependencies.finished_installing_package == True:
        bpy.utils.unregister_class(MidiController_PT_Panel_InstallRequiredPackages)
        bpy.utils.unregister_class(MidiController_OP_InstallRequiredPackages)
        bpy.utils.unregister_class(MidiController_OP_LoadPlugin)
        return

    if MidiController_Midi.midi_open:
        MidiController_Midi.close()
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.app.timers.unregister(
        MidiController_Midi.PropertyChangeProcess.listen_for_property_changes)
    bpy.app.timers.unregister(
        MidiController_Midi.ParseMidiMessages.parse_midi_messages)


# if __name__ == "__main__":
if __name__ == "__main__":
    register()
