import blenderproc as bproc
import numpy as np
import bpy
import sys
import os
from skimage import measure
import argparse
from bpy_extras import mesh_utils
from mathutils import Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import genMaterial


def initiate():
    bproc.renderer.set_render_devices(
        desired_gpu_device_type=["CUDA"], desired_gpu_ids=0
    )
    bproc.renderer.enable_experimental_features()
    bproc.renderer.enable_diffuse_color_output()
    bproc.renderer.enable_segmentation_output(
        map_by=["instance", "class", "name"],
        default_values={"category_id": 1},
        pass_alpha_threshold=0,
    )

    bpy.ops.scene.view_layer_add_aov()
    compositor_node_tree = bpy.context.scene.node_tree
    render_layers_node = compositor_node_tree.nodes["Render Layers"]
    compositor_node_tree.links.new(
        render_layers_node.outputs["AOV"],
        compositor_node_tree.nodes["File Output"].inputs["Image"],
    )

    bproc.camera.set_resolution(args.resolution[0], args.resolution[1])


def create_obj(obj_path):
    obj, mat, _ = bproc.loader.load_blend(
        path=obj_path, obj_types="mesh", data_blocks=["objects", "materials"]
    )
    bpy_obj = obj.blender_obj
    bpy.context.view_layer.objects.active = bpy_obj
    bpy_obj.select_set(True)
    obj.set_name("Object of interest")
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    obj.set_shading_mode("AUTO")
    obj.enable_rigidbody(
        True, mass=1.0, friction=100.0, linear_damping=0.99, angular_damping=0.99
    )
    bpy_obj.modifiers.new(name="subsurf", type="SUBSURF")
    bpy_obj.modifiers["subsurf"].uv_smooth = "PRESERVE_CORNERS"
    bpy_obj.cycles.use_adaptive_subdivision = True

    proc_mat = bproc.material.convert_to_materials([mat])[0]
    obj.replace_materials(proc_mat)
    return obj


def sample_object_pose(obj: bproc.types.MeshObject):
    obj.set_rotation_euler(bproc.sampler.uniformSO3())
    obj.set_location([0, 0, 1])


parser = argparse.ArgumentParser()
parser.add_argument("-obj", dest="obj_path", type=str, required=True)
parser.add_argument("-cc", dest="cc_material_path", type=str, required=True)
parser.add_argument("-res", dest="resolution", nargs=2, type=int, default=[620, 620])
parser.add_argument("-runs", dest="runs", type=int, default=1)
parser.add_argument("-frames", dest="frames", type=int, default=1)
parser.add_argument("-fits", dest="needs_to_fit", action="store_true")
parser.add_argument("-random_texture", dest="random_texture", action="store_true")
parser.add_argument(
    "-lighting",
    dest="lighting_type",
    type=str,
    choices=["SPOT", "POINT"],
    default="SPOT",
)
args = parser.parse_args()

bproc.init()

initiate()
cc_textures = bproc.loader.load_ccmaterials(args.cc_material_path)
obj = create_obj(args.obj_path)
bounding_box_local = obj.get_bound_box(local_coords=True)
obj_reach = np.linalg.norm(bounding_box_local[0])
obj.set_scale([1 / obj_reach, 1 / obj_reach, 1 / obj_reach])
plane_size = 2
room_planes = [
    bproc.object.create_primitive("PLANE", scale=[plane_size, plane_size, 1]),
    bproc.object.create_primitive(
        "PLANE",
        scale=[plane_size, plane_size, 1],
        location=[0, -plane_size, plane_size],
        rotation=[-1.570796, 0, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[plane_size, plane_size, 1],
        location=[0, plane_size, plane_size],
        rotation=[1.570796, 0, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[plane_size, plane_size, 1],
        location=[plane_size, 0, plane_size],
        rotation=[0, -1.570796, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[plane_size, plane_size, 1],
        location=[-plane_size, 0, plane_size],
        rotation=[0, 1.570796, 0],
    ),
]
for plane in room_planes:
    plane.enable_rigidbody(
        False,
        collision_shape="BOX",
        mass=1.0,
        friction=100.0,
        linear_damping=0.99,
        angular_damping=0.99,
    )

# sample light color and strenght from ceiling
light_plane = bproc.object.create_primitive(
    "PLANE", scale=[3, 3, 1], location=[0, 0, 10]
)
light_plane.set_name("light_plane")
light_plane_material = bproc.material.create("light_material")

# sample point light on shell
light_point = bproc.types.Light("POINT")
light_point.set_energy(150)
light_spot = bproc.types.Light("SPOT")
light_spot.set_energy(50)

if args.lighting_type == "SPOT":
    light_point.hide(True)
else:
    light_spot.hide(True)

for run in range(args.runs):
    genMaterial.randomize_material(args.random_texture)

    sample_object_pose(obj)

    # Sample two light sources
    light_plane_material.make_emissive(
        emission_strength=np.random.uniform(3, 6),
        emission_color=np.random.uniform([0.5, 0.5, 0.5, 1.0], [1.0, 1.0, 1.0, 1.0]),
    )
    light_plane.replace_materials(light_plane_material)
    light_point.set_color(np.random.uniform([0.5, 0.5, 0.5], [1, 1, 1]))
    light_spot.set_color(np.random.uniform([0.5, 0.5, 0.5], [1, 1, 1]))
    location = bproc.sampler.shell(
        center=[0, 0, 0],
        radius_min=1,
        radius_max=1.5,
        elevation_min=5,
        elevation_max=89,
    )
    light_point.set_location(location)

    # sample CC Texture and assign to room planes
    random_cc_texture = np.random.choice(cc_textures)
    for plane in room_planes:
        plane.replace_materials(random_cc_texture)

    # Physics Positioning
    bproc.object.simulate_physics_and_fix_final_poses(
        min_simulation_time=3,
        max_simulation_time=10,
        check_object_interval=1,
        substeps_per_frame=20,
        solver_iters=25,
    )

    mesh_obj = obj.blender_obj.to_mesh()
    islands = mesh_utils.mesh_linked_uv_islands(mesh_obj)
    obj_world_matrix = obj.blender_obj.matrix_world
    obj_rot_matrix = obj.get_rotation_mat()

    selected_polys = [mesh_obj.polygons[idx] for idx in islands[2]]
    areas = [selected_poly.area for selected_poly in selected_polys]
    p = np.array(areas) / sum(areas)
    flat_forbidden_indices = [idx for sublist in islands[0:2] for idx in sublist]
    forbidden_polys = [mesh_obj.polygons[idx] for idx in flat_forbidden_indices]

    for i in range(args.frames):
        fits = False
        while fits == False:
            fits = True
            poly = np.random.choice(selected_polys, p=p)

            vertex_coords = [mesh_obj.vertices[idx].co for idx in poly.vertices]
            vector_a = vertex_coords[1] - vertex_coords[0]
            vector_c = vertex_coords[2] - vertex_coords[3]

            dim_1_mult = np.random.random()
            dim_2_mult = np.random.random()

            spot_on_a = vertex_coords[0] + vector_a * dim_1_mult
            spot_on_c = vertex_coords[3] + vector_c * dim_1_mult

            final_spot_local = spot_on_a + (spot_on_c - spot_on_a) * dim_2_mult

            final_spot = obj_world_matrix @ final_spot_local
            normal = obj_rot_matrix @ poly.normal

            x_val = normal[0]
            y_val = normal[1]

            angle = np.rad2deg(np.arctan2(y_val, x_val))

            azimuth_borders = [angle - 20, angle + 20]

            for idx in range(2):
                if azimuth_borders[idx] > 180:
                    azimuth_borders[idx] -= 360
                elif azimuth_borders[idx] < -180:
                    azimuth_borders[idx] += 360

            cam_location = bproc.sampler.shell(
                center=final_spot,
                radius_min=0.3,
                radius_max=0.4,
                elevation_min=30,
                elevation_max=90,
                azimuth_min=min(azimuth_borders),
                azimuth_max=max(azimuth_borders),
            )

            cam_rotation = bproc.camera.rotation_from_forward_vec(
                forward_vec=final_spot - Vector(cam_location)
            )

            cam_pose = bproc.math.build_transformation_mat(cam_location, cam_rotation)

            # Check if camera is inside room
            for cam_coord in cam_location[0:2]:
                if abs(cam_coord) > plane_size:
                    fits = False

            obj_bvh_tree = obj.create_bvh_tree()
            if not bproc.camera.perform_obstacle_in_view_check(
                cam2world_matrix=cam_pose,
                proximity_checks={"min": 0.2},
                bvh_tree=obj_bvh_tree,
            ):
                fits = False

            # Check if camera is inside object
            relative_cam_location = cam_location - obj.get_location()
            _, closest, normal, _ = obj.blender_obj.closest_point_on_mesh(
                relative_cam_location
            )
            cam_to_closest = closest - Vector(relative_cam_location)
            if cam_to_closest.dot(normal) >= 0:
                fits = False

            bproc.camera.add_camera_pose(cam2world_matrix=cam_pose, frame=i)
            light_spot.set_location(location=cam_location, frame=i)
            light_spot.set_rotation_mat(
                rotation_mat=cam_rotation,
                frame=i,
            )

            if args.needs_to_fit:
                for forbidden_poly in forbidden_polys:
                    point = obj_world_matrix @ forbidden_poly.center
                    if bproc.camera.is_point_inside_camera_frustum(
                        point=point, frame=i
                    ):
                        ray = bproc.object.scene_ray_cast(
                            cam_location, point - Vector(cam_location)
                        )
                        if ray[0] and ray[3] in forbidden_poly.loop_indices:
                            fits = False
                            break

    data = bproc.renderer.render()
    for f in range(args.frames):
        active_diff = np.array(data["diffuse"][f])
        del data["instance_attribute_maps"][f][:]
        scratchMap = np.ones((active_diff.shape[0], active_diff.shape[1]))
        mask00 = active_diff[:, :, 0] == 0
        mask01 = active_diff[:, :, 1] == 0
        mask02 = active_diff[:, :, 2] == 0
        mask10 = active_diff[:, :, 0] == 1
        mask11 = active_diff[:, :, 1] == 1
        mask12 = active_diff[:, :, 2] == 1
        mask = np.logical_or(
            np.logical_and(mask00, mask01, mask02),
            np.logical_and(mask10, mask11, mask12),
        )
        scratchMap[mask] = 0
        labels = measure.label(scratchMap)
        data["instance_segmaps"][f] = labels
        label_props = measure.regionprops(labels)

        for l in label_props:
            if l.area > 10:
                id = l.label
                data["instance_attribute_maps"][f].append(
                    {"idx": id, "category_id": 1, "name": "scratch"}
                )

    bproc.writer.write_coco_annotations(
        "/output",
        instance_segmaps=data["instance_segmaps"],
        instance_attribute_maps=data["instance_attribute_maps"],
        colors=data["colors"],
        color_file_format="JPEG",
        indent=4,
        label_mapping=bproc.python.utility.LabelIdMapping.LabelIdMapping.from_dict(
            {"scratch": 1}
        ),
    )

    bproc.utility.reset_keyframes()