"""
Handles all midi interactions.
"""
import bpy
import copy
import traceback
import json
import logging

def property_changed(*args):
    self, obj_name, path = args

    v = None
    k = path
    for obj in bpy.context.selected_objects:
        if obj.name == obj_name:
            v = getattr(obj, k)
    try:
        new_obj = copy.deepcopy(self.mapping_template)

        if str(type(v)) in ["<class 'Vector'>", "<class 'Quaternion'>", "<class 'Euler'>"]:
            for i, x in enumerate(v):
                self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                if f'{k}[{i}]' not in self.previous_property_value:
                    self.previous_property_value[f'{k}[{i}]'] = x

                if self.previous_property_value[f'{k}[{i}]'] != x:
                    self.log.info(
                        f"Previous: {obj.name}[{k}][{i}] = {self.previous_property_value[f'{k}[{i}]']}")
                    new_obj["name"] = f'{k}[{i}]'
                    new_obj["property"] = k
                    new_obj["data"] = False
                    new_obj["key"] = False
                    new_obj["type"] = "<class 'Vector'>"
                    new_obj['index'] = i
                    new_obj['value'] = x
                    self.previous_property_value[f'{k}[{i}]'] = x
                    self.mapping_pending = copy.deepcopy(new_obj)
                    self.log.info("Updated mapping pending")
        elif str(type(v)) in ["<class 'bpy_prop_array'>"]:
            for i, x in enumerate(v.to_list()):
                self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                if f'{k}[{i}]' not in self.previous_property_value:
                    self.previous_property_value[f'{k}[{i}]'] = x
                if self.previous_property_value[f'{k}[{i}]'] != x:
                    self.log.info(
                        f"Previous: {obj.name}[{k}][{i}] = { self.previous_property_value[f'{k}[{i}]']}")
                    new_obj["name"] = f"{k}[{i}]"
                    new_obj["property"] = k
                    new_obj["data"] = False
                    new_obj["key"] = True
                    new_obj["type"] = "<class 'IDPropertyArray'>"
                    new_obj['index'] = i
                    new_obj['value'] = x
                    self.previous_property_value[f'{k}[{i}]'] = x
                    self.mapping_pending = copy.copy(new_obj)
        elif str(type(v)) in ["<class 'IDPropertyArray'>"]:
            for i, x in enumerate(v.to_list()):
                self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                if f'{k}[{i}]' not in self.previous_property_value:
                    self.previous_property_value[f'{k}[{i}]'] = x
                if self.previous_property_value[f'{k}[{i}]'] != x:
                    self.log.info(
                        f"Previous: {obj.name}[{k}][{i}] = { self.previous_property_value[f'{k}[{i}]']}")
                    new_obj["name"] = f"{k}[{i}]"
                    new_obj["property"] = k
                    new_obj["data"] = False
                    new_obj["key"] = False
                    new_obj["type"] = "<class 'IDPropertyArray'>"
                    new_obj['index'] = i
                    new_obj['value'] = x
                    self.previous_property_value[f'{k}[{i}]'] = x
                    self.mapping_pending = copy.deepcopy(new_obj)
        elif str(type(v)) in ["<class 'float'>", "<class 'int'>"]:
            self.log.info(
                f"{obj.name}[{k}] = {v} (type: {str(type(v))})")
            if f'{k}' not in self.previous_property_value:
                self.log.info(f"New: = {x}")
                self.previous_property_value[f'{k}'] = v
            if self.previous_property_value[f'{k}'] != v:
                self.log.info(
                    f"Changed from: {obj.name}[{k}] = {self.previous_property_value[f'{k}'] }")
                new_obj["name"] = f"{k}"
                new_obj["property"] = k
                new_obj["data"] = False
                new_obj["key"] = True
                new_obj["type"] = str(type(v))
                new_obj['value'] = v
                self.previous_property_value[f"{k}"] = v
                self.mapping_pending = copy.copy(new_obj)
        else:
            self.log.info(
                f"Unsupported type: {str(type(v))} for property {k} in object: {obj.name}")
    except Exception as e:
        self.log.warning(
            f"Failed to check changes for property: {k} for object: {obj_name}")
        self.log.warning(e)


class MidiController_Midi():
    # to register and control midi
    connected_controller = ""
    connected_port = None
    available_ports = None
    midi_input = None
    midi_open = False
    midi = None
    midi_last_control_changed = 0
    midi_last_control_mapped = False
    midi_last_control_value = 0
    midi_last_control_velocity = 0
    midi_control_to_map = None
    midi_control_to_map_is_direct = False
    midi_control_to_map_direct_path = ""

    # max properties (it will be terribly slow otherwise):
    max_properties = 1000

    # settings
    loaded_json = {}

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

    # default mapping template
    mapping_template = {
        "direct": False,
        "path": None,
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

    # Controller to edit
    editting_controller = None
    editting_mapped = None
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

    controls_to_set_resolution = {
        "set_fine_resolution": {
            "state": ControllerButtonBindingState.NONE,
            "controller": None  # changes from the current frame into future frames
        },
        "set_coarse_resolution": {
            "state": ControllerButtonBindingState.NONE,
            "controller": None  # changes from the current frame into future frames
        },
        "fine_resolution": 1,
        "coarse_resolution": 1,
    }

    controllers_to_set_frame_current_frame = 0
    controllers_to_set_frame_timeout = 1

    # midi update rate (If users experience slowdowns: this should be looked at.)
    midi_update_rate = 0.08

    # Some globals for object data.
    current_selected_object = None

    # Store subscriptions so they can be cleared later
    subscriptions = []
    last_custom_props = {}
    previous_property_value = {}

    # Register logger
    log = logging.getLogger(__name__)

    def start(self):
        """Ensures not callback is left behind or previously registered.
        """
        self.log.setLevel(logging.WARNING)

        if self.check_custom_props in bpy.app.handlers.depsgraph_update_post:
            self.log.warning(
                f"Found registered handler 'check_custom_props' which should have been deregistered!")
            bpy.app.handlers.depsgraph_update_post.remove(
                self.check_custom_props)

    def enable_info_log(self):
        self.log.setLevel(logging.INFO)
        self.log.info("Enabled INFO level logging.")

    def disable_info_log(self):
        self.log.info("Disabled INFO level logging.")
        self.log.setLevel(logging.WARNING)

    def set_path_value(self, full_dp: str, value):
        """ Sets a value to a specific data path.

        Args:
            full_dp (str): Data Path to property.
            value (float,int,str): Value of property.
        """
        try:
            full_dp = full_dp.strip()
            self.log.info(f"Setting: {full_dp}: {value}")

            # This probably does not work  for everything but its a quick workaround for now, to allow brushes to work :)
            # If users report issues with data paths: this will be the first thing to look into :).
            if ", " in full_dp and "]." in full_dp:
                full_dp = full_dp.split(
                    ', ')[0][:-1] + "\"]" + full_dp.split(']')[1]
                self.log.info(f"Removed the path, new fulldp: {full_dp}")

            if full_dp.endswith(']'):
                i = full_dp.rfind('[')
                # path_resolve not allow extra space
                attr0 = full_dp[9: i].strip()
                attr1 = full_dp[i:].strip()

                parent = bpy.data.path_resolve(attr0)
                if ('"' in attr1):
                    parent[attr1[2: -2]] = value
                else:
                    parent[int(attr1[1: -1])] = value
            else:
                i = full_dp.rfind(".")
                attr0 = full_dp[9: i].strip()
                attr1 = full_dp[i + 1:].strip()
                parent = bpy.data.path_resolve(attr0)
                attrtype = str(type(getattr(parent, attr1)))
                if ('int' in attrtype):
                    value = int(value)
                if ('float' in attrtype):
                    value = float(value)
                if ('str' in attrtype):
                    value = str(value)
                setattr(parent, attr1, value)
        except Exception as e:
            self.log.warning(f"Failed to write property using setattr:")
            self.log.warning(f"Data Path: {full_dp}, Value: {value}")
            self.log.warning(f"{e}")

    def check_custom_props(self, scene, x):
        """Handler to detect custom property changes."""

        obj = bpy.context.object
        if not obj:
            self.log.info(
                f"Got change in property while not having any object selected, ignoring!")
            return

        current = {k: v for k, v in obj.items() if k != "_RNA_UI"}
        # Detect changes
        for k, v in current.items():
            try:
                new_obj = copy.deepcopy(self.mapping_template)
                if str(type(v)) in ["<class 'Vector'>", "<class 'Quaternion'>", "<class 'Euler'>"]:
                    for i, x in enumerate(v):
                        self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                        if f'{k}[{i}]' not in self.previous_property_value:
                            self.previous_property_value[f'{k}[{i}]'] = x
                        if self.previous_property_value[f'{k}[{i}]'] != x:
                            self.log.info(
                                f"Previous: {obj.name}[{k}][{i}] = {self.previous_property_value[f'{k}[{i}]']}")
                            new_obj["name"] = f'{k}[{i}]'
                            new_obj["property"] = k
                            new_obj["data"] = False
                            new_obj["key"] = True
                            new_obj["type"] = "<class 'Vector'>"
                            new_obj['index'] = i
                            new_obj['value'] = x
                            self.previous_property_value[f'{k}[{i}]'] = x
                            self.mapping_pending = copy.deepcopy(new_obj)

                elif str(type(v)) in ["<class 'IDPropertyArray'>"]:
                    for i, x in enumerate(v.to_list()):
                        self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                        if f'{k}[{i}]' not in self.previous_property_value:
                            self.previous_property_value[f'{k}[{i}]'] = x
                        if self.previous_property_value[f'{k}[{i}]'] != x:
                            self.log.info(
                                f"Previous: {obj.name}[{k}][{i}] = { self.previous_property_value[f'{k}[{i}]']}")
                            new_obj["name"] = f"{k}[{i}]"
                            new_obj["property"] = k
                            new_obj["data"] = False
                            new_obj["key"] = True
                            new_obj["type"] = "<class 'IDPropertyArray'>"
                            new_obj['index'] = i
                            new_obj['value'] = x
                            self.previous_property_value[f'{k}[{i}]'] = x
                            self.mapping_pending = copy.deepcopy(new_obj)
                elif str(type(v)) in ["<class 'bpy_prop_array'>"]:
                    for i, x in enumerate(v.to_list()):
                        self.log.info(f"{obj.name}[{k}][{i}] = {x}")
                        if f'{k}[{i}]' not in self.previous_property_value:
                            self.previous_property_value[f'{k}[{i}]'] = x
                        if self.previous_property_value[f'{k}[{i}]'] != x:
                            self.log.info(
                                f"Previous: {obj.name}[{k}][{i}] = { self.previous_property_value[f'{k}[{i}]']}")
                            new_obj["name"] = f"{k}[{i}]"
                            new_obj["property"] = k
                            new_obj["data"] = False
                            new_obj["key"] = True
                            new_obj["type"] = "<class 'IDPropertyArray'>"
                            new_obj['index'] = i
                            new_obj['value'] = x
                            self.previous_property_value[f'{k}[{i}]'] = x
                            self.mapping_pending = copy.copy(new_obj)
                elif str(type(v)) in ["<class 'float'>", "<class 'int'>"]:
                    self.log.info(
                        f"{obj.name}[{k}] = {v} (type: {str(type(v))})")
                    if f'{k}' not in self.previous_property_value:
                        self.log.info(f"New: = {x}")
                        self.previous_property_value[f'{k}'] = v
                    if self.previous_property_value[f'{k}'] != v:
                        self.log.info(
                            f"Changed from: {obj.name}[{k}] = {self.previous_property_value[f'{k}'] }")
                        new_obj["name"] = f"{k}"
                        new_obj["property"] = k
                        new_obj["data"] = False
                        new_obj["key"] = True
                        new_obj["type"] = str(type(v))
                        new_obj['value'] = v
                        self.previous_property_value[f"{k}"] = v
                        self.mapping_pending = copy.copy(new_obj)
                else:
                    self.log.info(
                        f"Unsupported type: {str(type(v))} for property {k} in object: {obj.name}")
            except Exception as e:
                self.log.error(
                    f"Failed to parse property {k} in object: {obj.name}")
                self.log.error(e)

        self.last_custom_props[obj.name] = copy.copy(current)

    def track_all_properties(self, obj):
        """Subscribe to all RNA + custom properties of the object."""

        # clear last custom prop values!
        self.previous_property_value = {}

        self.log.info(f"Selected object: {obj}")

        try:
            # Clear old subscriptions
            for sub in self.subscriptions:
                bpy.msgbus.clear_by_owner(sub)
            self.subscriptions.clear()
        except Exception as e:
            self.log.warning(
                f"Failed to clear subscriptions before registering any for {obj.name}")

        # Get RNA type
        rna_type = type(obj)

        # Iterate over all RNA properties
        for prop in obj.bl_rna.properties:
            if prop.is_readonly or prop.identifier == "rna_type":
                continue

            path = prop.identifier
            sub = object()
            self.log.info(f"Try registering: {prop.identifier}")
            try:
                bpy.msgbus.subscribe_rna(
                    key=(rna_type, path),
                    owner=sub,
                    args=(self, obj.name, path),
                    notify=property_changed,
                )
                self.subscriptions.append(sub)
                self.log.info(f"Registered: {prop.identifier}")
            except Exception as e:
                # Some properties can't be subscribed to, skip those
                self.log.warning(f"Skipping {prop.identifier}")
                self.log.error(e)

        # Handle ALL custom properties
        if self.check_custom_props not in bpy.app.handlers.depsgraph_update_post:
            try:
                bpy.app.handlers.depsgraph_update_post.append(
                    self.check_custom_props)
                self.log.info(f"Tracking ALL properties for: {obj.name}")
            except Exception as e:
                self.log.error(
                    f"Failed to register handler for listening to property changes for {obj.name}")
                self.log.error(e)

    def obj_prop_change_update(self):
        if bpy.context.object is not None:
            if bpy.context.object.name != self.current_selected_object:
                self.track_all_properties(bpy.context.object)
                self.current_selected_object = bpy.context.object.name
                self.log.info(
                    f"Registered logging of properties to: {self.current_selected_object}")

    def get_mapping_template(self):
        """Returns a full copy of the mapping template (prevent reference issues)

        Returns:
            dict: mapping template
        """
        return copy.deepcopy(self.mapping_template)

    def get_mapping_pending(self):
        """Returns a full copy of the mapping that is currently pending (prevent reference issues)

        Returns:
            dict: mapping pending
        """
        return copy.deepcopy(self.mapping_pending)

    def parse_midi_messages_update(self):
        """Handle midi messages from midi controller.
        """
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
            self.log.error("Failed reading from midi controller!")
            self.log.error(traceback.format_exc())
            self.log.error(e)

    def frame_update(self):
        """Update the frame counter for frame control using midi input.
        """
        if self.controllers_to_set_frame_timeout > self.midi_update_rate:
            self.controllers_to_set_frame_timeout = round(
                self.controllers_to_set_frame_timeout - self.midi_update_rate, 3)
            self.redraw_ui()
        else:
            try:
                self.controllers_to_set_frame_current_frame = bpy.context.scene.frame_current
                if (self.controllers_to_set_frame_timeout != 0):
                    self.controllers_to_set_frame_timeout = 0
                    self.redraw_ui()
            except Exception as e:
                self.log.warning(
                    f"Failed to get current frame from bpy.context.scene")
                self.log.warning(e)

    def redraw_ui(self):
        """To make a property change visible blender has to be triggered to redraw the UI, this also applies the property change on the object.
        """
        if self.screens == None:
            return
        try:
            for screen in self.screens:
                for area in screen.areas:
                    area.tag_redraw()
        except Exception as e:
            self.log.info("Screen error")

    def update_data(self, mapping, new_value):
        """Updates a specific property based on the type of the property.

        Args:
            mapping (dict): the mapped property.
            new_value (int,float,str): the value to write to the property
        """
        if mapping["direct"]:
            self.set_path_value(mapping['path'], new_value)
        else:
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
            try:
                if len(bpy.context.selected_objects) > 0:
                    obj.hide_render = obj.hide_render
            except Exception as e:
                self.log.error(f"Failed to update UI/property")
                self.log.error(e)

    def insert_keyframes(self):
        """Allows to insert a key frame for mapped properties on a midi button input.
        """
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
                        self.log.info(e)
                        self.log.info(
                            "Ugly but functional way to skip properties that are not part of the selected object")

    def control_frame(self, direction, raw_value):
        """Allows a midi input to control the frame position.

        Args:
            direction (str): direction of frame to set
            raw_value (int): raw frame value.
        """
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
            self.log.info("Failed updating frame somehow...")
            self.log.info(e)

    def save(self, external=False):
        """Save the current midi control config. Default is part of the .blend project.

        Args:
            external (bool, optional): Save to a external json file. Defaults to False.

        Returns:
            str: The json dump if external is True, otherwise None.
        """
        to_save = {
            "controller_names": self.controller_names,
            "controller_mapping": self.controller_property_mapping,
            "selection_groups": {
                "mapping": self.controller_selection_mapping,
                "velocity": self.select_group_button_velocity_pressed
            },
            "controller_keyframe_bind": {
                "mapping": self.key_frame_control,
                "velocity": self.keyframe_insert_button_velocity_pressed
            },
            "frame_control": self.controllers_to_set_frame,
            "resolution_control": self.controls_to_set_resolution
        }

        try:
            self.loaded_json[self.connected_controller] = to_save
            if external:
                return json.dumps(self.loaded_json, indent=4)
            else:
                if bpy.data.texts.get("midicontrol") == None:
                    bpy.data.texts.new("midicontrol")
                bpy.data.texts["midicontrol"].clear()
                bpy.data.texts["midicontrol"].write(
                    json.dumps(self.loaded_json, indent=4))
                return None
        except Exception as e:
            self.log.info(e)
            return None

    def load(self, external=False, external_json=None):
        """Load midi control config.

        Args:
            external (bool, optional): Use external_json as input. Defaults to False.
            external_json (str, optional): External json path. Defaults to None.
        """
        self.log.info(f"Loading external: {external}")
        try:
            if bpy.data.texts.get("midicontrol") == None and external == False:
                self.log.info("Nothing stored, a fresh beginning!")
                self.save()
            else:
                if external:
                    self.loaded_json = json.load(external_json)
                    if self.connected_controller not in self.loaded_json:
                        self.save()
                    self.log.info(f"Loaded Config: {self.loaded_json}")
                else:
                    self.loaded_json = json.loads(
                        bpy.data.texts.get("midicontrol").as_string())
                    if self.connected_controller not in self.loaded_json:
                        self.save()
                    self.log.info(f"Loaded Config: {self.loaded_json}")

                loaded = self.loaded_json[self.connected_controller]
                try:
                    self.controller_names = loaded["controller_names"]
                except Exception as e:
                    self.log.error(f"Failed Reading Config: controller_names")
                    self.log.error(e)
                try:
                    self.controller_property_mapping = loaded["controller_mapping"]

                    for controller, mapping in self.controller_property_mapping.items():
                        self.log.info(mapping)
                        for map in mapping:
                            if "direct" not in map:
                                map["direct"] = False
                            if "path" not in map:
                                map["path"] = None
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_mapping")
                    self.log.error(e)

                try:
                    self.controller_selection_mapping = loaded["selection_groups"]["mapping"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: selection_groups->mapping")
                    self.log.error(e)
                try:
                    self.select_group_button_velocity_pressed = loaded[
                        "selection_groups"]["velocity"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: selection_groups->velocity")
                    self.log.error(e)
                try:
                    self.select_group_bind_selection_state = self.ControllerButtonBindingState.NONE
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: selection_groups->state")
                    self.log.error(e)

                try:
                    self.key_frame_control = loaded["controller_keyframe_bind"]["mapping"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->mapping")
                    self.log.error(e)
                try:
                    self.keyframe_insert_button_velocity_pressed = loaded[
                        "controller_keyframe_bind"]["velocity"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->velocity")
                    self.log.error(e)
                try:
                    self.select_group_bind_selection_state = self.ControllerButtonBindingState.NONE
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->state")
                    self.log.error(e)

                try:
                    self.controllers_to_set_frame = loaded["frame_control"]
                except Exception as e:
                    self.log.error(f"Failed Reading Config: frame_control")
                    self.log.error(e)

                try:
                    self.controls_to_set_resolution = loaded["resolution_control"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: resolution_control")
                    self.log.error(e)

                if external:
                    # Make sure that external overwrites the internal configuration.
                    self.save(external=False)

        except Exception as e:
            self.log.info("failed load ;(")
            self.log.info(e)

    def select_objects(self, objects):
        """Select specific objects.

        Args:
            objects (str): Name of object to select.
        """
        bpy.ops.object.select_all(action='DESELECT')
        for objname in objects:
            try:
                bpy.data.objects[objname].select_set(True)
            except Exception as e:
                self.log.warning(
                    f"Tried to select object {objname}, likely does not exist anymore!")
                self.log.warning(e)

    def midi_callback(self, midi_data):
        """Callback called when new midi_data is available.

        Args:
            midi_data (list[][]): first dimension: midi device, second dimension: data
        """
        try:
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

                found = (str(control) in self.controller_property_mapping.keys())
                self.midi_control_to_map = control
                if found == False:
                    self.midi_last_control_mapped = False
                else:
                    self.midi_last_control_mapped = True

                    for mapping in self.controller_property_mapping[str(control)]:
                        min = mapping["min"]
                        max = mapping["max"]
                        # allows for controlling with more granuality than the max 127 resolution

                        resolution = (self.controls_to_set_resolution["coarse_resolution"]) + (
                            ((1 / 127) * self.controls_to_set_resolution["fine_resolution"]))
                        new_value = (
                            (((max - min) / 127) * resolution) * value) + min
                        self.update_data(mapping, new_value)

                if self.controllers_to_set_frame["increase"]["state"] == self.ControllerButtonBindingState.PENDING:
                    if self.midi_last_control_mapped == False:
                        self.controllers_to_set_frame["increase"]["controller"] = control
                        self.controllers_to_set_frame["increase"]["state"] = self.ControllerButtonBindingState.BOUND
                        self.save()
                        self.midi_last_control_mapped = True
                elif self.controllers_to_set_frame["increase"]["controller"] == control:
                    self.midi_last_control_mapped = True
                    self.control_frame("increase", value)

                if self.controllers_to_set_frame["decrease"]["state"] == self.ControllerButtonBindingState.PENDING:
                    if self.midi_last_control_mapped == False:
                        self.controllers_to_set_frame["decrease"]["controller"] = control
                        self.controllers_to_set_frame["decrease"]["state"] = self.ControllerButtonBindingState.BOUND
                        self.save()
                        self.midi_last_control_mapped = True
                elif self.controllers_to_set_frame["decrease"]["controller"] == control:
                    self.midi_last_control_mapped = True
                    self.control_frame("decrease", value)

                if self.controls_to_set_resolution["set_fine_resolution"]["state"] == self.ControllerButtonBindingState.PENDING:
                    if self.midi_last_control_mapped == False:
                        self.controls_to_set_resolution["set_fine_resolution"]["controller"] = control
                        self.controls_to_set_resolution["set_fine_resolution"][
                            "state"] = self.ControllerButtonBindingState.BOUND
                        self.save()
                        self.midi_last_control_mapped = True
                elif self.controls_to_set_resolution["set_fine_resolution"]["controller"] == control:
                    self.midi_last_control_mapped = True
                    self.controls_to_set_resolution["fine_resolution"] = value

                if self.controls_to_set_resolution["set_coarse_resolution"]["state"] == self.ControllerButtonBindingState.PENDING:
                    if self.midi_last_control_mapped == False:
                        self.controls_to_set_resolution["set_coarse_resolution"]["controller"] = control
                        self.controls_to_set_resolution["set_coarse_resolution"][
                            "state"] = self.ControllerButtonBindingState.BOUND
                        self.save()
                        self.midi_last_control_mapped = True
                elif self.controls_to_set_resolution["set_coarse_resolution"]["controller"] == control:
                    self.midi_last_control_mapped = True
                    self.controls_to_set_resolution["coarse_resolution"] = value

                self.midi_last_control_value = value
            self.midi_last_control_changed = control
            self.redraw_ui()
        except Exception as e:
            self.log.error(f"Failed to handle midi input!")
            self.log.error(e)

    def close(self):
        """Closes properly the device and undoes any configuration that is currently opened.
    """
        for sub in self.subscriptions:
            try:
                bpy.msgbus.clear_by_owner(sub)
            except Exception as e:
                self.log.error(
                    "Failed unregistering rna subscription but likely already unregistered before.")
                self.log.error(e)
                continue
        try:
            self.subscriptions.clear()
        except Exception as e:
            self.log.error(
                "Failed unregistering rna subscription but likely already unregistered before.")
            self.log.error(e)

        try:
            if self.check_custom_props in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(
                    self.check_custom_props)
        except Exception as e:
            self.log.error(
                "Failed unregistering custom prop callback but likely already unregistered before.")
            self.log.error(e)

        if self.midi_open:
            if self.midi_input.is_port_open():
                self.midi_input.close_port()
            self.midi_input.delete()
            self.log.info(
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
