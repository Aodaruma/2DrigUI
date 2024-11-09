"""
Copyright (C) 2023 Aodaruma
hi@aodaruma.net

Created by Aodaruma

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
from typing import Callable
import bpy
import bpy_extras
import bpy_extras.view3d_utils
import mathutils
from mathutils import Vector, Matrix, Quaternion, geometry
import math
import bmesh
from bpy.props import (
    FloatProperty,
    IntProperty,
    BoolProperty,
    StringProperty,
    CollectionProperty,
    FloatVectorProperty,
    EnumProperty,
    IntVectorProperty,
)
from mathutils import Vector, Matrix, Quaternion

import bgl
import blf
from math import radians, degrees
import traceback
import gpu
from gpu_extras.batch import batch_for_shader
import pdb

# -------------------------------------------------------------------


class COATOOLS2_OT_Create2DrigABC(bpy.types.Operator):
    RIGS_DATA_CONTAINER_NAME = "COA_Rigs_data"

    bone_name: bpy.props.StringProperty(
        name="Bone Name",
        description="Name of the bone to use for the slider",
        default="ui.slider",
    )

    label: bpy.props.StringProperty(
        name="Label",
        description="Label of the slider",
        default="Text",
    )

    location: bpy.props.FloatVectorProperty(
        name="Location",
        description="Location of the slider",
        default=(0.0, 0.0, 0.0),
        subtype="XYZ",
    )

    _rigs_collection = bpy.props.PointerProperty()
    amt = bpy.props.PointerProperty()
    root_bone = bpy.props.PointerProperty()
    text_obj = bpy.props.PointerProperty()

    @property
    def rigs_collection(self) -> bpy.types.Collection:
        """
        Get the rigs collection
        """
        if (
            self._rigs_collection is None
            and self.RIGS_DATA_CONTAINER_NAME not in bpy.data.collections
        ):
            override = bpy.context.copy()
            override["selected_objects"] = []
            with bpy.context.temp_override(**override):
                bpy.ops.collection.create(name=self.RIGS_DATA_CONTAINER_NAME)

            collection = bpy.data.collections[self.RIGS_DATA_CONTAINER_NAME]
            collection.use_fake_user = True
            collection.hide_viewport = True
            collection.hide_render = True

            self._rigs_collection = collection

        return self._rigs_collection

    def createTextObject(self, text: str, size: float):
        """
        Create a text object
        """
        # Create text object
        mode = bpy.context.object.mode
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.text_add()
        txt: bpy.types.Object = bpy.context.object

        txt.name = text
        txt.show_name = False
        tcu: bpy.types.TextCurve = txt.data
        tcu.name = text

        # TextCurve attributes
        tcu.body = text
        tcu.font = bpy.data.fonts[0]
        tcu.size = size
        tcu.align_x = "CENTER"
        tcu.align_y = "TOP"

        txt.draw_type = "WIRE"

        # add to collection
        self._rigs_collection.objects.link(txt)

        bpy.ops.object.mode_set(mode=mode)

        self.text_obj = txt
        # return txt

    def createRootBone(self, arm: bpy.types.Armature):
        """
        Create a root bone
        """
        # Create bones
        bpy.ops.object.mode_set(mode="EDIT")

        bone = arm.edit_bones.new(self.bone_name)
        loc = Vector(self.location)
        bone.head = loc
        bone.tail = loc + Vector((0, 0, 1))
        bone.use_deform = False
        bone.use_inherit_rotation = False
        bone.use_local_location = True
        bone.show_wire = True
        # bone.show_x_ray = True

        # return bone
        self.root_bone = bone

    def create_slider(self, context: bpy.types.Context, arm: bpy.types.Armature):
        raise NotImplementedError

    @classmethod
    def poll(cls, context):
        return functions.is_the_active_object_is_coatools_armature(context)

    def execute(self, context):
        arm: bpy.types.Armature = context.object.data
        self.create_slider(context, arm)
        return {"FINISHED"}


class COATOOLS2_OT_Create2DSlider(COATOOLS2_OT_Create2DrigABC):
    """Create a 2D slider on the active coa_tools2 armature"""

    bl_idname = "coa_tools2.create_2d_slider"
    bl_label = "Create 2D Slider"
    bl_options = {"REGISTER", "UNDO"}

    value_type: bpy.props.EnumProperty(
        name="Value Type",
        description="Type of value to control",
        items=[
            ("int", "Integer", "Integer"),
            ("float", "Float", "Float"),
        ],
        default="float",
    )

    height: bpy.props.FloatProperty(
        name="Height",
        description="Height of the slider",
        default=1.0,
        min=0.1,
        soft_max=5.0,
    )

    width: bpy.props.FloatProperty(
        name="Width",
        description="Width of the slider",
        default=1.0,
        min=0.1,
        soft_max=5.0,
    )

    padding: bpy.props.FloatProperty(
        name="Padding",
        description="Padding of the slider",
        default=0.1,
        min=0.0,
        soft_max=1.0,
    )

    def createShape(self, context: bpy.types.Context, arm: bpy.types.Armature):
        """
        create holder and slider shape
        """

        # Create holder shape
        bpy.ops.mesh.primitive_plane_add(
            size=1.0, enter_editmode=False, align="WORLD", location=(0, 0, 0)
        )
        holder: bpy.types.Object = bpy.context.object
        holder.name = "holder"
        holder.data.name = "holder"

        # edit holder shape
        bpy.context.view_layer.objects.active = holder
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.transform.resize(
            value=(self.width, self.height, 1.0), orient_type="LOCAL"
        )
        bpy.ops.transform.translate(
            value=(0, self.height / 2 + self.padding, 0), orient_type="LOCAL"
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        # --------------------------------------------------
        # Create slider shape
        bpy.ops.mesh.primitive_plane_add(
            size=1.0, enter_editmode=False, align="WORLD", location=(0, 0, 0)
        )
        slider: bpy.types.Object = bpy.context.object
        slider.name = "slider"
        slider.data.name = "slider"

        # edit slider shape
        bpy.context.view_layer.objects.active = slider
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.transform.resize(
            value=(self.width, self.width, 1.0), orient_type="LOCAL"
        )
        bpy.ops.transform.translate(
            value=(0, -self.width / 2 - self.padding, 0), orient_type="LOCAL"
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        # --------------------------------------------------

        # add to collection
        self._rigs_collection.objects.link(holder)
        self._rigs_collection.objects.link(slider)

        return holder, slider

    def create_slider(self, context: bpy.types.Context, arm: bpy.types.Armature):
        obj = context.object
        cursol_loc = bpy.context.scene.cursor.location

        root_bone = self.createRootBone(arm)
        text_obj = self.createTextObject(self.label, self.height)

        holder, slider = self.createShape(context, arm)

        # create bones
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        holder_bone = arm.edit_bones.new("holder")
        holder_bone.use_connect = False
        holder_bone.parent = root_bone
        holder_bone.head = root_bone.head + Vector((0, 0, 0.5))
        holder_bone.tail = root_bone.head + Vector((0, 0, 1.5))

        slider_bone = arm.edit_bones.new("slider")
        slider_bone.parent = holder_bone
        slider_bone.head = holder_bone.head
        slider_bone.tail = holder_bone.head + Vector((0, 0, 1))

        bpy.ops.object.mode_set(mode="POSE")
        # set custom shape

        root_bone: bpy.types.PoseBone = obj.pose.bones.get(root_bone.name)
        holder_bone: bpy.types.PoseBone = obj.pose.bones.get(holder_bone.name)
        slider_bone: bpy.types.PoseBone = obj.pose.bones.get(slider_bone.name)

        root_bone.custom_shape = text_obj
        holder_bone.custom_shape = holder
        slider_bone.custom_shape = slider

        # set constraints
        con = slider_bone.constraints.new("LIMIT_LOCATION")
        con.owner_space = "LOCAL"
        con.use_min_x = True
        con.min_x = 0.0
        con.use_max_x = True
        con.max_x = self.width

        con.use_min_y = True
        con.min_y = 0.0
        con.use_max_y = True
        con.max_y = self.height

        con.use_transform_limit = True
