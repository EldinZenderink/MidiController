# MidiControl Plugin Documentation

## Introduction
The **MidiControl** plugin enables you to connect a MIDI device to Blender and control the values of objects (e.g., location, rotation, scale) or any other numeric input — including geometry nodes, brush settings, and more — via your MIDI controller’s inputs.

---

## Functionalities

### 1. Property Mapping

The plugin supports two distinct mapping methods:

#### **Method 1 – Object Property Mapping**
Used for mapping properties shared by multiple objects in Blender.

**Steps:**
1. Move the MIDI control you wish to assign on your MIDI device.
2. Adjust the value of the desired property in Blender.
3. The plugin automatically detects the last property you changed. Click the **Map** button.
4. Set the mapping name, along with the minimum and maximum values.
5. The property is now linked to your MIDI control.

> **Note:** Changes apply **only** to the currently selected object(s) in the viewport. You may select one or multiple objects to affect.
> This method **cannot** be used for brush properties or other specialized values like geometry nodes. Use **Method 2** for such cases.

---

#### **Method 2 – Direct “Full Data Path” Mapping**
Ideal for mapping a specific property of a single object, independent of which object is selected.

**Steps:**
1. Move the MIDI control you wish to assign on your MIDI device.
2. In Blender, right‑click the property you want to map and select **Copy Full Data Path**.
3. The plugin detects the copied data path. Click the **Map** button.
4. Set the mapping name, along with the minimum and maximum values.
5. The property is now linked to your MIDI control.

> **Tip:** This method also works for brush settings, geometry nodes, and other changeable Blender properties.

---

### 2. Selection Groups

Create groups of objects that can be selected instantly via a mapped MIDI control button. This allows rapid switching between object sets during a workflow.

---

### 3. Resolution Control

Adjust the granularity of property value changes.
You can map **two MIDI controls** to act as **Fine** and **Coarse** resolution factors, which are multiplied by the main MIDI input to refine control sensitivity.

---

### 4. Keyframe Insertion

Bind a MIDI button to insert a keyframe for **all mapped properties** of the currently selected object.

---

### 5. Frame Control

Use a MIDI control to navigate the timeline by adjusting the current frame position.


## Dependencies

The current midi python module used for this plugin is: [rtmidi2](https://github.com/gesellkammer/rtmidi2)
