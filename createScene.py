import blenderproc as bproc
import numpy as np
import bpy
import sys
import os
from skimage import measure
import argparse
from bpy_extras import mesh_utils
from mathutils import Vector

sys.path.append(os.path.dirname(bpy.data.filepath))
import genMaterial

# Bproc debug support for VSCode
# only works with blenderproc run 
DEBUG = False
if DEBUG:
    import debugpy
    debugpy.listen(5678)
    debugpy.wait_for_client()
## END DEBUG
USE_CPU = False

def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend_file", dest="blend_path", type=str, required=True)
    parser.add_argument(
        "--cc_material_path", dest="cc_material_path", type=str, required=True
    )
    parser.add_argument(
        "--resolution", dest="resolution", nargs=2, type=int, default=[640, 640]
    )
    parser.add_argument("--runs", dest="runs", type=int, default=1)
    parser.add_argument("--frames", dest="frames", type=int, default=1)
    parser.add_argument("--random_texture", dest="random_texture", action="store_true")
    parser.add_argument("--random_background", dest="random_background", action="store_true")
    parser.add_argument(
        "--setup",
        dest="setup_type",
        type=str,
        choices=["tripod", "random"],
        default="tripod",
    )
    parser.add_argument("--length", dest="length", type=float, required=True)
    return parser

def initiate():
    bproc.init()
    if USE_CPU:
        bproc.renderer.set_render_devices(use_only_cpu=True)
    else:
        bproc.renderer.set_render_devices(
            desired_gpu_device_type=["CUDA"],
            # adjust number of available GPUs
            desired_gpu_ids=[0, 1]
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
    bproc.camera.set_intrinsics_from_blender_params(
        lens=np.deg2rad(61.23544725), lens_unit="FOV", clip_start=0.001, clip_end=2
    )


def create_obj(blend_path, real_length):
    objects = bproc.loader.load_blend(path=blend_path, data_blocks=["objects"])
    materials = bproc.loader.load_blend(path=blend_path, data_blocks=["materials"], name_regrex="white_leather")
    root = bproc.filter.one_by_attr(objects, "name", "root")
    paint = bproc.filter.one_by_attr(objects, "name", "Paint_Geo_lodA")
    paint_mat = paint.blender_obj.material_slots
    white_bg = bproc.material.convert_to_materials(materials)
    obj_bound_box = bproc.filter.one_by_attr(objects, "name", "Carbon2_Geo_lodA").get_bound_box(local_coords=True)
 
    bpy_obj = root.blender_obj
    bpy.context.view_layer.objects.active = bpy_obj
    bpy_obj.select_set(True)
    root.set_name("Object of interest")
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    #bpy.ops.mesh.customdata_custom_splitnormals_clear()
 
    obj_length = 2 * np.max(obj_bound_box)
    obj_scale = real_length / obj_length
    root.set_scale([obj_scale, obj_scale, obj_scale])
    obj_reach = np.linalg.norm(obj_bound_box[0]) * obj_scale
 
    #root.set_shading_mode("AUTO")
    #bpy_obj.modifiers.new(name="subsurf", type="SUBSURF")
    #bpy_obj.modifiers["subsurf"].uv_smooth = "PRESERVE_CORNERS"
    bpy_obj.cycles.use_adaptive_subdivision = True
 
    for mat_slot in paint_mat:
        bproc_mat = bproc.material.convert_to_materials([mat_slot.material])[0]
        paint.set_material(mat_slot.slot_index, bproc_mat)
 
    # set selection to paint again
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = bpy_obj
    bpy_obj.select_set(True)
    return root, paint, obj_reach, white_bg


def sample_object_pose(obj: bproc.types.MeshObject, obj_reach):
    current_rotation = obj.blender_obj.rotation_euler

    new_rotation = (
        current_rotation.x,
        current_rotation.y,
        np.random.uniform(0, 2 * np.pi)
    )
    obj.set_rotation_euler(new_rotation)
    new_location = np.random.uniform(
        low=[-0.3 + obj_reach, -0.6 + obj_reach],
        high=[0.3 - obj_reach, 0.6 - obj_reach],
    )
    obj.set_location(np.append(new_location, 0))

def find_island(islands, poly_idx):
    for island_index, island in enumerate(islands):
        for idx in island:
            if idx == poly_idx:
                return island_index
    return None  

parser = create_parser()
args = parser.parse_args()

initiate()    
obj, paint, obj_reach, white_bg = create_obj(args.blend_path, args.length)

if(args.random_background):
    bg_textures = bproc.loader.load_ccmaterials(args.cc_material_path)
else:
    if(len(white_bg) == 0):
        raise ValueError("Missing white background texture. Please provide valid texture and load it accordingly in create_obj.")    
    bg_textures = white_bg    

room_planes = [
    bproc.object.create_primitive("PLANE", scale=[0.3, 0.6, 1]),
    bproc.object.create_primitive(
        "PLANE",
        scale=[0.3, 0.3, 1],
        location=[0, -0.6, 0.3],
        rotation=[-1.570796, 0, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[0.3, 0.3, 1],
        location=[0, 0.6, 0.3],
        rotation=[1.570796, 0, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[0.3, 0.6, 1],
        location=[0.3, 0, 0.3],
        rotation=[0, -1.570796, 0],
    ),
    bproc.object.create_primitive(
        "PLANE",
        scale=[0.3, 0.6, 1],
        location=[-0.3, 0, 0.3],
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
area_light_1 = bproc.types.Light(light_type="AREA", name="area_light_1")
area_light_2 = bproc.types.Light(light_type="AREA", name="area_light_2")
area_light_1.set_location([0.25, -0.5, 1.27])
area_light_2.set_location([0.25, 0.5, 1.27])
area_light_1_blend = area_light_1.blender_obj
area_light_2_blend = area_light_2.blender_obj
area_light_1_blend.data.shape = "RECTANGLE"
area_light_2_blend.data.shape = "RECTANGLE"
area_light_1_blend.data.size = 0.5
area_light_1_blend.data.size_y = 0.08
area_light_2_blend.data.size = 0.5
area_light_2_blend.data.size_y = 0.08

for run in range(args.runs):
    genMaterial.randomize_material(args.random_texture)

    sample_object_pose(obj, obj_reach)
    bpy.context.view_layer.update()

    area_light_color = np.random.uniform([0.5, 0.5, 0.5], [1, 1, 1])
    area_light_1.set_color(area_light_color)
    area_light_2.set_color(area_light_color)
    area_light_1.set_energy(np.random.randint(20, 80))
    area_light_2.set_energy(np.random.randint(20, 80))

    # assign texture to room planes
    random_bg_texture = np.random.choice(bg_textures)
    for plane in room_planes:
        plane.replace_materials(random_bg_texture)
    
    mesh_obj = paint.blender_obj.to_mesh()
    all_islands = mesh_utils.mesh_linked_uv_islands(mesh_obj)
    islands = []
    # find correct islands for corresponding polygon index
    # directions are denoted in the direction of travel
    #
    # left door
    islands.append(find_island(all_islands, 28008))
    # right door
    islands.append(find_island(all_islands, 7070))
    # right fender
    islands.append(find_island(all_islands, 3030))
    # left fender
    islands.append(find_island(all_islands, 5181))
    # upper hood
    islands.append(find_island(all_islands, 27154))
    # lower hood
    islands.append(find_island(all_islands, 9029))
    # side panel left
    islands.append(find_island(all_islands, 26638))
    # side panel right
    islands.append(find_island(all_islands, 25722))
    # rear 
    islands.append(find_island(all_islands, 14083))
    # rear spoiler
    islands.append(find_island(all_islands, 22205))

    obj_world_matrix = obj.blender_obj.matrix_world
    obj_rot_matrix = obj.get_rotation_mat()
    selected_polys = [mesh_obj.polygons[idx] for isl_idx in islands for idx in all_islands[isl_idx]]
    areas = [selected_poly.area for selected_poly in selected_polys]
    p = np.array(areas) / sum(areas)
    flat_forbidden_indices = []
    for sublist in all_islands:
        for island in sublist:
            if island not in islands:
                flat_forbidden_indices.append(island)

    forbidden_polys = [mesh_obj.polygons[idx] for idx in flat_forbidden_indices]
    
    for i in range(args.frames):
        fits = False
        while fits == False:
            fits = True
            poly = np.random.choice(selected_polys, p=p)

            vertex_coords = [mesh_obj.vertices[idx].co for idx in poly.vertices]
            vector_a = vertex_coords[1] - vertex_coords[0]
            vector_c = vertex_coords[2] - vertex_coords[1]

            dim_1_mult = np.random.random()
            dim_2_mult = np.random.random()

            spot_on_a = vertex_coords[0] + vector_a * dim_1_mult
            spot_on_c = vertex_coords[2] + vector_c * dim_1_mult

            final_spot_local = spot_on_a + (spot_on_c - spot_on_a) * dim_2_mult

            final_spot = obj_world_matrix @ final_spot_local

            cam_location = None
            if args.setup_type == "random":
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
                    radius_min=0.02,
                    radius_max=0.05,
                    elevation_min=30,
                    elevation_max=90,
                    azimuth_min=min(azimuth_borders),
                    azimuth_max=max(azimuth_borders),
                )
            elif args.setup_type == "tripod":
                cam_height = np.random.uniform(0.12, 0.13)
                cam_location = bproc.sampler.disk(
                    center=final_spot, radius=0.03, sample_from="disk"
                )
                cam_location[2] = cam_height

            cam_rotation = bproc.camera.rotation_from_forward_vec(
                forward_vec=final_spot - Vector(cam_location)
            )

            cam_pose = bproc.math.build_transformation_mat(cam_location, cam_rotation)

            # Check if camera is inside room
            if abs(cam_location[0]) > 0.3:
                fits = False
            if abs(cam_location[1]) > 0.6:
                fits = False

            obj_bvh_tree = paint.create_bvh_tree()
            if not bproc.camera.perform_obstacle_in_view_check(
                cam2world_matrix=cam_pose,
                proximity_checks={"min": 0.01},
                bvh_tree=obj_bvh_tree,
            ):
                fits = False

            bproc.camera.add_camera_pose(cam2world_matrix=cam_pose, frame=i)
            frustum_close = bproc.camera.get_camera_frustum(
                clip_start=0.001, clip_end=0.01, frame=i
            )
            cam_points = np.append(arr=frustum_close, values=[cam_location], axis=0)
            # Check if camera is inside object
            for cam_point in cam_points:
                relative_cam_point = obj_world_matrix.inverted() @ Vector(cam_point)
                _, closest, normal, _ = paint.blender_obj.closest_point_on_mesh(
                    relative_cam_point
                )
                cam_to_closest = closest - Vector(relative_cam_point)
                if cam_to_closest.dot(normal) >= 0:
                    fits = False

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
            if l.area > 25:
                id = l.label
                data["instance_attribute_maps"][f].append(
                    {"idx": id, "category_id": 1, "name": "scratch"}
                )

    bproc.writer.write_coco_annotations(
        #change to /output for usage with the sample synth_datagen.sh script
        "./output",
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