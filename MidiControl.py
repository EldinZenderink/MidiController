"""
Handles all midi interactions.
"""
import bpy
import copy
import traceback
import json
import logging
import rtmidi
from rtmidi.midiutil import open_midiinput
import time


def midicontroller_obj_selected_callback(self, *args):
    midi_controller_instance, _ = args
    if midi_controller_instance.running:
        # Update all selected objects for future reference usage.
        # This needs to be done to ensure that we do not get restricted context error
        # this error occurs because of the midi callback likely not having the correct
        # access to the bpy.context that contains the selected object, but the msgbus
        # callback does!
        midi_controller_instance.selected_objects_context = bpy.context.selected_objects

        # Then update the callbacks for property changes for the selected object, ensure
        # it only happens for the first selected object!
        if len(bpy.context.selected_objects) > 0:
            if bpy.context.selected_objects[0].name != midi_controller_instance.current_selected_object:
                midi_controller_instance.track_all_properties(
                    bpy.context.selected_objects[0])
                midi_controller_instance.current_selected_object = bpy.context.selected_objects[
                    0].name
                midi_controller_instance.log.info(
                    f"Registered logging of properties to: {midi_controller_instance.current_selected_object}")


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
                    new_obj['index'] = ig
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
        self.log.warning(traceback.format_exc())
        self.log.warning(
            f"Failed to check changes for property: {k} for object: {obj_name}")
        self.log.warning(e)


class MidiController_InputHandler():
    def __init__(self, midicontroller_instance, port):
        self.port = port
        self.midicontroller_instance = midicontroller_instance
        self._wallclock = time.time()

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        self.midicontroller_instance.parse_midi_messages_update(message)


class MidiController_Midi():
    # to register and control midi
    connected_controller = ""
    connected_port = None
    available_ports = None
    midi_input = None
    midi_open = False
    running = None
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
    controller_increase_frame_last_value = 0
    controller_decrease_frame_last_value = 0

    # midi update rate (If users experience slowdowns: this should be looked at.)
    midi_update_rate = 16  # milliseconds
    midi_last_message = 0

    # Some globals for object data.
    current_selected_object = None

    # Store subscriptions so they can be cleared later
    subscriptions = []
    last_custom_props = {}
    previous_property_value = {}
    propchange_last_time = 0

    # Subscription owners
    obj_sub_owner = None
    obj_change_sub_owner = None

    # Register logger
    log = None

    def enable_info_log(self):
        self.log.setLevel(logging.INFO)
        self.log.info("Enabled INFO level logging.")

    def disable_info_log(self):
        self.log.info("Disabled INFO level logging.")
        self.log.setLevel(logging.WARNING)

    def start(self):
        """Ensures not callback is left behind or previously registered.
        """
        # if already running, we do nothing.
        if self.running:
            return None

        # Set context
        self.selected_objects_context = bpy.context.selected_objects

        # Create single owner for msgbus subs
        self.obj_sub_owner = object()
        self.obj_change_sub_owner = object()

        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.WARNING)
        self.log.info("STARTED MIDI CONTROL!")

        # get current time since epoch in milliseconds
        self.midi_last_message = round(time.time() * 1000)
        self.propchange_last_time = round(time.time() * 1000)
        # setup midi
        self.midi_input = rtmidi.MidiIn()

        # set current frame
        self.controllers_to_set_frame_current_frame = bpy.context.scene.frame_current

        # Unregister any previous registered custom prop change callbacks (unlikely but just to be sure)
        if self.check_custom_props in bpy.app.handlers.depsgraph_update_post:
            self.log.warning(
                f"Found registered handler 'check_custom_props' which should have been deregistered!")
            bpy.app.handlers.depsgraph_update_post.remove(
                self.check_custom_props)

        # Register object selection callback.
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.LayerObjects, 'active'),
            owner=self.obj_change_sub_owner,
            args=("update_property", self, "dummy??"),
            notify=midicontroller_obj_selected_callback
        )

        # check if current object is selected
        if len(self.selected_objects_context) > 0:
            if self.selected_objects_context[0].name != self.current_selected_object:
                self.track_all_properties(self.selected_objects_context[0])
                self.current_selected_object = self.selected_objects_context[0].name
                self.log.info(
                    f"Registered logging of properties to: {self.current_selected_object}")

        self.refresh_available_midi_ports()

        self.running = True

    def refresh_available_midi_ports(self):
        self.log.info(f"Refreshing available midi ports")
        self.available_ports = rtmidi.MidiIn().get_ports()
        self.redraw_ui()

    def open_midi(self, port,):
        # Connect to the midi port (callback method)
        try:
            self.midi_input, port_name = open_midiinput(port)
            self.midi_input.set_callback(
                MidiController_InputHandler(self, port_name))
        except (EOFError, KeyboardInterrupt):
            self.log.critical(f"Could not open midi controller!")
            return None

        # self.midi_input.open_port(self.midi_port) <- old method
        self.midi_open = self.midi_input.is_port_open()

        # if opening port is successful set the connection information
        self.connected_port = port
        self.connected_controller = port_name

        # Ensure that the correct configuration for the midi controller is loaded in.
        self.load()

    def parse_midi_messages_update(self, data):
        """Handle midi messages from midi controller.
        """
        try:
            # get current time since epoch in milliseconds
            currenttime = round(time.time() * 1000)

            # ensure only update of anything after 16 milliseconds to prevent blasting the ui with redraw
            # calls.
            if (currenttime - self.midi_last_message) > self.midi_update_rate:
                self.midi_last_message = currenttime
                self.midi_callback(data)
            else:
                self.log.info("update to soon")
        except Exception as e:
            self.log.error("Failed reading from midi controller!")
            self.log.error(traceback.format_exc())
            self.log.error(e)

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
            self.log.error(traceback.format_exc())
            self.log.warning(f"Failed to write property using setattr:")
            self.log.warning(f"Data Path: {full_dp}, Value: {value}")
            self.log.warning(f"{e}")

    def check_custom_props(self, scene, x):
        """Handler to detect custom property changes."""

        # Prevent running code to often during callback,
        # we only need to see a change happen by a user,
        # the user wont change properties 100 times a second
        # and since only the change has to be detected we can wait
        # a bit between callbacks
        current_time = round(time.time() * 1000)
        diff = current_time - self.propchange_last_time
        if diff > 100:
            self.propchange_last_time = current_time
        else:
            return None

        try:
            obj = bpy.context.object
            if not obj:
                self.log.info(
                    f"Got change in property while not having any object selected, ignoring!")
                return
        except Exception as e:
            self.log.info("Context has no object, thus do nothing.")
            return None

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
                self.log.error(traceback.format_exc())
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
            self.log.warning(traceback.format_exc())
            self.log.warning(
                f"Failed to clear subscriptions before registering any for {obj.name}")

        # Get RNA type
        rna_type = type(obj)

        # Iterate over all RNA properties
        for prop in obj.bl_rna.properties:
            if prop.is_readonly or prop.identifier == "rna_type":
                continue

            path = prop.identifier

            self.log.info(f"Try registering: {prop.identifier}")
            try:
                bpy.msgbus.subscribe_rna(
                    key=(rna_type, path),
                    owner=self.obj_sub_owner,
                    args=(self, obj.name, path),
                    notify=property_changed,
                )
                self.subscriptions.append(self.obj_sub_owner)
                self.log.info(f"Registered: {prop.identifier}")
            except Exception as e:
                # Some properties can't be subscribed to, skip those
                self.log.warning(f"Skipping {prop.identifier}")
                self.log.error(e)
                self.log.error(traceback.format_exc())

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
                self.log.error(traceback.format_exc())

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

    def edit_property_mapping(self, editting_controller, mapped_property, index, edit_state):
        self.editting_controller = editting_controller
        self.editting_mapped = mapped_property
        self.editting_index = index
        self.edit_state = edit_state
        min = self.controller_property_mapping[editting_controller][index]['min']
        max = self.controller_property_mapping[editting_controller][index]['max']
        return min, max

    def save_property_mapping(self, controller_name, min, max):
        self.controller_property_mapping[self.editting_controller][
            self.editting_index]['min'] = min
        self.controller_property_mapping[self.editting_controller][
            self.editting_index]['max'] = max
        self.controller_names[str(
            self.editting_controller)] = controller_name
        self.editting_controller = None
        self.editting_mapped = None
        self.editting_index = None
        self.edit_state = self.EditState.NONE
        self.save()

    def delete_property_mapping(self):
        if len(self.controller_property_mapping[self.editting_controller]) > 1:
            self.controller_property_mapping[self.editting_controller].pop(
                self.editting_index)
        else:
            self.controller_property_mapping.pop(
                self.editting_controller, None)
        self.editting_controller = None
        self.editting_mapped = None
        self.editting_index = None
        self.edit_state = self.EditState.NONE
        self.save()

    def cancel_edit_property_mapping(self):
        self.editting_controller = None
        self.editting_mapped = None
        self.editting_index = None
        self.edit_state = self.EditState.NONE

    def start_update_key_frame_mapping(self):
        self.key_frame_bind_control_state = self.ControllerButtonBindingState.PENDING

    def reset_key_frame_mapping(self):
        self.key_frame_bind_control_state = self.ControllerButtonBindingState.NONE
        self.key_frame_control = None
        self.save()  # ensure current state is saved.

    def start_selection_group_mapping(self, name):
        array = None
        for obj in self.selected_objects_context:
            if array is None:
                array = [obj.name]
            else:
                array += [obj.name]

        # Prevent duplicate group names!
        matches = 0
        for control, selection_mapping in self.controller_selection_mapping:
            if selection_mapping["name"] == name:
                matches += 1

        if matches > 0:
            name = f"name_{matches}"

        to_map = {
            "selected": array,
            "name": name
        }

        self.selection_to_map = copy.deepcopy(to_map)
        self.select_group_bind_selection_state = self.ControllerButtonBindingState.PENDING

    def cancel_selection_group_mapping(self):
        self.selection_to_map = None
        self.select_group_bind_selection_state = self.ControllerButtonBindingState.NONE

    def delete_selection_group(self, controller):
        try:
            self.controller_selection_mapping.pop(
                controller, None)
        except Exception as e:
            self.log.warning("Potential issue while removing selection group!")
            self.log.warning(traceback.format_exc())

        self.save()

    def map_frame_selection_control(self, direction):
        self.log.info(f"Mapped frame selection control")
        if self.controllers_to_set_frame[direction]['state'] == self.ControllerButtonBindingState.NONE:
            self.controllers_to_set_frame[direction][
                'state'] = self.ControllerButtonBindingState.PENDING
        else:
            self.controllers_to_set_frame[direction][
                'state'] = self.ControllerButtonBindingState.NONE
        return int(self.controllers_to_set_frame['frame_control_resolution']), int(self.controllers_to_set_frame['timeout'])

    def save_frame_selection_control(self, frame_control_resolution, timeout):
        self.log.info(f"Saved frame selection control")
        self.controllers_to_set_frame["frame_control_resolution"] = frame_control_resolution
        self.controllers_to_set_frame["timeout"] = timeout
        self.save()
        return int(self.controllers_to_set_frame['frame_control_resolution']), int(self.controllers_to_set_frame['timeout'])

    def reset_frame_selection_control(self):
        self.controllers_to_set_frame = {
            "increase": {
                "state": self.ControllerButtonBindingState.NONE,
                "controller": None  # changes from the current frame into future frames
            },
            "decrease": {
                "state": self.ControllerButtonBindingState.NONE,
                # changes from the current frame into the past frames.
                "controller": None
            },
            # this is the resolution of the control (127/5 = 25.4 = 25 frames starting from the current frame)
            "frame_control_resolution": 5,
            # this allows for the system ot change the last frame position to the newly changed after this amount of time seeing no changes.
            "timeout": 1,
        }
        self.save()

    def map_resolution_selection(self, resolution_type):
        if self.controls_to_set_resolution[resolution_type]['state'] == self.ControllerButtonBindingState.NONE:
            self.controls_to_set_resolution[resolution_type][
                'state'] = self.ControllerButtonBindingState.PENDING
            resolution_factor = (float(self.controls_to_set_resolution["coarse_resolution"]) - 1.0) + (
                (1.0 / 128.0) * float(self.controls_to_set_resolution["fine_resolution"]))
            return resolution_factor

    def reset_map_resolution_selection(self, resolution_type):
        self.controls_to_set_resolution[resolution_type][
            'state'] = self.ControllerButtonBindingState.NONE
        self.controls_to_set_resolution[resolution_type][
            'controller'] = None

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
            self.log.info(traceback.format_exc())

    def update_data(self, mapping, new_value):
        """Updates a specific property based on the type of the property.

        Args:
            mapping (dict): the mapped property.
            new_value (int,float,str): the value to write to the property
        """
        if mapping["direct"]:
            self.set_path_value(mapping['path'], new_value)
        else:
            for obj in self.selected_objects_context:
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
                if len(self.selected_objects_context) > 0:
                    obj.hide_render = obj.hide_render
            except Exception as e:
                self.log.error(f"Failed to update UI/property")
                self.log.error(e)
                self.log.error(traceback.format_exc())

    def insert_keyframes(self):
        """Allows to insert a key frame for mapped properties on a midi button input.
        """
        for obj in self.selected_objects_context:
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
                        self.log.info(traceback.format_exc())

    def control_frame(self, direction):
        """Allows a midi input to control the frame position.

        Args:
            direction (str): direction of frame to set
            raw_value (int): raw frame value.
        """
        # try:
        if self.controllers_to_set_frame_current_frame != int(bpy.context.scene.frame_current):
            self.controllers_to_set_frame_current_frame = self.controllers_to_set_frame_current_frame
        if direction == "increase":
            self.controllers_to_set_frame_current_frame += self.controllers_to_set_frame[
                "frame_control_resolution"]
            bpy.context.scene.frame_set(
                self.controllers_to_set_frame_current_frame)
        else:
            self.controllers_to_set_frame_current_frame -= self.controllers_to_set_frame[
                "frame_control_resolution"]

            if self.controllers_to_set_frame_current_frame > 0:
                bpy.context.scene.frame_set(
                    int(self.controllers_to_set_frame_current_frame + 0.5))
            else:
                bpy.context.scene.frame_set(0)
            self.redraw_ui()

        # except Exception as e:
        #     self.log.info("Failed updating frame somehow...")
        #     self.log.info(e)
        #     self.log.info(traceback.format_exc())

    def save(self, external=None):
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
            "select_group_bind_selection_state": self.select_group_bind_selection_state,
            "controller_keyframe_bind": {
                "mapping": self.key_frame_control,
                "velocity": self.keyframe_insert_button_velocity_pressed
            },
            "key_frame_bind_control_state": self.key_frame_bind_control_state,
            "frame_control": self.controllers_to_set_frame,
            "resolution_control": self.controls_to_set_resolution
        }

        try:
            if self.connected_controller == "" or self.connected_controller is None or len(self.connected_controller) == 0:
                self.log.error(
                    f"Could not find connected controller while saving, perhaps saving after close?")
                return None

            self.loaded_json[self.connected_controller] = to_save

            # always write to project settings (to ensure its saved somewhere)
            if bpy.data.texts.get("midicontrol") == None:
                bpy.data.texts.new("midicontrol")
            bpy.data.texts["midicontrol"].clear()
            bpy.data.texts["midicontrol"].write(
                json.dumps(self.loaded_json, indent=4))

            # E.g. in case of wanting to reuse the config outside the .blend project.
            if external is not None:
                with open(external, "w") as outfile:
                    outfile.write(json.dumps(self.loaded_json, indent=4))
        except Exception as e:
            self.log.info(e)
            self.log.info(traceback.format_exc())
            return None

    def load(self, external=None):
        """Load midi control config.

        Args:
            external (bool, optional): Use external_json as input. Defaults to False.
            external_json (str, optional): External json path. Defaults to None.
        """
        self.log.info(f"Loading external: {external}")
        try:
            if bpy.data.texts.get("midicontrol") == None and external is None:
                self.log.info("Nothing stored, a fresh beginning!")
                self.save()
            else:
                if external is not None:
                    with open(external, "r") as openfile:
                        self.loaded_json = json.load(openfile)
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
                    self.log.error(traceback.format_exc())
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
                    self.log.error(traceback.format_exc())

                try:
                    self.controller_selection_mapping = loaded["selection_groups"]["mapping"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: selection_groups->mapping")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.select_group_button_velocity_pressed = loaded[
                        "selection_groups"]["velocity"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: selection_groups->velocity")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.select_group_bind_selection_state = loaded["select_group_bind_selection_state"]
                except Exception as e:
                    self.select_group_button_velocity_pressed = 0
                    self.select_group_bind_selection_state = self.ControllerButtonBindingState.NONE
                    self.log.error(
                        f"Failed Reading Config: selection_groups->state")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.key_frame_control = loaded["controller_keyframe_bind"]["mapping"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->mapping")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.keyframe_insert_button_velocity_pressed = loaded[
                        "controller_keyframe_bind"]["velocity"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->velocity")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.key_frame_bind_control_state = loaded["key_frame_bind_control_state"]
                except Exception as e:
                    self.keyframe_insert_button_velocity_pressed = 0
                    self.key_frame_bind_control_state = self.ControllerButtonBindingState.NONE
                    self.log.error(
                        f"Failed Reading Config: controller_keyframe_bind->state")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.controllers_to_set_frame = loaded["frame_control"]
                except Exception as e:
                    self.reset_frame_selection_control()
                    self.log.error(f"Failed Reading Config: frame_control")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                try:
                    self.controls_to_set_resolution = loaded["resolution_control"]
                except Exception as e:
                    self.log.error(
                        f"Failed Reading Config: resolution_control")
                    self.log.error(e)
                    self.log.error(traceback.format_exc())

                if external:
                    # Make sure that external overwrites the internal configuration.
                    self.save(external=False)
                else:
                    self.save()

        except Exception as e:
            self.log.critical("failed load ;(")
            self.log.critical(e)
            self.log.critical(traceback.format_exc())

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
                self.log.warning(traceback.format_exc())

    def midi_callback(self, midi_data):
        """Callback called when new midi_data is available.

        Args:
            midi_data (list[][]): first dimension: midi device, second dimension: data
        """
        try:
            velocity = midi_data[0]
            control = midi_data[1]
            value = midi_data[2]

            if velocity != self.midi_last_control_velocity:
                if self.key_frame_bind_control_state == self.ControllerButtonBindingState.PENDING:
                    self.key_frame_control = control
                    self.keyframe_insert_button_velocity_pressed = velocity
                    # self.save_to_blend()
                    self.key_frame_bind_control_state = self.ControllerButtonBindingState.BOUND
                    # ensure the bound key to frame control are saved.
                    self.save()

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
                    # ensure the selection group mapping are saved.
                    self.save()

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

                    # increase only when the value is higher than before
                    if (value > self.controller_increase_frame_last_value):
                        self.control_frame("increase")
                    self.controller_increase_frame_last_value = value

                if self.controllers_to_set_frame["decrease"]["state"] == self.ControllerButtonBindingState.PENDING:

                    if self.midi_last_control_mapped == False:
                        self.controllers_to_set_frame["decrease"]["controller"] = control
                        self.controllers_to_set_frame["decrease"]["state"] = self.ControllerButtonBindingState.BOUND
                        self.save()
                        self.midi_last_control_mapped = True
                elif self.controllers_to_set_frame["decrease"]["controller"] == control:
                    self.midi_last_control_mapped = True
                    # increase only when the value is higher than before
                    if (value > self.controller_decrease_frame_last_value):
                        self.control_frame("decrease")
                    self.controller_decrease_frame_last_value = value

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
            self.log.error(traceback.format_exc())
            self.log.error(f"Failed to handle midi input!")
            self.log.error(e)

    def close_midi(self):
        # ensure that all that is currently known is saved before closing
        self.save()
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
            self.running = None
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

            # Map a running control to a property somehow
            self.mapping_pending = None

            # Controller to edit
            self.editting_controller = None
            self.edit_state = self.EditState.NONE

            # Controller to register keyframe(s) (note: all properties)
            self.key_frame_control = None

            # Selection group buttons bound
            self.selection_to_map = None
            self.bind_selection_state = self.ControllerButtonBindingState.NONE

    def close(self):
        """Closes properly the device and undoes any configuration that is currently opened.
        """
        # Unregister any active subscription
        # for sub in self.subscriptions:
        try:
            bpy.msgbus.clear_by_owner(self.obj_sub_owner)
            bpy.msgbus.clear_by_owner(self.obj_change_sub_owner)
        except Exception as e:
            self.log.error(traceback.format_exc())
            self.log.error(
                "Failed unregistering rna subscription but likely already unregistered before.")
            self.log.error(e)

        # Unregister custom property callback handler (this is globally registered and not per selected object!)
        try:
            if self.check_custom_props in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(
                    self.check_custom_props)
        except Exception as e:
            self.log.error(traceback.format_exc())
            self.log.error(
                "Failed unregistering custom prop callback but likely already unregistered before.")
            self.log.error(e)

        self.close_midi()
