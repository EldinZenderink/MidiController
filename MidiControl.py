"""
Handles all midi interactions.

Returns:
    _type_: _description_
"""
import bpy
import copy
import traceback
import json


class MidiController_Midi():
    # to register and control midi
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

    # settings
    loaded_from_blend = False

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
    class ControllerButtonBindingState:
        NONE = 0
        PENDING = 1
        BOUND = 2

    # The current mapping state
    current_mapping_state = State.NONE

    # To interact/update ui
    screens = None

    # To interact/update objects
    context = None

    # Map a midi control to a property somehow
    mapping_pending = None
    mapping_error = None
    controller_property_mapping = {}
    properties_to_skip = []
    controller_names = {}

    # Controller to edit
    editting_controller = None
    edit_state = EditState.NONE

    # Controller to register keyframe(s) (note: all properties)
    key_frame_control = None
    key_frame_bind_control_state = ControllerButtonBindingState.NONE
    keyframe_insert_button_velocity_pressed = 0

    # Selection group buttons bound
    selection_to_map = None
    select_group_bind_selection_state = ControllerButtonBindingState.NONE
    controller_selection_mapping = {}
    select_group_button_velocity_pressed = 0

    # Frame position update
    controllers_to_set_frame = {
        "increase": {
            "state": ControllerButtonBindingState.NONE,
            "controller": None  # changes from the current frame into future frames
        },
        "decrease": {
            "state": ControllerButtonBindingState.NONE,
            # changes from the current frame into the past frames.
            "controller": None
        },
        # this is the resolution of the control (127/5 = 25.4 = 25 frames starting from the current frame)
        "frame_control_resolution": 5,
        # this allows for the system ot change the last frame position to the newly changed after this amount of time seeing no changes.
        "timeout": 1,
    }

    controllers_to_set_frame_current_frame = 0
    controllers_to_set_frame_timeout = 1

    # midi update rate
    midi_update_rate = 0.08

    previous_object = None
    current_object = None
    previous_object_data = {}
    current_object_data = {}
    accepted_types = ["<class 'int'>", "<class 'float'>",
                      "<class 'list'>", "<class 'Vector'>", "<class 'IDPropertyArray'>"]

    # class for usage in timer to read midi input

    def parse_midi_messages_update(self):
        try:
            if self.midi_input is not None and self.midi_input.is_port_open():
                last_data = None
                data = self.midi_input.get_message()
                while data is not None and self.midi_input.is_port_open():
                    last_data = data
                    data = self.midi_input.get_message()
                if last_data is not None:
                    self.midi_callback(last_data)
            else:
                self.close()
        except Exception as e:
            print("Failed reading from midi controller!")
            print(traceback.format_exc())
            print(e)
        return self.midi_update_rate

    def obj_prop_change_update(self):
        # print("Listening for property changes!")
        try:
            if bpy.context.screen.is_animation_playing:
                return self.midi_update_rate

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

            if self.current_mapping_state != self.State.NONE:
                if len(bpy.context.selected_objects) == 0:
                    return self.midi_update_rate

                obj = bpy.context.selected_objects[0]
                self.current_object = obj.name

                is_new = False

                if self.previous_object != self.current_object:
                    self.previous_object = obj.name
                    self.previous_object_data = {}
                    self.current_object_data = {}
                    is_new = True

                # default props
                # print("attr in obj:")
                # print(len(dir(obj)))
                if len(dir(obj)) < 400:
                    for prop in dir(obj):
                        if str(type(getattr(obj, prop))) in self.accepted_types:
                            if str(type(getattr(obj, prop))) in ["<class 'Vector'>"]:
                                if len(getattr(obj, prop)) > 6:
                                    print("attribute way to large, skipping")
                                    continue
                                for i, v in enumerate(getattr(obj, prop)):
                                    if f"{prop}_{i}" in self.properties_to_skip:
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
                                    self.current_object_data[f"{prop}_{i}"] = copy.copy(
                                        new_obj)
                            elif str(type(getattr(obj, prop))) in ["<class 'IDPropertyArray'>"]:
                                if len(getattr(obj, prop).to_list()) > 6:
                                    print("attribute way to large, skipping")
                                    continue
                                for i, v in enumerate(getattr(obj, prop).to_list()):
                                    if f"{prop}_{i}" in self.properties_to_skip:
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
                                    self.current_object_data[f"{prop}_{i}"] = copy.copy(
                                        new_obj)
                            else:
                                if f"{prop}" in self.properties_to_skip:
                                    continue
                                new_obj = copy.deepcopy(new_obj_template)
                                new_obj["name"] = f"{prop}"
                                new_obj["property"] = prop
                                new_obj["data"] = False
                                new_obj["type"] = str(
                                    type(getattr(obj, prop)))
                                new_obj['value'] = getattr(obj, prop)
                                self.current_object_data[f"{prop}"] = copy.copy(
                                    new_obj)
                    self.mapping_error = None
                else:
                    self.mapping_error = f"Failed parsing properties, too many!"

                # custom props
                if len(obj.keys()) > 1 and len(obj.keys()) < 400:
                    # First item is _RNA_UI
                    for K in obj.keys():
                        if K not in '_RNA_UI':
                            value = obj[K]
                            prop = K
                            if str(type(value)) in self.accepted_types:
                                if str(type(value)) in ["<class 'Vector'>"]:
                                    if len(value) > 6:
                                        print(
                                            "attribute way to large, skipping")
                                        continue
                                    for i, v in enumerate(value):
                                        if f"{prop}_{i}" in self.properties_to_skip:
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
                                        self.current_object_data[f"prop_{i}"] = copy.copy(
                                            new_obj)
                                elif str(type(value)) in ["<class 'IDPropertyArray'>"]:
                                    if len(value.to_list()) > 6:
                                        print(
                                            "attribute way to large, skipping")
                                        continue
                                    for i, v in enumerate(value.to_list()):
                                        if f"{prop}_{i}" in self.properties_to_skip:
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
                                        self.current_object_data[f"prop_{i}"] = copy.copy(
                                            new_obj)
                                else:
                                    if f"{prop}" in self.properties_to_skip:
                                        continue
                                    new_obj = copy.deepcopy(
                                        new_obj_template)
                                    new_obj["name"] = f"{prop}"
                                    new_obj["property"] = prop
                                    new_obj["key"] = True
                                    new_obj["data"] = False
                                    new_obj['value'] = value
                                    new_obj["type"] = str(type(value))
                                    self.current_object_data[prop] = copy.copy(
                                        new_obj)
                    self.mapping_error = None
                else:
                    self.mapping_error = f"Failed parsing properties, too many!"

                if self.previous_object == self.current_object and is_new == False:
                    for key, value in self.current_object_data.items():
                        if key in self.previous_object_data:
                            if value['value'] != self.previous_object_data[key]['value']:
                                self.mapping_pending = copy.copy(
                                    value)
                                self.current_mapping_state = self.State.CONFIGURE_MAPPING
                        else:
                            print(
                                f"Key: {key} not in previous object, skipping compare.")

                self.previous_object = copy.copy(
                    self.current_object)

                self.previous_object_data = copy.copy(
                    self.current_object_data)

                return self.midi_update_rate
        except Exception as e:
            self.mapping_error = f"Failed detecting changes."
            print("Failed detecting changes in object!")
            print(traceback.format_exc())
            print(e)

        return self.midi_update_rate

    def frame_update(self):
        if self.controllers_to_set_frame_timeout > 0:
            self.controllers_to_set_frame_timeout -= self.midi_update_rate
            self.redraw_ui()
        else:
            self.controllers_to_set_frame_timeout = 0
            self.controllers_to_set_frame_current_frame = bpy.context.scene.frame_current

    def redraw_ui(self):
        if self.screens == None:
            return
        try:
            for screen in self.screens:
                for area in screen.areas:
                    area.tag_redraw()
        except Exception as e:
            print("Screen error")

    def update_data(self, mapping, new_value):
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

            # This refreshes it... for some reason.
            # see: https://projects.blender.org/blender/blender/issues/74000
            obj.hide_render = obj.hide_render

    def insert_keyframes(self):
        for obj in bpy.context.selected_objects:
            for controller, mapping_array in self.controller_property_mapping.items():
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

    def control_frame(self, direction, raw_value):
        self.controllers_to_set_frame_timeout = self.controllers_to_set_frame["timeout"]
        frames_to_add = int(
            raw_value / self.controllers_to_set_frame["frame_control_resolution"] + 0.5)
        try:
            if direction == "increase":
                new_frame = self.controllers_to_set_frame_current_frame + frames_to_add
                bpy.context.scene.frame_set(new_frame)
            else:
                new_frame = self.controllers_to_set_frame_current_frame - frames_to_add
                if (self.controllers_to_set_frame_current_frame != new_frame):
                    if new_frame > 0:
                        bpy.context.scene.frame_set(new_frame)
                    else:
                        bpy.context.scene.frame_set(0)
                    self.redraw_ui()

        except Exception as e:
            print("Failed updating frame somehow...")
            print(e)

    def save_to_blend(self):
        to_save = {
            "controller_names": self.controller_names,
            "controller_mapping": self.controller_property_mapping,
            "selection_groups": self.controller_selection_mapping,
            "controller_keyframe_bind": {"controller": self.key_frame_control, "velocity": self.keyframe_insert_button_velocity_pressed}
        }
        try:
            setattr(self.context.scene, 'midicontrol_data', json.dumps(to_save))
        except Exception as e:
            print(e)

    def load_from_blend(self):
        try:
            if hasattr(self.context.scene, 'midicontrol_data') and self.loaded_from_blend == False:
                json_object = json.loads(
                    getattr(self.context.scene, 'midicontrol_data'))
                self.controller_names = json_object["controller_names"]
                self.controller_property_mapping = json_object["controller_mapping"]
                self.controller_selection_mapping = json_object["selection_groups"]
                self.key_frame_control = json_object[
                    "controller_keyframe_bind"]["controller"]
                self.keyframe_insert_button_velocity_pressed = json_object[
                    "controller_keyframe_bind"]["velocity"]
                self.loaded_from_blend = True
        except Exception as e:
            print(e)

    def select_objects(self, objects):
        bpy.ops.object.select_all(action='DESELECT')
        for objname in objects:
            bpy.data.objects[objname].select_set(True)

    def midi_callback(self, midi_data):
        velocity = midi_data[0][0]
        control = midi_data[0][1]
        value = midi_data[0][2]

        if velocity != self.midi_last_control_velocity:
            if self.key_frame_bind_control_state == self.ControllerButtonBindingState.PENDING:
                self.key_frame_control = control
                self.keyframe_insert_button_velocity_pressed = velocity
                        # self.save_to_blend()
                self.key_frame_bind_control_state = self.ControllerButtonBindingState.BOUND

            elif self.select_group_bind_selection_state == self.ControllerButtonBindingState.PENDING:
                new_selection_mapping = {
                    "name": self.selection_to_map["name"],
                    "selected_objects": self.selection_to_map["selected"],
                    "velocity": velocity
                }
                self.controller_selection_mapping[str(
                    control)] = new_selection_mapping
                self.select_group_button_velocity_pressed = velocity

                self.select_group_bind_selection_state = self.ControllerButtonBindingState.BOUND

            elif self.key_frame_bind_control_state == self.ControllerButtonBindingState.BOUND and \
                velocity == self.keyframe_insert_button_velocity_pressed and \
                self.key_frame_control == control:
                self.insert_keyframes()

                    # self.save_to_blend()
            elif self.select_group_bind_selection_state == self.ControllerButtonBindingState.BOUND and \
                velocity == self.select_group_button_velocity_pressed:
                if str(control) in self.controller_selection_mapping:
                    self.select_objects(
                        self.controller_selection_mapping[str(control)]["selected_objects"])


            self.midi_last_control_velocity = velocity

        if value != self.midi_last_control_value:
            self.midi_last_control_changed = control
            self.midi_last_control_value = value
            self.redraw_ui()

            found = (
                str(control) in self.controller_property_mapping.keys())
            if found == False:
                self.midi_control_to_map = control
            else:

                for mapping in self.controller_property_mapping[str(control)]:
                    min = mapping["min"]
                    max = mapping["max"]
                    new_value = (((max - min) / 127) * value) + min
                    self.update_data(mapping, new_value)

                self.midi_control_to_map = control

            if self.controllers_to_set_frame["increase"]["state"] == self.ControllerButtonBindingState.PENDING:
                self.controllers_to_set_frame["increase"]["controller"] = control
                self.controllers_to_set_frame["increase"]["state"] = self.ControllerButtonBindingState.BOUND
            elif self.controllers_to_set_frame["increase"]["controller"] == control:
                self.control_frame("increase", value)

            if self.controllers_to_set_frame["decrease"]["state"] == self.ControllerButtonBindingState.PENDING:
                self.controllers_to_set_frame["decrease"]["controller"] = control
                self.controllers_to_set_frame["decrease"]["state"] = self.ControllerButtonBindingState.BOUND
            elif self.controllers_to_set_frame["decrease"]["controller"] == control:
                self.control_frame("decrease", value)

        self.midi_last_control_changed = control
        self.midi_last_control_value = value
        self.redraw_ui()

    def close(self):
        if self.midi_open:
            if self.midi_input.is_port_open():
                self.midi_input.close_port()
            self.midi_input.delete()
            print(
                f"Closed midi controller: {self.connected_controller}")
            self.connected_controller = ""
            self.connected_port = None
            self.available_ports = None
            self.midi_input = None
            self.midi_open = False
            self.midi = None
            self.midi_last_control_changed = 0
            self.midi_last_control_value = 0
            self.midi_last_control_velocity = 0
            self.midi_control_to_map = None

            # settings
            self.loaded_from_blend = False

            # The current mapping state
            self.current_mapping_state = self.State.NONE

            # To interact/update ui
            self.screens = None

            # To interact/update objects
            self.context = None

            # Map a midi control to a property somehow
            self.mapping_pending = None

            # Controller to edit
            self.editting_controller = None
            self.edit_state = self.EditState.NONE

            # Controller to register keyframe(s) (note: all properties)
            self.key_frame_control = None

            # Selection group buttons bound
            self.selection_to_map = None
            self.bind_selection_state = self.ControllerButtonBindingState.NONE
