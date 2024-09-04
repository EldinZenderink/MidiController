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
    "blender": (4, 2, 0),
    "version": (0, 0, 4),
    "location": "",
    "warning": "",
    "category": "Generic"
}


global midicontrol_instance
midicontrol_instance = MidiController_Midi()


class MIDICONTROLLER_OP_FindMidi(bpy.types.Operator):
    bl_idname = "wm.find_midi"
    bl_label = "Find Midi Controllers"

    def execute(self, context):
        bpy.types.Scene.MidiControl.midi_input = rtmidi.MidiIn()
        bpy.types.Scene.MidiControl.available_ports = bpy.types.Scene.MidiControl.midi_input.get_ports()
        return {"FINISHED"}


class MIDICONTROLLER_OP_ConnectMidi(bpy.types.Operator):
    bl_idname = "wm.connect_midi"
    bl_label = "Connect Midi Controller"

    midi_port: bpy.props.IntProperty(default=0)

    def execute(self, context):
        bpy.types.Scene.MidiControl.connected_port = self.midi_port
        bpy.types.Scene.MidiControl.connected_controller = bpy.types.Scene.MidiControl.available_ports[
            self.midi_port]
        bpy.types.Scene.MidiControl.midi_input.open_port(self.midi_port)
        bpy.types.Scene.MidiControl.midi_open = bpy.types.Scene.MidiControl.midi_input.is_port_open()

        return {"FINISHED"}


class MIDICONTROLLER_OP_DisconnectMidi(bpy.types.Operator):
    bl_idname = "wm.disconnect_midi"
    bl_label = "Disconnect Midi Controller"

    def execute(self, context):
        if bpy.types.Scene.MidiControl.midi_open:
            bpy.types.Scene.MidiControl.close()
        return {"FINISHED"}


class MIDICONTROLLER_OP_SavePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.register_control"
    bl_label = "Save Property Mapping"

    min: bpy.props.FloatProperty(default=0)
    max: bpy.props.FloatProperty(default=0)
    controller_name: bpy.props.StringProperty(default="")
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if bpy.types.Scene.MidiControl.current_mapping_state == bpy.types.Scene.MidiControl.State.CONFIGURE_MAPPING:
            if self.cancel:
                bpy.types.Scene.MidiControl.mapping_pending = None
                bpy.types.Scene.MidiControl.mapping_pending = None
                bpy.types.Scene.MidiControl.midi_control_to_map = None
                bpy.types.Scene.MidiControl.current_mapping_state = bpy.types.Scene.MidiControl.State.NONE
                return {"FINISHED"}

            bpy.types.Scene.MidiControl.mapping_pending["min"] = self.min
            bpy.types.Scene.MidiControl.mapping_pending["max"] = self.max
            if str(bpy.types.Scene.MidiControl.midi_control_to_map) not in bpy.types.Scene.MidiControl.controller_property_mapping:
                bpy.types.Scene.MidiControl.controller_property_mapping[str(bpy.types.Scene.MidiControl.midi_control_to_map)] = [
                    copy.copy(bpy.types.Scene.MidiControl.mapping_pending)]
            else:
                bpy.types.Scene.MidiControl.controller_property_mapping[str(
                    bpy.types.Scene.MidiControl.midi_control_to_map)] += [copy.copy(bpy.types.Scene.MidiControl.mapping_pending)]

            if self.controller_name != "":
                bpy.types.Scene.MidiControl.controller_names[str(
                    bpy.types.Scene.MidiControl.midi_control_to_map)] = self.controller_name

            bpy.types.Scene.MidiControl.mapping_pending = None
            bpy.types.Scene.MidiControl.midi_control_to_map = None
            bpy.types.Scene.MidiControl.current_mapping_state = bpy.types.Scene.MidiControl.State.REGISTER_CONTROL

        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()

        return {"FINISHED"}


class MIDICONTROLLER_OP_UpdatePropertyMapping(bpy.types.Operator):
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
            bpy.types.Scene.MidiControl.editting_controller = self.midi_control
            bpy.types.Scene.MidiControl.editting_mapped = self.mapped_property
            bpy.types.Scene.MidiControl.editting_index = self.index
            bpy.types.Scene.MidiControl.edit_state = bpy.types.Scene.MidiControl.EditState.EDIT

        if self.save:
            bpy.types.Scene.MidiControl.controller_property_mapping[bpy.types.Scene.MidiControl.editting_controller][
                bpy.types.Scene.MidiControl.editting_index]['min'] = self.min
            bpy.types.Scene.MidiControl.controller_property_mapping[bpy.types.Scene.MidiControl.editting_controller][
                bpy.types.Scene.MidiControl.editting_index]['max'] = self.max
            bpy.types.Scene.MidiControl.controller_names[str(
                bpy.types.Scene.MidiControl.editting_controller)] = self.controller_name
            bpy.types.Scene.MidiControl.editting_controller = None
            bpy.types.Scene.MidiControl.editting_mapped = None
            bpy.types.Scene.MidiControl.editting_index = None
            bpy.types.Scene.MidiControl.edit_state = bpy.types.Scene.MidiControl.EditState.NONE

        if self.delete:
            if len(bpy.types.Scene.MidiControl.controller_property_mapping[bpy.types.Scene.MidiControl.editting_controller]) > 1:
                bpy.types.Scene.MidiControl.controller_property_mapping[bpy.types.Scene.MidiControl.editting_controller].pop(
                    bpy.types.Scene.MidiControl.editting_index)
            else:
                bpy.types.Scene.MidiControl.controller_property_mapping.pop(
                    bpy.types.Scene.MidiControl.editting_controller, None)
            bpy.types.Scene.MidiControl.editting_controller = None
            bpy.types.Scene.MidiControl.editting_mapped = None
            bpy.types.Scene.MidiControl.editting_index = None
            bpy.types.Scene.MidiControl.edit_state = bpy.types.Scene.MidiControl.EditState.NONE

        if self.cancel:
            bpy.types.Scene.MidiControl.editting_controller = None
            bpy.types.Scene.MidiControl.editting_mapped = None
            bpy.types.Scene.MidiControl.editting_index = None
            bpy.types.Scene.MidiControl.edit_state = bpy.types.Scene.MidiControl.EditState.NONE

        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_UpdateKeyFrameMapping(bpy.types.Operator):
    bl_idname = "wm.update_keyframe_control"
    bl_label = "Update Keyframe Mapping"

    start: bpy.props.BoolProperty(default=False)
    reset: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if self.start:
            bpy.types.Scene.MidiControl.bind_control_state = bpy.types.Scene.MidiControl.ControllerButtonBindingState.PENDING
        elif self.reset:
            bpy.types.Scene.MidiControl.bind_control_state = bpy.types.Scene.MidiControl.ControllerButtonBindingState.NONE
            bpy.types.Scene.MidiControl.key_frame_control = None
        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_MapSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.map_selection_group"
    bl_label = "Map Selection Group"

    name: bpy.props.StringProperty(default="")
    start: bpy.props.BoolProperty(default=False)
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):
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
            bpy.types.Scene.MidiControl.selection_to_map = copy.copy(to_map)
            bpy.types.Scene.MidiControl.bind_selection_state = bpy.types.Scene.MidiControl.ControllerButtonBindingState.PENDING
        else:
            bpy.types.Scene.MidiControl.selection_to_map = None
            bpy.types.Scene.MidiControl.bind_selection_state = bpy.types.Scene.MidiControl.ControllerButtonBindingState.NONE

        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_DeleteSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.delete_selection_group"
    bl_label = "Delete"

    controller: bpy.props.StringProperty(default="")

    def execute(self, context):
        try:
            bpy.types.Scene.MidiControl.controller_selection_mapping.pop(
                self.controller, None)
        except Exception as e:
            print(f"Guess we leakin now...")
            print(e)
            pass
        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()
        return {"FINISHED"}


class MIDICONTROLLER_OP_Save(bpy.types.Operator):
    bl_label = "Export Mapping"
    bl_idname = "wm.save_dialog"

    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        to_save = {
            "controller_names": bpy.types.Scene.MidiControl.controller_names,
            "controller_mapping": bpy.types.Scene.MidiControl.controller_property_mapping,
            "selection_groups": bpy.types.Scene.MidiControl.controller_selection_mapping,
            "controller_keyframe_bind": {"controller": bpy.types.Scene.MidiControl.key_frame_control, "velocity": bpy.types.Scene.MidiControl.button_velocity_pressed}
        }
        with open(self.filepath, "w") as outfile:
            outfile.write(json.dumps(to_save))
        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()
        return {'FINISHED'}

    def invoke(self, context, event):
        self.filename = bpy.types.Scene.MidiControl.connected_controller + ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MIDICONTROLLER_OP_Load(bpy.types.Operator):
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
            bpy.types.Scene.MidiControl.controller_names = json_object["controller_names"]
            bpy.types.Scene.MidiControl.controller_property_mapping = json_object[
                "controller_mapping"]
            if "selection_groups" in json_object:
                bpy.types.Scene.MidiControl.controller_selection_mapping = json_object[
                    "selection_groups"]
            bpy.types.Scene.MidiControl.key_frame_control = json_object[
                "controller_keyframe_bind"]["controller"]
            bpy.types.Scene.MidiControl.button_velocity_pressed = json_object[
                "controller_keyframe_bind"]["velocity"]
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

    def draw(self, context):
        layout = self.layout

        # Very cheeky
        # bpy.types.Scene.MidiControl.save_to_blend()

        bpy.types.Scene.MidiControl.screens = bpy.data.screens
        """define the layout of the panel"""
        box = layout.box()
        row = box.row()

        if bpy.types.Scene.MidiControl.midi_input is not None:
            if bpy.types.Scene.MidiControl.midi_open:
                row.operator(MIDICONTROLLER_OP_DisconnectMidi.bl_idname)
            else:
                row = box.row()
                row.label(text="Click To Connect Device:")
                for port, name in enumerate(bpy.types.Scene.MidiControl.available_ports):
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

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:
            box = layout.box()
            row = box.row()
            row.label(text=f"Connected Device:")
            row = box.row()
            row.label(
                text=f"{str(bpy.types.Scene.MidiControl.connected_controller)}")
            row = box.row()
            row.label(
                text=f"Last changed control: {bpy.types.Scene.MidiControl.midi_last_control_changed}")
            row = box.row()
            row.label(
                text=f"Last value: {bpy.types.Scene.MidiControl.midi_last_control_value}")
            row = box.row()
            row.label(
                text=f"Last velocity: {bpy.types.Scene.MidiControl.midi_last_control_velocity}")
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

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:
            layout.label(text="Bind A Control To Insert Keyframes")
            box = layout.box()
            row = box.row()
            row.label(
                text=f"Bound To: {bpy.types.Scene.MidiControl.key_frame_control}")
            row = box.row()
            if bpy.types.Scene.MidiControl.key_frame_control is None:
                op = row.operator(
                    MIDICONTROLLER_OP_UpdateKeyFrameMapping.bl_idname, text="Start Binding")
                op.reset = False
                op.start = True

                if bpy.types.Scene.MidiControl.bind_control_state == bpy.types.Scene.MidiControl.ControllerButtonBindingState.PENDING:
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

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:
            layout.label(text=f"Follow the instruction:")
            if bpy.types.Scene.MidiControl.midi_control_to_map is None:
                box = layout.box()
                row = box.row()
                row.label(text=f"1. Touch a Midi Control!")
            else:
                if bpy.types.Scene.MidiControl.current_mapping_state == bpy.types.Scene.MidiControl.State.NONE:
                    bpy.types.Scene.MidiControl.current_mapping_state = bpy.types.Scene.MidiControl.State.REGISTER_CONTROL
                elif bpy.types.Scene.MidiControl.current_mapping_state == bpy.types.Scene.MidiControl.State.REGISTER_CONTROL:
                    box = layout.box()
                    controller_name = bpy.types.Scene.MidiControl.midi_control_to_map
                    if bpy.types.Scene.MidiControl.midi_control_to_map in bpy.types.Scene.MidiControl.controller_names:
                        controller_name = bpy.types.Scene.MidiControl.controller_names[
                            bpy.types.Scene.MidiControl.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({bpy.types.Scene.MidiControl.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(text=f"2. Now change object property to map!")
                elif bpy.types.Scene.MidiControl.current_mapping_state == bpy.types.Scene.MidiControl.State.CONFIGURE_MAPPING:

                    box = layout.box()
                    controller_name = bpy.types.Scene.MidiControl.midi_control_to_map
                    if bpy.types.Scene.MidiControl.midi_control_to_map in bpy.types.Scene.MidiControl.controller_names:
                        controller_name = bpy.types.Scene.MidiControl.controller_names[
                            bpy.types.Scene.MidiControl.midi_control_to_map]
                    row = box.row()
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({bpy.types.Scene.MidiControl.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch other control to change!")
                    box = layout.box()
                    row = box.row()
                    row.label(
                        text=f"Mapping Property: {bpy.types.Scene.MidiControl.mapping_pending['name']}")
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
                        MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Save")
                    op.controller_name = context.scene.control_name_input
                    op.min = context.scene.min_input
                    op.max = context.scene.max_input
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

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:

            box = layout.box()
            if bpy.types.Scene.MidiControl.edit_state == bpy.types.Scene.MidiControl.EditState.NONE:
                for controller, mapping in bpy.types.Scene.MidiControl.controller_property_mapping.items():
                    box.separator()
                    nbox = box.box()
                    controller_names = controller
                    if controller in bpy.types.Scene.MidiControl.controller_names:
                        controller_names = bpy.types.Scene.MidiControl.controller_names[controller]
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

            elif bpy.types.Scene.MidiControl.edit_state == bpy.types.Scene.MidiControl.EditState.EDIT:
                box.separator()
                row = box.row()
                controller_names = bpy.types.Scene.MidiControl.midi_control_to_map
                if bpy.types.Scene.MidiControl.midi_control_to_map in bpy.types.Scene.MidiControl.controller_names:
                    controller_names = bpy.types.Scene.MidiControl.controller_names[
                        bpy.types.Scene.MidiControl.midi_control_to_map]

                row.label(
                    text=f"Control: {controller_names}, Mapped: {bpy.types.Scene.MidiControl.editting_mapped}")
                row = box.row()
                row.label(
                    text=f"Index: {bpy.types.Scene.MidiControl.editting_index}")
                box.row()
                box.prop(context.scene, 'control_name_input',
                         text="Controller Name")
                box.row()
                box.prop(context.scene, 'min_input')
                box.row()
                box.prop(context.scene, 'max_input')
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text="Save")
                op.min = context.scene.min_input
                op.max = context.scene.max_input
                op.controller_name = context.scene.control_name_input
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


# clasS NAMING CONVENTION ‘CATEGORY_PT_name’
class MIDICONTROLLER_PT_Panel_ImportExport(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Import / Export"  # found at the top of the Panel

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:
            layout.label(text="Import/Export")
            box = layout.box()
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Save.bl_idname)
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Load.bl_idname)
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

    def draw(self, context):
        layout = self.layout

        if bpy.types.Scene.MidiControl.midi_open:
            layout.label(text="Map Current Selection")
            if bpy.types.Scene.MidiControl.bind_selection_state == bpy.types.Scene.MidiControl.ControllerButtonBindingState.NONE:
                box = layout.box()
                row = box.row()
                row.label(text="Selection Group Name:")
                row = box.row()
                row.prop(context.scene, 'control_name_input', text="")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname)
                op.name = f"Group: {len(bpy.types.Scene.MidiControl.controller_selection_mapping.keys())}"
                if context.scene.control_name_input != "":
                    op.name = context.scene.control_name_input
                op.start = True
                op.cancel = False
            else:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Press button to map: {bpy.types.Scene.MidiControl.selection_to_map['name']}!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname, text=f"Cancel")
                op.cancel = True
                op.start = False

            row = layout.row()
            row.label(text="Current Mappings")
            row = layout.row()
            row.separator()

            for controller, mapped in bpy.types.Scene.MidiControl.controller_selection_mapping.items():
                row = layout.row()
                nbox = row.box()
                nbox.label(text=f"{mapped['name']}")
                row = nbox.row()
                op = row.operator(
                    MIDICONTROLLER_OP_DeleteSelectionGroup.bl_idname, text=f"Delete")
                op.controller = controller

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


classes = (MIDICONTROLLER_PT_Panel_Device,
           MIDICONTROLLER_PT_Panel_Status,
           MIDICONTROLLER_PT_Panel_BindKeyFrameInput,
           MIDICONTROLLER_PT_Panel_RegisterControllerMapping,
           MIDICONTROLLER_PT_Panel_MappedControls,
           MIDICONTROLLER_PT_Panel_SelectionGroups,
           MIDICONTROLLER_PT_Panel_ImportExport,
           MIDICONTROLLER_OP_FindMidi,
           MIDICONTROLLER_OP_ConnectMidi,
           MIDICONTROLLER_OP_DisconnectMidi,
           MIDICONTROLLER_OP_SavePropertyMapping,
           MIDICONTROLLER_OP_UpdatePropertyMapping,
           MIDICONTROLLER_OP_UpdateKeyFrameMapping,
           MIDICONTROLLER_OP_MapSelectionGroup,
           MIDICONTROLLER_OP_DeleteSelectionGroup,
           MIDICONTROLLER_OP_Save,
           MIDICONTROLLER_OP_Load)


def updatetimer():
    # print("update timer called")
    global midicontrol_instance
    midicontrol_instance.listen_for_property_changes()
    midicontrol_instance.parse_midi_messages()
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
    print("regisering plugin")
    if MidiController_Dependencies.required_packages_installed == False:
        bpy.utILS.REGISTER_CLASS(
            MIDICONTROLLER_PT_Panel_InstallRequiredPackages)
        bpy.utils.register_class(MIDICONTROLLER_OP_InstallRequiredPackages)
        bpy.utils.register_class(MIDICONTROLLER_OP_LoadPlugin)
        return

    global midicontrol_instance
    bpy.types.Scene.MidiControl = midicontrol_instance
    bpy.types.Scene.MidiControl.context = bpy.context

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"Could not register: {cls.bl_label}")
            print(e)

    bpy.types.Scene.min_input = bpy.props.FloatProperty(name='Min')
    bpy.types.Scene.max_input = bpy.props.FloatProperty(name='Max')
    bpy.types.Scene.control_name_input = bpy.props.StringProperty(
        name='Controller Name')
    bpy.app.timers.register(updatetimer)

    bpy.app.handlers.load_post.append(load_post)


def unregister():
    try:
        if MidiController_Dependencies.required_packages_installed == False or MidiController_Dependencies.finished_installing_package == True:
            print("finished installing required packages")
            bpy.utILS.UNREGISTER_CLASS(
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


# # if __name__ == "__main__":
# if __name__ == "__main__":
#     register()
