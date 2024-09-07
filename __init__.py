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

import json
import copy
import bpy
import site
import os
import subprocess
from bpy.app.handlers import persistent

from .Dependencies import *
from .MidiControl import *


try:
    if bpy.app.version < (4, 2, 0):
        print("In older versions we install wheels in a local directory relative to the add-on")
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
    "blender": (3, 0, 0),
    "version": (0, 0, 5),
    "location": "",
    "warning": "",
    "category": "Generic"
}


global midicontrol_instance
midicontrol_instance = MidiController_Midi()


class MIDICONTROLLER_GenericProperties(bpy.types.PropertyGroup):
    bl_label = "generic_properties"
    generic_number_1: bpy.props.IntProperty(name="generic_number_1", default=0)
    generic_number_2: bpy.props.IntProperty(name="generic_number_2", default=0)
    generic_number_3: bpy.props.IntProperty(name="generic_number_3", default=0)
    generic_text_1: bpy.props.StringProperty(name="generic_text_1", default="")
    generic_text_2: bpy.props.StringProperty(name="generic_text_2", default="")
    generic_text_3: bpy.props.StringProperty(name="generic_text_3", default="")


class MIDICONTROLLER_OP_FindMidi(bpy.types.Operator):
    bl_idname = "wm.find_midi"
    bl_label = "Find Midi Controllers"
    bl_description = "Find connected midi controllers."

    def execute(self, context):

        scene = context.scene
        midi_control = scene.MidiControl

        midi_control.midi_input = rtmidi.MidiIn()
        midi_control.available_ports = midi_control.midi_input.get_ports()
        return {"FINISHED"}


class MIDICONTROLLER_OP_ConnectMidi(bpy.types.Operator):
    bl_idname = "wm.connect_midi"
    bl_label = "Connect Midi Controller"
    bl_description = "Connect midi controller."

    midi_port: bpy.props.IntProperty(default=0)

    def execute(self, context):

        scene = context.scene
        midi_control = scene.MidiControl

        scene = context.scene
        midi_control = scene.MidiControl
        midi_control.connected_port = self.midi_port
        midi_control.connected_controller = midi_control.available_ports[
            self.midi_port]
        midi_control.midi_input.open_port(self.midi_port)
        midi_control.midi_open = midi_control.midi_input.is_port_open()

        return {"FINISHED"}


class MIDICONTROLLER_OP_DisconnectMidi(bpy.types.Operator):
    bl_idname = "wm.disconnect_midi"
    bl_label = "Disconnect Midi Controller"
    bl_description = "Disconnect the currently connected midi controller."

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl
        if midi_control.midi_open:
            midi_control.close()
        return {"FINISHED"}


class MIDICONTROLLER_OP_SavePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.register_control"
    bl_label = "Save Property Mapping"
    bl_description = "Store the currently configured property mapping to the last active midi control."

    min: bpy.props.FloatProperty(default=0)
    max: bpy.props.FloatProperty(default=0)
    controller_name: bpy.props.StringProperty(default="")
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if midi_control.current_mapping_state == midi_control.State.CONFIGURE_MAPPING:
            if self.cancel:
                midi_control.mapping_pending = None
                midi_control.mapping_pending = None
                midi_control.midi_control_to_map = None
                midi_control.current_mapping_state = midi_control.State.NONE
                return {"FINISHED"}

            midi_control.mapping_pending["min"] = self.min
            midi_control.mapping_pending["max"] = self.max
            if str(midi_control.midi_control_to_map) not in midi_control.controller_property_mapping:
                midi_control.controller_property_mapping[str(midi_control.midi_control_to_map)] = [
                    copy.copy(midi_control.mapping_pending)]
            else:
                midi_control.controller_property_mapping[str(
                    midi_control.midi_control_to_map)] += [copy.copy(midi_control.mapping_pending)]

            if self.controller_name != "":
                midi_control.controller_names[str(
                    midi_control.midi_control_to_map)] = self.controller_name

            midi_control.mapping_pending = None
            midi_control.midi_control_to_map = None
            midi_control.current_mapping_state = midi_control.State.REGISTER_CONTROL

        # Very cheeky
        # midi_control.save_to_blend()

        return {"FINISHED"}


class MIDICONTROLLER_OP_UpdatePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.update_mapping_control"
    bl_label = "Update Control Mapping"
    bl_description = "Click to edit/save/delete/cancel the current mapped property to the midi controller."

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
        scene = context.scene
        midi_control = scene.MidiControl

        print(
            f"Updating control: {self.min}, {self.max}, {self.edit}, {self.delete},  {self.save}, {self.cancel}")

        if self.edit:
            midi_control.editting_controller = self.midi_control
            midi_control.editting_mapped = self.mapped_property
            midi_control.editting_index = self.index
            midi_control.edit_state = midi_control.EditState.EDIT

        if self.save:
            midi_control.controller_property_mapping[midi_control.editting_controller][
                midi_control.editting_index]['min'] = self.min
            midi_control.controller_property_mapping[midi_control.editting_controller][
                midi_control.editting_index]['max'] = self.max
            midi_control.controller_names[str(
                midi_control.editting_controller)] = self.controller_name
            midi_control.editting_controller = None
            midi_control.editting_mapped = None
            midi_control.editting_index = None
            midi_control.edit_state = midi_control.EditState.NONE

        if self.delete:
            if len(midi_control.controller_property_mapping[midi_control.editting_controller]) > 1:
                midi_control.controller_property_mapping[midi_control.editting_controller].pop(
                    midi_control.editting_index)
            else:
                midi_control.controller_property_mapping.pop(
                    midi_control.editting_controller, None)
            midi_control.editting_controller = None
            midi_control.editting_mapped = None
            midi_control.editting_index = None
            midi_control.edit_state = midi_control.EditState.NONE

        if self.cancel:
            midi_control.editting_controller = None
            midi_control.editting_mapped = None
            midi_control.editting_index = None
            midi_control.edit_state = midi_control.EditState.NONE

        # Very cheeky
        # midi_control.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_UpdateKeyFrameMapping(bpy.types.Operator):
    bl_idname = "wm.update_keyframe_control"
    bl_label = "Update Keyframe Mapping"
    bl_description = "Click to map a midi control which allows for inserting keyframes for all mapped properties for the selected objects."

    start: bpy.props.BoolProperty(default=False)
    reset: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if self.start:
            midi_control.key_frame_bind_control_state = midi_control.ControllerButtonBindingState.PENDING
        elif self.reset:
            midi_control.key_frame_bind_control_state = midi_control.ControllerButtonBindingState.NONE
            midi_control.key_frame_control = None
        # Very cheeky
        # midi_control.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_MapSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.map_selection_group"
    bl_label = "Map Selection Group"
    bl_description = "Click to map all currently selected objects to a control on your midi device!"

    name: bpy.props.StringProperty(default="")
    start: bpy.props.BoolProperty(default=False)
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if self.start:
            array = None
            for obj in bpy.context.selected_objects:
                if array is None:
                    array = [obj.name]
                else:
                    array += [obj.name]
            to_map = {
                "selected": array,
                "name": self.name
            }
            midi_control.selection_to_map = copy.copy(to_map)
            midi_control.select_group_bind_selection_state = midi_control.ControllerButtonBindingState.PENDING
        else:
            midi_control.selection_to_map = None
            midi_control.select_group_bind_selection_state = midi_control.ControllerButtonBindingState.NONE

        # Very cheeky
        # midi_control.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_DeleteSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.delete_selection_group"
    bl_label = "Delete"
    bl_description = "Remove selection group."

    controller: bpy.props.StringProperty(default="")

    def execute(self, context):

        scene = context.scene
        midi_control = scene.MidiControl

        try:
            midi_control.controller_selection_mapping.pop(
                self.controller, None)
        except Exception as e:
            print(f"Guess we leakin now...")
            print(e)
            pass
        # Very cheeky
        # midi_control.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_MapFrameSelection(bpy.types.Operator):
    bl_idname = "wm.map_frame_selection"
    bl_label = "Map Frame Select Controller"
    bl_description = "Configure increase/decrease frame actions to midi controllers."

    direction: bpy.props.StringProperty(default="")
    action: bpy.props.StringProperty(default="")
    frame_control_resolution: bpy.props.IntProperty(default=1)
    timeout: bpy.props.IntProperty(default=1)

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if self.action == "map_control":
            if midi_control.controllers_to_set_frame[self.direction]['state'] == midi_control.ControllerButtonBindingState.NONE:
                midi_control.controllers_to_set_frame[self.direction][
                    'state'] = midi_control.ControllerButtonBindingState.PENDING
            else:
                midi_control.controllers_to_set_frame[self.direction][
                    'state'] = midi_control.ControllerButtonBindingState.NONE
        elif self.action == "save_settings":
            midi_control.controllers_to_set_frame["frame_control_resolution"] = self.frame_control_resolution
            midi_control.controllers_to_set_frame["timeout"] = self.timeout
        elif self.action == "reset":
            midi_control.controllers_to_set_frame = {
                "increase": {
                    "state": midi_control.ControllerButtonBindingState.NONE,
                    "controller": None  # changes from the current frame into future frames
                },
                "decrease": {
                    "state": midi_control.ControllerButtonBindingState.NONE,
                    # changes from the current frame into the past frames.
                    "controller": None
                },
                # this is the resolution of the control (127/5 = 25.4 = 25 frames starting from the current frame)
                "frame_control_resolution": 5,
                # this allows for the system ot change the last frame position to the newly changed after this amount of time seeing no changes.
                "timeout": 1,
            }
        return {"FINISHED"}


class MIDICONTROLLER_OP_Save(bpy.types.Operator):
    bl_label = "Export Mapping"
    bl_idname = "wm.save_dialog"
    bl_description = "Save everything to a json file."

    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        to_save = {
            "controller_names": midi_control.controller_names,
            "controller_mapping": midi_control.controller_property_mapping,
            "selection_groups": {"mapping": midi_control.controller_selection_mapping, "velocity": midi_control.select_group_button_velocity_pressed},
            "controller_keyframe_bind": {"controller": midi_control.key_frame_control, "velocity": midi_control.keyframe_insert_button_velocity_pressed},
            "frame_control": midi_control.controllers_to_set_frame
        }
        with open(self.filepath, "w") as outfile:
            outfile.write(json.dumps(to_save))
        # Very cheeky
        # midi_control.save_to_blend()
        return {'FINISHED'}

    def invoke(self, context, event):
        scene = context.scene
        midi_control = scene.MidiControl
        self.filename = midi_control.connected_controller + ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MIDICONTROLLER_OP_Load(bpy.types.Operator):
    bl_label = "Import Mapping"
    bl_idname = "wm.load_dialog"
    bl_description = "Load settings from a json file."

    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        with open(self.filepath, "r") as openfile:
            # Reading from json file
            json_object = json.load(openfile)
            midi_control.controller_names = json_object["controller_names"]
            midi_control.controller_property_mapping = json_object[
                "controller_mapping"]
            midi_control.key_frame_control = json_object[
                "controller_keyframe_bind"]["controller"]
            midi_control.keyframe_insert_button_velocity_pressed = json_object[
                "controller_keyframe_bind"]["velocity"]

            if "selection_groups" in json_object:
                midi_control.controller_selection_mapping = json_object[
                    "selection_groups"]["mapping"]
                midi_control.select_group_button_velocity_pressed = json_object[
                    "selection_groups"]["velocity"]

            if "frame_control" in json_object:
                midi_control.controllers_to_set_frame = json_object[
                    "frame_control"]
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_Device(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Midi Device"  # found at the top of the Panel
    bl_description = "Find/Connect/Disconnect Midi Device."

    def draw(self, context):
        scene = context.scene
        midi_control = scene.MidiControl
        layout = self.layout

        # Very cheeky
        # midi_control.save_to_blend()

        midi_control.screens = bpy.data.screens
        """define the layout of the panel"""
        box = layout.box()
        row = box.row()

        if midi_control.midi_input is not None:
            if midi_control.midi_open:
                row.operator(MIDICONTROLLER_OP_DisconnectMidi.bl_idname)
            else:
                row = box.row()
                row.label(text="Click To Connect Device:")
                for port, name in enumerate(midi_control.available_ports):
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_ConnectMidi.bl_idname, text=name)
                    op.midi_port = port
        else:
            # row.operator("mesh.primitive_cube_add", text="Add Cube")
            row.operator(MIDICONTROLLER_OP_FindMidi.bl_idname)


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_Status(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Status"  # found at the top of the Panel
    bl_description = "Status/data from connected midi device."

    def draw(self, context):

        scene = context.scene
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            box = layout.box()
            row = box.row()
            row.label(text=f"Connected Device:")
            row = box.row()
            row.label(
                text=f"{str(midi_control.connected_controller)}")
            row = box.row()
            row.label(
                text=f"Last changed control: {midi_control.midi_last_control_changed}")
            row = box.row()
            row.label(
                text=f"Last value: {midi_control.midi_last_control_value}")
            row = box.row()
            row.label(
                text=f"Last velocity: {midi_control.midi_last_control_velocity}")
        else:
            layout.label(text="Connect Midi Device First!")


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_BindKeyFrameInput(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Bind Keyframe Input"  # found at the top of the Panel
    bl_description = "Configure midi control for inserting keyframes."

    def draw(self, context):

        scene = context.scene
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text="Bind A Control To Insert Keyframes")
            box = layout.box()
            row = box.row()
            row.label(
                text=f"Bound To: {midi_control.key_frame_control}")
            row = box.row()
            if midi_control.key_frame_control is None:
                op = row.operator(
                    MIDICONTROLLER_OP_UpdateKeyFrameMapping.bl_idname, text="Start Binding")
                op.reset = False
                op.start = True

                if midi_control.key_frame_bind_control_state == midi_control.ControllerButtonBindingState.PENDING:
                    row = box.row()
                    row.label(text="Press a button to bind!")

            else:
                op = row.operator(
                    MIDICONTROLLER_OP_UpdateKeyFrameMapping.bl_idname, text="Reset Bind")
                op.reset = True
                op.start = False
        else:
            layout.label(text="Connect Midi Device First!")


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_RegisterControllerMapping(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Register Controller Mapping"  # found at the top of the Panel
    bl_description = "Map property to midi control."

    def draw(self, context):

        scene = context.scene
        generic_properties = scene.generic_properties
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text=f"Follow the instruction:")
            if midi_control.mapping_error is not None:
                box = layout.box()
                row = box.row()
                row.label(text=f"Error Mapping:")
                row = box.row()
                row.label(text=midi_control.mapping_error)

            if midi_control.midi_control_to_map is None:
                box = layout.box()
                row = box.row()
                row.label(text=f"1. Touch a Midi Control!")
            else:
                if midi_control.current_mapping_state == midi_control.State.NONE:
                    midi_control.current_mapping_state = midi_control.State.REGISTER_CONTROL
                elif midi_control.current_mapping_state == midi_control.State.REGISTER_CONTROL:
                    box = layout.box()
                    controller_name = midi_control.midi_control_to_map
                    if midi_control.midi_control_to_map in midi_control.controller_names:
                        controller_name = midi_control.controller_names[
                            midi_control.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({midi_control.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(text=f"2. Now change object property to map!")
                elif midi_control.current_mapping_state == midi_control.State.CONFIGURE_MAPPING:

                    box = layout.box()
                    controller_name = midi_control.midi_control_to_map
                    if midi_control.midi_control_to_map in midi_control.controller_names:
                        controller_name = midi_control.controller_names[
                            midi_control.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({midi_control.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(
                        text=f"Mapping Property: {midi_control.mapping_pending['name']}")
                    row = box.row()
                    row.label(text=f"Edit other property to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(text=f"3. Configure Mapping")
                    row = box.row()
                    row.prop(generic_properties, 'generic_text_1',
                             text="Controller Name")
                    row = box.row()
                    row.prop(generic_properties,
                             'generic_number_1', text="Min")
                    row = box.row()
                    row.prop(generic_properties,
                             'generic_number_2', text="Max")
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Apply")
                    op.controller_name = generic_properties.generic_text_1
                    op.min = generic_properties.generic_number_1
                    op.max = generic_properties.generic_number_2
                    op.cancel = False
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Cancel")
                    op.cancel = True
        else:
            layout.label(text="Connect Midi Device First!")


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_MappedControls(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Mapped Controls"  # found at the top of the Panel
    bl_description = "Manage mapped properties to midi controls."

    def draw(self, context):
        scene = context.scene
        generic_properties = scene.generic_properties
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:

            box = layout.box()
            if midi_control.edit_state == midi_control.EditState.NONE:
                for controller, mapping in midi_control.controller_property_mapping.items():
                    box.separator()
                    nbox = box.box()
                    controller_names = controller
                    if controller in midi_control.controller_names:
                        controller_names = midi_control.controller_names[controller]
                    nbox.label(text=f"Controller: {controller_names}")
                    for index, mapped in enumerate(mapping):
                        row = nbox.row()
                        op = row.operator(
                            MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text=f"{mapped['name']}")
                        op.edit = True
                        op.save = False
                        op.delete = False
                        op.cancel = False
                        op.index = index
                        op.midi_control = controller
                        op.mapped_property = mapped['name']

            elif midi_control.edit_state == midi_control.EditState.EDIT:
                box.separator()
                row = box.row()
                controller_names = midi_control.midi_control_to_map
                if midi_control.midi_control_to_map in midi_control.controller_names:
                    controller_names = midi_control.controller_names[
                        midi_control.midi_control_to_map]

                row.label(
                    text=f"Control: {controller_names}, Mapped: {midi_control.editting_mapped}")
                row = box.row()
                row.label(
                    text=f"Index: {midi_control.editting_index}")
                box.row()
                row.label(
                    text=f"Current Min: {midi_control.controller_property_mapping[midi_control.editting_controller][midi_control.editting_index]['min']}, Max: {midi_control.controller_property_mapping[midi_control.editting_controller][midi_control.editting_index]['max']}")
                box.row()
                box.prop(generic_properties, 'generic_text_1',
                         text="Controller Name")
                box.row()
                box.prop(generic_properties, 'generic_number_1',
                         text="Min")
                box.row()
                box.prop(generic_properties, 'generic_number_2',
                         text="Max")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text="Apply")
                op.min = generic_properties.generic_number_1
                op.max = generic_properties.generic_number_2
                op.controller_name = generic_properties.generic_text_1
                op.edit = False
                op.save = True
                op.delete = False
                op.cancel = False
                op = row.operator(
                    MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text="Delete")
                op.edit = False
                op.save = False
                op.delete = True
                op.cancel = False
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text="Cancel")
                op.edit = False
                op.save = False
                op.delete = False
                op.cancel = True
        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_SelectionGroups(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Selection Groups"  # found at the top of the Panel
    bl_description = "Manage selection groups bound to midi controls."

    def draw(self, context):

        scene = context.scene
        generic_properties = scene.generic_properties
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text="Map Current Selection")
            if midi_control.select_group_bind_selection_state != midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                row = box.row()
                row.label(text="Selection Group Name:")
                row = box.row()
                row.prop(generic_properties, 'generic_text_1', text="Name")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname)
                op.name = f"Group: {len(midi_control.controller_selection_mapping.keys())}"
                if generic_properties.generic_text_1 != "":
                    op.name = generic_properties.generic_text_1
                op.start = True
                op.cancel = False
            else:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Press button to map: {midi_control.selection_to_map['name']}!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname, text=f"Cancel")
                op.cancel = True
                op.start = False

            row = layout.row()
            row.label(text="Current Mappings")
            row = layout.row()
            row.separator()

            for controller, mapped in midi_control.controller_selection_mapping.items():
                row = layout.row()
                nbox = row.box()
                nbox.label(text=f"{mapped['name']}")
                row = nbox.row()
                op = row.operator(
                    MIDICONTROLLER_OP_DeleteSelectionGroup.bl_idname, text=f"Delete")
                op.controller = controller

        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_FramePosition(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Frame Position"  # found at the top of the Panel
    bl_description = "Manage midi controls which can change the frame position."

    def draw(self, context):

        scene = context.scene
        generic_properties = scene.generic_properties
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text="Control Frame Position")
            if midi_control.controllers_to_set_frame["increase"]["state"] == midi_control.ControllerButtonBindingState.NONE:
                box = layout.box()
                row = box.row()
                row.label(text="Increase Control:")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Map Control")
                op.action = "map_control"
                op.direction = "increase"
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
            elif midi_control.controllers_to_set_frame["increase"]["state"] == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind increase action!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
            elif midi_control.controllers_to_set_frame["decrease"]["state"] == midi_control.ControllerButtonBindingState.NONE:
                box = layout.box()
                row = box.row()
                row.label(text="Decrease Control:")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Map Control")
                op.action = "map_control"
                op.direction = "decrease"
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
            elif midi_control.controllers_to_set_frame["decrease"]["state"] == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind decrease action!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"

            box = layout.box()
            row = box.row()
            row.label(text="General Settings:")
            row = box.row()
            row.label(
                text=f"Current Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")
            row = box.row()
            row.label(
                text=f"Current Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")
            row = box.row()
            row.label(
                text=f"Current Resolution: {midi_control.controllers_to_set_frame['frame_control_resolution']}")
            row = box.row()
            row.label(
                text=f"Current Timeout: {midi_control.controllers_to_set_frame['timeout']}")
            row = box.row()
            row.label(
                text=f"Current Frame Position: {midi_control.controllers_to_set_frame_current_frame}")
            row = box.row()
            row.label(
                text=f"Frame Position Reset Timeout: {midi_control.controllers_to_set_frame_timeout}")
            row = box.row()
            row.prop(generic_properties, 'generic_number_1', text="Resolution")
            row = box.row()
            row.prop(generic_properties, 'generic_number_2',
                     text="Frame Position Reset Timeout")
            row = box.row()
            op = row.operator(
                MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Save")
            op.frame_control_resolution = generic_properties.generic_number_1
            op.timeout = generic_properties.generic_number_2
            op.action = "save_settings"
            row = box.row()
            op = row.operator(
                MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
            op.action = "reset"
            row = box.row()

        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_ImportExport(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Import / Export"  # found at the top of the Panel
    bl_description = "Import/Export midicontrol settings."

    def draw(self, context):

        scene = context.scene
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text="Import/Export")
            box = layout.box()
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Save.bl_idname)
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Load.bl_idname)
        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_InstallRequiredPackages(bpy.types.Panel):

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

        text_finished = [
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
            row.operator(MIDICONTROLLER_OP_InstallRequiredPackages.bl_idname)

        elif MidiController_Dependencies.finished_installing_package == True and MidiController_Dependencies.required_packages_installed == True:
            for line in text_finished:
                row = layout.row()
                row.ui_units_y -= 7
                row.label(text=line)

            row = layout.row()
            row.operator(MIDICONTROLLER_OP_LoadPlugin.bl_idname)
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


class MIDICONTROLLER_OP_InstallRequiredPackages(bpy.types.Operator):
    bl_label = "Install Packages"
    bl_idname = "wm.install_packages"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):

        MidiController_Dependencies.progress_printer += [
            "Selecting wheels package:"]
        package = MidiController_Dependencies.select_system_package()
        print(f"Found wheel package to install: {package}")
        MidiController_Dependencies.progress_printer += [package]

        if package is None:
            raise Exception(
                "Could not find correct included wheel package for system configuration!")

        MidiController_Dependencies.progress_printer += [
            "Finding plugin site-packages!"]
        site_packages_dir = MidiController_Dependencies.get_packages_dir()
        MidiController_Dependencies.progress_printer += [
            "Found:", site_packages_dir]

        MidiController_Dependencies.progress_printer += [
            "Finding blender's python binary!"]
        python_path = MidiController_Dependencies.get_python_executable()
        MidiController_Dependencies.progress_printer += ["Found:", python_path]

        if python_path is not None:

            MidiController_Dependencies.progress_printer += [
                "Installing wheels into: "]
            MidiController_Dependencies.progress_printer += [site_packages_dir]
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '-t', site_packages_dir, package])
            print(result.returncode)

            MidiController_Dependencies.progress_printer += [
                f"Return code: {result.returncode}"]

            try:
                import rtmidi
                MidiController_Dependencies.progress_printer += [f"Success!"]
                MidiController_Dependencies.required_packages_installed = True
                MidiController_Dependencies.finished_installing_package = True
            except Exception as e:
                print(e)
                print("Failed installing :(")
                MidiController_Dependencies.progress_printer += [
                    f"Failed installing :("]
                MidiController_Dependencies.finished_installing_package = True
        else:
            raise Exception("Did not find python binary to use!")
        return {'FINISHED'}


class MIDICONTROLLER_OP_LoadPlugin(bpy.types.Operator):
    bl_label = "Save & Restart Blender"
    bl_idname = "wm.restart_blender"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):

        blender_exe = bpy.app.binary_path
        head, tail = os.path.split(blender_exe)
        blender_launcher = os.path.join(head, "blender-launcher.exe")
        try:
            bpy.ops.wm.save_mainfile()
        except Exception as e:
            bpy.ops.wm.save_mainfile('INVOKE_AREA')
        subprocess.run([blender_launcher, "-con", "--python-expr",
                       "import bpy; bpy.ops.wm.recover_last_session()"])
        bpy.ops.wm.quit_blender()
        return {'FINISHED'}


classes = (MIDICONTROLLER_GenericProperties,
           MIDICONTROLLER_PT_Panel_Device,
           MIDICONTROLLER_PT_Panel_Status,
           MIDICONTROLLER_PT_Panel_BindKeyFrameInput,
           MIDICONTROLLER_PT_Panel_RegisterControllerMapping,
           MIDICONTROLLER_PT_Panel_MappedControls,
           MIDICONTROLLER_PT_Panel_SelectionGroups,
           MIDICONTROLLER_PT_Panel_FramePosition,
           MIDICONTROLLER_PT_Panel_ImportExport,
           MIDICONTROLLER_OP_FindMidi,
           MIDICONTROLLER_OP_ConnectMidi,
           MIDICONTROLLER_OP_DisconnectMidi,
           MIDICONTROLLER_OP_SavePropertyMapping,
           MIDICONTROLLER_OP_UpdatePropertyMapping,
           MIDICONTROLLER_OP_UpdateKeyFrameMapping,
           MIDICONTROLLER_OP_MapSelectionGroup,
           MIDICONTROLLER_OP_DeleteSelectionGroup,
           MIDICONTROLLER_OP_MapFrameSelection,
           MIDICONTROLLER_OP_Save,
           MIDICONTROLLER_OP_Load)


def updatetimer():
    # print("update timer called")
    global midicontrol_instance
    midicontrol_instance.obj_prop_change_update()
    midicontrol_instance.parse_midi_messages_update()
    midicontrol_instance.frame_update()
    return midicontrol_instance.midi_update_rate


@persistent
def load_post(dummy):
    print("Finished load")
    try:
        bpy.app.timers.unregister(updatetimer)
    except Exception as e:
        print("Failed to unregister timer")
        print(e)
    bpy.app.timers.register(updatetimer)


def register():
    print("registering plugin")
    if MidiController_Dependencies.required_packages_installed == False:
        bpy.utils.register_class(
            MIDICONTROLLER_PT_Panel_InstallRequiredPackages)
        bpy.utils.register_class(MIDICONTROLLER_OP_InstallRequiredPackages)
        bpy.utils.register_class(MIDICONTROLLER_OP_LoadPlugin)
        return

    global midicontrol_instance
    midicontrol_instance.context = bpy.context
    bpy.types.Scene.MidiControl = midicontrol_instance

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"Could not register: {cls.bl_label}")
            print(e)

    bpy.types.Scene.generic_properties = bpy.props.PointerProperty(
        type=MIDICONTROLLER_GenericProperties)
    bpy.app.timers.register(updatetimer)

    bpy.app.handlers.load_post.append(load_post)


def unregister():
    try:
        if MidiController_Dependencies.required_packages_installed == False or MidiController_Dependencies.finished_installing_package == True:
            print("finished installing required packages")
            bpy.utils.unregister_class(
                MIDICONTROLLER_PT_Panel_InstallRequiredPackages)
            bpy.utils.unregister_class(
                MIDICONTROLLER_OP_InstallRequiredPackages)
            bpy.utils.unregister_class(MIDICONTROLLER_OP_LoadPlugin)
            return
    except Exception as e:
        print("Failed to unregister dependency installer")
        print(e)

    global midicontrol_instance

    try:
        if midicontrol_instance.midi_open:
            midicontrol_instance.close()
            print("Midi controller closed properly")
    except Exception as e:
        print("Failed to close midi")
        print(e)

    try:
        bpy.app.timers.unregister(updatetimer)
    except Exception as e:
        print("Failed to unregister timer")
        print(e)

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Could not unregister: {cls.bl_label}")
            print(e)

    del bpy.types.Scene.MidiControl


# # if __name__ == "__main__":
# if __name__ == "__main__":
#     register()
