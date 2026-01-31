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


import bpy
from bpy.app.handlers import persistent
from copy import deepcopy

# Packages from wheels:
import copykitten

from .MidiControl import *

bl_info = {
    "name": "MidiController",
    "author": "Eldin Zenderink",
    "description": "",
    "blender": (4, 2, 0),
    "version": (0, 1, 5),
    "location": "",
    "warning": "",
    "category": "User Interface"
}

global midicontrol_instance
midicontrol_instance = MidiController_Midi()

# Global functions


def update_scene_prop(prop, name, value, scene_name=0):
    if scene_name is None:
        for scene in bpy.data.scenes.keys():
            try:
                if prop in bpy.data.scenes[scene]:
                    if name in bpy.data.scenes[scene][prop]:
                        bpy.data.scenes[scene][prop][name] = value
            except Exception as e:
                print(e)
    else:
        if prop in bpy.data.scenes[scene_name]:
            if name in bpy.data.scenes[scene_name][prop]:
                bpy.data.scenes[scene_name][prop][name] = value


def get_scene_prop_val(prop, name, scene_name=0):
    if scene_name is None:
        for scene in bpy.data.scenes.keys():
            try:
                if prop in bpy.data.scenes[scene]:
                    if name in bpy.data.scenes[scene][prop]:
                        return bpy.data.scenes[scene][prop][name]
            except Exception as e:
                print(e)
    else:
        if prop in bpy.data.scenes[scene_name]:
            if name in bpy.data.scenes[scene_name][prop]:
                return bpy.data.scenes[scene_name][prop][name]


class MIDICONTROLLER_GenericProperties(bpy.types.PropertyGroup):
    bl_label = "generic_properties"
    new_prop_min: bpy.props.IntProperty(name="new_prop_min", default=0)
    new_prop_max: bpy.props.IntProperty(name="new_prop_max", default=1)
    edit_prop_min: bpy.props.IntProperty(name="edit_prop_min", default=0)
    edit_prop_max: bpy.props.IntProperty(name="edit_prop_max", default=1)
    frame_control_sensitivity: bpy.props.IntProperty(
        name="frame_control_sensitivity", default=1)
    frame_control_update_timeout: bpy.props.IntProperty(
        name="frame_control_update_timeout", default=1)
    new_controller_name: bpy.props.StringProperty(
        name="new_controller_name", default="")
    edit_controller_name: bpy.props.StringProperty(
        name="edit_controller_name", default="")
    selection_group_name: bpy.props.StringProperty(
        name="selection_group_name", default="")


class MIDICONTROLLER_OP_FindMidi(bpy.types.Operator):
    bl_idname = "wm.find_midi"
    bl_label = "Find Midi Controllers"
    bl_description = "Find connected midi controllers."

    def execute(self, context):
        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl

        if midi_control.running is None:
            midi_control.start()

        # cheeky load, must be a better place to do this right... right?
        update_scene_prop('generic_properties',
                          'new_prop_min', int(0))
        update_scene_prop('generic_properties',
                          'new_prop_max', int(1))
        update_scene_prop('generic_properties',
                          'new_controller_name', "")
        update_scene_prop('generic_properties',
                          'edit_prop_min', int(0))
        update_scene_prop('generic_properties',
                          'edit_prop_max', int(1))
        update_scene_prop('generic_properties',
                          'edit_controller_name', "")
        update_scene_prop('generic_properties', 'fine_resolution', int(
            midi_control.controls_to_set_resolution['fine_resolution']))
        update_scene_prop('generic_properties', 'coarse_resolution', int(
            midi_control.controls_to_set_resolution['coarse_resolution']))
        update_scene_prop('generic_properties', 'frame_control_sensitivity', int(
            midi_control.controllers_to_set_frame['frame_control_resolution']))
        update_scene_prop('generic_properties', 'frame_control_update_timeout', int(
            midi_control.controllers_to_set_frame['timeout']))
        update_scene_prop('generic_properties',
                          'selection_group_name', f"")
        return {"FINISHED"}


class MIDICONTROLLER_OP_ConnectMidi(bpy.types.Operator):
    bl_idname = "wm.connect_midi"
    bl_label = "Connect Midi Controller"
    bl_description = "Connect midi controller."

    midi_port: bpy.props.IntProperty(default=0)

    def execute(self, context):
        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl
        midi_control.open_midi(self.midi_port)
        return {"FINISHED"}


class MIDICONTROLLER_OP_DisconnectMidi(bpy.types.Operator):
    bl_idname = "wm.disconnect_midi"
    bl_label = "Disconnect Midi Controller"
    bl_description = "Disconnect the currently connected midi controller."

    def execute(self, context):
        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl

        # Ensure the current configuration is saved
        if midi_control.midi_open:
            midi_control.close_midi()
        return {"FINISHED"}


class MIDICONTROLLER_OP_SavePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.save_property_mapping"
    bl_label = "Save Property Mapping"
    bl_description = "Store the currently configured property mapping to the last active midi control."

    min: bpy.props.FloatProperty(default=0)
    max: bpy.props.FloatProperty(default=0)
    controller_name: bpy.props.StringProperty(default="")
    cancel: bpy.props.BoolProperty(default=False)
    refresh: bpy.props.BoolProperty(default=False)
    direct_mapping: bpy.props.BoolProperty(default=False)
    direct_path: bpy.props.StringProperty(default="")

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if self.refresh:
            update_scene_prop('generic_properties', 'new_controller_name',
                              f"Ctrl_{self.controller_name}_{midi_control.mapping_pending['name']}")

        if self.cancel:
            midi_control.mapping_pending = None
            midi_control.midi_control_to_map = None
            midi_control.current_mapping_state = midi_control.State.NONE
            update_scene_prop('generic_properties',
                              'new_prop_min', int(0))
            update_scene_prop('generic_properties',
                              'new_prop_max', int(1))
            update_scene_prop('generic_properties',
                              'new_controller_name', "")
            return {"FINISHED"}

        if midi_control.current_mapping_state == midi_control.State.CONFIGURE_MAPPING:

            midi_control.mapping_pending["min"] = self.min
            midi_control.mapping_pending["max"] = self.max
            if str(midi_control.midi_control_to_map) not in midi_control.controller_property_mapping:
                midi_control.controller_property_mapping[str(midi_control.midi_control_to_map)] = [
                    midi_control.get_mapping_pending()]
            else:
                midi_control.controller_property_mapping[str(
                    midi_control.midi_control_to_map)] += [midi_control.get_mapping_pending()]

            if self.controller_name != "":
                midi_control.controller_names[str(
                    midi_control.midi_control_to_map)] = self.controller_name

            midi_control.mapping_pending = None
            midi_control.midi_control_to_map = None
            midi_control.current_mapping_state = midi_control.State.REGISTER_CONTROL
            update_scene_prop('generic_properties',
                              'new_prop_min', int(0))
            update_scene_prop('generic_properties',
                              'new_prop_max', int(1))
            update_scene_prop('generic_properties',
                              'new_controller_name', "")
        else:
            if midi_control.current_mapping_state == midi_control.State.REGISTER_CONTROL:
                if self.direct_mapping:
                    midi_control.mapping_pending = midi_control.mapping_template
                    midi_control.mapping_pending['direct'] = self.direct_mapping
                    midi_control.mapping_pending['path'] = self.direct_path
                    midi_control.mapping_pending['type'] = 'DIRECTPATH'
                else:
                    midi_control.mapping_pending['direct'] = self.direct_mapping
                midi_control.current_mapping_state = midi_control.State.CONFIGURE_MAPPING

        midi_control.save()
        return {"FINISHED"}


class MIDICONTROLLER_OP_UpdatePropertyMapping(bpy.types.Operator):
    bl_idname = "wm.update_property_mapping"
    bl_label = "Update Control Mapping"
    bl_description = "Click to edit/save/delete/cancel the current mapped property to the midi controller."

    midi_control_to_edit: bpy.props.StringProperty(default="")
    direct_path:  bpy.props.BoolProperty(default=False)
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
        # Get midicontroller instance
        scene = context.scene
        midi_control = scene.MidiControl
        if self.edit:
            min, max = midi_control.edit_property_mapping(
                self.midi_control_to_edit,
                self.mapped_property,
                self.index,
                midi_control.EditState.EDIT
            )
            update_scene_prop('generic_properties',
                              'edit_prop_min', int(min))
            update_scene_prop('generic_properties',
                              'edit_prop_max', int(max))

        if self.save:
            midi_control.save_property_mapping(
                self.controller_name, self.min, self.max)

        if self.delete:
            midi_control.delete_property_mapping()

        if self.cancel:
            midi_control.cancel_edit_property_mapping()

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
            midi_control.start_update_key_frame_mapping()
        elif self.reset:
            midi_control.reset_key_frame_mapping()

        return {"FINISHED"}


class MIDICONTROLLER_OP_MapSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.map_selection_group"
    bl_label = "Map Selection Group"
    bl_description = "Click to map all currently selected objects to a control on your midi device!"

    name: bpy.props.StringProperty(default="")
    start: bpy.props.BoolProperty(default=False)
    cancel: bpy.props.BoolProperty(default=False)

    def execute(self, context):

        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl

        if self.start:
            midi_control.start_selection_group_mapping(self.name)
            update_scene_prop('generic_properties',
                              'selection_group_name', f"")

        if self.cancel:
            midi_control.cancel_selection_group_mapping()
            update_scene_prop('generic_properties',
                              'selection_group_name', f"")
        return {"FINISHED"}


class MIDICONTROLLER_OP_DeleteSelectionGroup(bpy.types.Operator):
    bl_idname = "wm.delete_selection_group"
    bl_label = "Delete"
    bl_description = "Remove selection group."

    controller: bpy.props.StringProperty(default="")

    def execute(self, context):

        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl
        midi_control.delete_selection_group(self.controller)

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
        # Get midicontrol instance
        scene = context.scene
        midi_control = scene.MidiControl

        if self.action == "map_control":
            frame_control_resolution, timeout = midi_control.map_frame_selection_control(
                self.direction)
            update_scene_prop('generic_properties', 'frame_control_sensitivity',
                              frame_control_resolution)
            update_scene_prop(
                'generic_properties', 'frame_control_update_timeout', timeout)

        elif self.action == "save_settings":
            frame_control_resolution, timeout = midi_control.save_frame_selection_control(
                self.frame_control_resolution, self.timeout)
            update_scene_prop('generic_properties', 'frame_control_sensitivity',
                              frame_control_resolution)
            update_scene_prop(
                'generic_properties', 'frame_control_update_timeout', timeout)
        elif self.action == "reset":
            midi_control.reset_frame_selection_control()

        return {"FINISHED"}


class MIDICONTROLLER_OP_MapResolutionSelection(bpy.types.Operator):
    bl_idname = "wm.map_resolution_selection"
    bl_label = "Map Resolution Select Controller"
    bl_description = "Configure coarse/fine control."

    action: bpy.props.StringProperty(default="")
    type: bpy.props.StringProperty(default="")

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl

        if self.action == "map_control":
            resolution_factor = midi_control.map_resolution_selection(
                self.type)
            update_scene_prop('generic_properties', 'resolution',
                              resolution_factor)
        elif self.action == "reset":
            midi_control.reset_map_resolution_selection()

        midi_control.save()
        return {"FINISHED"}


class MIDICONTROLLER_OP_Save(bpy.types.Operator):
    bl_label = "Save"
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
        midi_control.save(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        scene = context.scene
        midi_control = scene.MidiControl
        self.filename = midi_control.connected_controller + ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MIDICONTROLLER_OP_Load(bpy.types.Operator):
    bl_label = "Load"
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

        # Reading from json file
        print(f"Loading: {self.filepath} ")
        midi_control.load(external=self.filepath)
        midi_control.save()
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MIDICONTROLLER_OP_EnableLogInfo(bpy.types.Operator):
    bl_label = "Enable Info Logging"
    bl_idname = "wm.enableloginfo_dialog"
    bl_description = "Enable Log Info."

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl
        midi_control.enable_info_log()
        return {'FINISHED'}


class MIDICONTROLLER_OP_DisableLogInfo(bpy.types.Operator):
    bl_label = "Disable Info Logging"
    bl_idname = "wm.disableloginfo_dialog"
    bl_description = "Disable Log Info."

    def execute(self, context):
        scene = context.scene
        midi_control = scene.MidiControl
        midi_control.disable_info_log()
        return {'FINISHED'}


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

        midi_control.screens = bpy.data.screens
        """define the layout of the panel"""
        box = layout.box()
        row = box.row()

        if midi_control.midi_input is not None and midi_control.midi_open:
            row.operator(MIDICONTROLLER_OP_DisconnectMidi.bl_idname)
        else:
            if midi_control.available_ports is None:
                row.operator(MIDICONTROLLER_OP_FindMidi.bl_idname)
            elif midi_control.midi_open == False:
                row = box.row()
                row.label(text="Click To Connect Device:")
                midi_control.refresh_available_midi_ports()
                for port, name in enumerate(midi_control.available_ports):
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_ConnectMidi.bl_idname, text=name)
                    op.midi_port = port


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


class MIDICONTROLLER_PT_Panel_ResolutionControls(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Resolution Control"  # found at the top of the Panel
    bl_description = "Manage the coarse and fine control over ."

    def draw(self, context):

        scene = context.scene
        generic_properties = scene.generic_properties
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            layout.label(text="Control Coarse Resolution")

            if midi_control.controls_to_set_resolution["set_coarse_resolution"]["state"] == midi_control.ControllerButtonBindingState.NONE:
                box = layout.box()
                box.alert = False
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text="Start Map Coarse Control")
                op.action = "map_control"
                op.type = "set_coarse_resolution"
            elif midi_control.controls_to_set_resolution["set_coarse_resolution"]["state"] == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                box.alert = True
                row = box.row()
                row.label(
                    text=f"Map Coarse Control: {midi_control.controls_to_set_resolution['set_coarse_resolution']['controller']}")

                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind to coarse control!")

                box.alert = False
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text="Stop")
                op.action = "reset"
                op.type = "set_coarse_resolution"

            if midi_control.controls_to_set_resolution["set_fine_resolution"]["state"] == midi_control.ControllerButtonBindingState.NONE:
                box = layout.box()
                box.alert = False
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text="Start Map Fine Control")
                op.action = "map_control"
                op.type = "set_fine_resolution"
            elif midi_control.controls_to_set_resolution["set_fine_resolution"]["state"] == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                box.alert = True
                row = box.row()
                row.label(
                    text=f"Map Coarse Control: {midi_control.controls_to_set_resolution['set_fine_resolution']['controller']}")
                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind to coarse control!")
                box.alert = False
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text="Stop")
                op.action = "reset"
                op.type = "set_fine_resolution"

            if midi_control.controls_to_set_resolution["set_coarse_resolution"]["controller"] != None:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Coarse Control: {midi_control.controls_to_set_resolution['set_coarse_resolution']['controller']}")

                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text=f"Reset Bind")
                op.action = "reset"
                op.type = "set_coarse_resolution"

            if midi_control.controls_to_set_resolution["set_fine_resolution"]["controller"] != None:

                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Fine Control: {midi_control.controls_to_set_resolution['set_fine_resolution']['controller']}")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapResolutionSelection.bl_idname, text=f"Reset Bind")
                op.action = "reset"
                op.type = "set_fine_resolution"

            box = layout.box()
            row = box.row()
            resolution = (midi_control.controls_to_set_resolution["coarse_resolution"]) + (
                ((1 / 127) * midi_control.controls_to_set_resolution["fine_resolution"]))
            row.label(
                text=f"Current Resolution: {resolution}")

        else:
            layout.label(text="Connect Midi Device First!")


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
                box.alert = True
                op = row.operator(
                    MIDICONTROLLER_OP_UpdateKeyFrameMapping.bl_idname, text="Start Binding")
                op.reset = False
                op.start = True

                if midi_control.key_frame_bind_control_state == midi_control.ControllerButtonBindingState.PENDING:
                    row = box.row()
                    row.label(text="Press a button to bind!")

            else:
                box.alert = False
                op = row.operator(
                    MIDICONTROLLER_OP_UpdateKeyFrameMapping.bl_idname, text="Reset Bind")
                op.reset = True
                op.start = False
        else:
            layout.label(text="Connect Midi Device First!")


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
                box.alert = False
                row = box.row()
                row.label(text=f"1. Touch a Midi Control!")
            else:
                if midi_control.current_mapping_state == midi_control.State.NONE:
                    midi_control.current_mapping_state = midi_control.State.REGISTER_CONTROL
                elif midi_control.current_mapping_state == midi_control.State.REGISTER_CONTROL:
                    box = layout.box()
                    box.alert = True
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
                    row = box.row()

                    row.label(text=f"Or configure a direct path by")
                    row = box.row()
                    row.label(text=f"Right click on property -> ")
                    row = box.row()
                    row.label(text=f"Copy Direct Path")
                    row = box.row()
                    row.label(text=f"Or:")
                    row = box.row()
                    row.label(text=f"Copy Full Data Path")
                    copied = copykitten.paste()
                    if copied.startswith("bpy"):
                        row = box.row()
                        row.label(text=f"Path to be mapped:")
                        row = box.row()
                        row.alert = True
                        row.label(text=f"Direct path mapping wil be applied")
                        row = box.row()
                        row.alert = True
                        row.label(
                            text=f"to that specific property independent")
                        row = box.row()
                        row.alert = True
                        row.label(text=f"of it being selected!!!")
                        row = box.row()

                        row.label(text=f"- {copykitten.paste()} -")
                        row = box.row()
                        op = row.operator(
                            MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Map Path")
                        op.direct_path = copied
                        op.direct_mapping = True
                        op.cancel = False
                    if midi_control.mapping_pending is not None:
                        row = box.row()
                        row.label(text=f"Last change blender property:")
                        row = box.row()
                        row.label(
                            text=f"{midi_control.mapping_pending['name']}")
                        row = box.row()
                        op = row.operator(
                            MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Map Control")
                        op.direct_mapping = False
                        op.cancel = False

                elif midi_control.current_mapping_state == midi_control.State.CONFIGURE_MAPPING:
                    box = layout.box()
                    box.alert = True
                    controller_name = midi_control.midi_control_to_map
                    if midi_control.midi_control_to_map in midi_control.controller_names:
                        controller_name = midi_control.controller_names[
                            midi_control.midi_control_to_map]

                    if get_scene_prop_val('generic_properties', 'new_controller_name') == "":
                        update_scene_prop('generic_properties', 'new_controller_name',
                                          f"NewMapping_{len(midi_control.controller_property_mapping.keys())}")

                    row = box.row()
                    row.alert = False
                    row.label(
                        text=f"Mapping Controller: {controller_name} ({midi_control.midi_control_to_map})")
                    row = box.row()
                    row.label(text=f"Touch control to change!")
                    box = layout.box()
                    box.alert = True
                    if midi_control.mapping_pending['direct']:
                        row = box.row()
                        row.label(
                            text=f"Mapping Path:")
                        row = box.row()
                        row.label(
                            text=midi_control.mapping_pending['path'])
                    else:
                        row = box.row()
                        row.label(
                            text=f"Mapping Property: {midi_control.mapping_pending['name']}")
                    row = box.row()
                    row.label(text=f"Edit blender property to change!")
                    box = layout.box()
                    row = box.row()

                    box.alert = True
                    row = box.row()
                    row.label(text=f"3. Configure Mapping")
                    box.alert = False
                    row = box.row()
                    row.prop(generic_properties, 'new_controller_name',
                             text="Controller Name")
                    row = box.row()
                    row.prop(generic_properties,
                             'new_prop_min', text="Min")
                    row = box.row()
                    row.prop(generic_properties,
                             'new_prop_max', text="Max")
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Apply")
                    op.controller_name = generic_properties.new_controller_name
                    op.min = generic_properties.new_prop_min
                    op.max = generic_properties.new_prop_max
                    op.direct_mapping = midi_control.mapping_pending['direct']
                    op.cancel = False
                    row = box.row()
                    op = row.operator(
                        MIDICONTROLLER_OP_SavePropertyMapping.bl_idname, text="Cancel")
                    op.cancel = True
        else:
            layout.label(text="Connect Midi Device First!")


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
            box.alert = False
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
                        name = mapped['name']
                        if mapped['direct']:
                            name = mapped['path']
                            row.alert = True
                        op = row.operator(
                            MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text=f"{name}")
                        op.edit = True
                        op.save = False
                        op.delete = False
                        op.cancel = False
                        op.index = index
                        op.midi_control_to_edit = controller
                        op.mapped_property = name

            elif midi_control.edit_state == midi_control.EditState.EDIT:
                box.separator()
                row = box.row()
                box.alert = True
                controller_names = midi_control.midi_control_to_map
                if midi_control.midi_control_to_map in midi_control.controller_names:
                    controller_names = midi_control.controller_names[
                        midi_control.midi_control_to_map]

                if midi_control.controller_property_mapping[midi_control.editting_controller][midi_control.editting_index]["direct"]:
                    row.label(text=f"Directly Mapped Property!")

                row.label(
                    text=f"Control: {controller_names}, Mapped: {midi_control.editting_mapped}")
                row = box.row()
                row.label(
                    text=f"Index: {midi_control.editting_index}")
                box.row()
                row.label(
                    text=f"Current Min: {midi_control.controller_property_mapping[midi_control.editting_controller][midi_control.editting_index]['min']}, Max: {midi_control.controller_property_mapping[midi_control.editting_controller][midi_control.editting_index]['max']}")

                box.alert = False
                box.row()
                box.prop(generic_properties, 'edit_controller_name',
                         text="Controller Name")
                box.row()
                box.prop(generic_properties, 'edit_prop_min',
                         text="Min")
                box.row()
                box.prop(generic_properties, 'edit_prop_max',
                         text="Max")

                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_UpdatePropertyMapping.bl_idname, text="Apply")
                op.min = generic_properties.edit_prop_min
                op.max = generic_properties.edit_prop_max
                op.controller_name = generic_properties.edit_controller_name
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
            layout.label(text="Map Current Selected As Group:")
            if midi_control.select_group_bind_selection_state != midi_control.ControllerButtonBindingState.PENDING:
                if generic_properties.selection_group_name == "":
                    update_scene_prop('generic_properties', 'selection_group_name',
                                      f"Group ({len(midi_control.controller_selection_mapping.keys())})")

                box = layout.box()
                row = box.row()
                row.label(text="Selection Group Name:")
                row = box.row()
                row.label(
                    text=f"Current: 'Group: {len(midi_control.controller_selection_mapping.keys())}'")

                row = box.row()
                row.prop(generic_properties,
                         'selection_group_name', text="Name")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname)
                op.name = generic_properties.selection_group_name
                op.start = True
                op.cancel = False
            elif midi_control.select_group_bind_selection_state == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                box.alert = True
                row = box.row()
                row.label(
                    text=f"Press button to map: {midi_control.selection_to_map['name']}!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapSelectionGroup.bl_idname, text=f"Cancel")
                op.cancel = True
                op.start = False

            row = layout.row()
            row.label(text="Mapped Groups:")
            row = layout.row()
            row.separator()

            for controller, mapped in midi_control.controller_selection_mapping.items():
                row = layout.row()
                nbox = row.box()
                nbox.label(
                    text=f"Group: {mapped['name']}, Mapped To: {controller}")
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
                row.label(
                    text=f"Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Map Control")
                op.action = "map_control"
                op.direction = "increase"
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")
            elif midi_control.controllers_to_set_frame["increase"]["state"] == midi_control.ControllerButtonBindingState.PENDING:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")
                row = box.row()
                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind to coarse control!")
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")
            elif midi_control.controllers_to_set_frame["decrease"]["state"] == midi_control.ControllerButtonBindingState.NONE:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")
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
                row.label(
                    text=f"Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")
                row = box.row()
                row.label(text="Change a midi control,")
                row = box.row()
                row.label(text="to bind to coarse control!")
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
            else:
                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Increase Control: {midi_control.controllers_to_set_frame['increase']['controller']}")

                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Decrease Control: {midi_control.controllers_to_set_frame['decrease']['controller']}")

                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Sensitivity: {midi_control.controllers_to_set_frame['frame_control_resolution']}")
                row = box.row()
                row.prop(generic_properties,
                         'frame_control_sensitivity', text="")

                box = layout.box()
                row = box.row()
                row.label(
                    text=f"Frame Position: {midi_control.controllers_to_set_frame_current_frame}")

                box = layout.box()
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Save")
                op.frame_control_resolution = generic_properties.frame_control_sensitivity
                op.timeout = generic_properties.frame_control_update_timeout
                op.action = "save_settings"
                row = box.row()
                op = row.operator(
                    MIDICONTROLLER_OP_MapFrameSelection.bl_idname, text="Reset")
                op.action = "reset"
                row = box.row()

        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_SaveLoad(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Save / Load"  # found at the top of the Panel
    bl_description = "Save/Load midicontrol settings from external json."

    def draw(self, context):

        scene = context.scene
        midi_control = scene.MidiControl
        layout = self.layout

        if midi_control.midi_open:
            box = layout.box()
            row = box.row()
            row.label(text="Save to external JSON")
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Save.bl_idname)
            row = box.row()
            row.label(text="Load from external JSON")
            row = box.row()
            row.operator(MIDICONTROLLER_OP_Load.bl_idname)
        else:
            layout.label(text="Connect Midi Device First!")


class MIDICONTROLLER_PT_Panel_Developer(bpy.types.Panel):

    # where to add the panel in the UI
    # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_space_type = "VIEW_3D"
    # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)
    bl_region_type = "UI"

    bl_category = "MidiController"  # found in the Sidebar
    bl_label = "Developer"  # found at the top of the Panel
    bl_description = "Developer and/or troubleshooting options."

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.operator(MIDICONTROLLER_OP_EnableLogInfo.bl_idname)
        row = box.row()
        row.operator(MIDICONTROLLER_OP_DisableLogInfo.bl_idname)


classes = (MIDICONTROLLER_GenericProperties,
           MIDICONTROLLER_PT_Panel_Device,
           MIDICONTROLLER_PT_Panel_Status,
           MIDICONTROLLER_PT_Panel_ResolutionControls,
           MIDICONTROLLER_PT_Panel_BindKeyFrameInput,
           MIDICONTROLLER_PT_Panel_RegisterControllerMapping,
           MIDICONTROLLER_PT_Panel_MappedControls,
           MIDICONTROLLER_PT_Panel_SelectionGroups,
           MIDICONTROLLER_PT_Panel_FramePosition,
           MIDICONTROLLER_PT_Panel_SaveLoad,
           MIDICONTROLLER_PT_Panel_Developer,
           MIDICONTROLLER_OP_FindMidi,
           MIDICONTROLLER_OP_ConnectMidi,
           MIDICONTROLLER_OP_DisconnectMidi,
           MIDICONTROLLER_OP_SavePropertyMapping,
           MIDICONTROLLER_OP_UpdatePropertyMapping,
           MIDICONTROLLER_OP_UpdateKeyFrameMapping,
           MIDICONTROLLER_OP_MapSelectionGroup,
           MIDICONTROLLER_OP_DeleteSelectionGroup,
           MIDICONTROLLER_OP_MapFrameSelection,
           MIDICONTROLLER_OP_MapResolutionSelection,
           MIDICONTROLLER_OP_Save,
           MIDICONTROLLER_OP_Load,
           MIDICONTROLLER_OP_EnableLogInfo,
           MIDICONTROLLER_OP_DisableLogInfo)


@persistent
def load_post(dummy):
    print("Finished load")
    global midicontrol_instance
    # Configure midicontrol after blender has fully loaded.

    midicontrol_instance.start()


@persistent
def save_pre(dummy):
    global midicontrol_instance
    if midicontrol_instance.running:
        midicontrol_instance.save()


def register():
    print("Registering Plugin: MidiController")
    global midicontrol_instance

    bpy.types.Scene.MidiControl = midicontrol_instance

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"Could not register: {cls.bl_label}")
            print(e)

    bpy.types.Scene.generic_properties = bpy.props.PointerProperty(
        type=MIDICONTROLLER_GenericProperties)

    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.save_pre.append(save_pre)


def unregister():
    global midicontrol_instance

    try:
        if midicontrol_instance.midi_open:
            midicontrol_instance.close()
            print("Midi controller closed properly")
    except Exception as e:
        print("Failed to close midi")
        print(e)

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Could not unregister: {cls.bl_label}")
            print(e)

    del bpy.types.Scene.MidiControl
