import bpy
import numpy as np
import cairo
import random
from PIL import Image, ImageFilter

mask_index = 0

DEBUG = False
# taken from https://pycairo.readthedocs.io/en/latest/tutorial/pillow.html
def to_pil(surface: cairo.ImageSurface) -> Image:
    format = surface.get_format()
    size = (surface.get_width(), surface.get_height())
    stride = surface.get_stride()

    with surface.get_data() as memory:
        if format == cairo.Format.RGB24:
            return Image.frombuffer(
                "RGB", size, memory.tobytes(), "raw", "BGRX", stride
            )
        elif format == cairo.Format.ARGB32:
            return Image.frombuffer(
                "RGBA", size, memory.tobytes(), "raw", "BGRa", stride
            )
        else:
            raise NotImplementedError(repr(format))


def randomize_scratch_image():
    global mask_index
    mask_path = (
        "/masks/scratch_image_"
        + str(mask_index)
        + ".png"
    )
    mask_index += 1
    original_size = 8192
    width, height = original_size, original_size
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    ctx = cairo.Context(surface)

    ctx.set_source_rgb(0, 0, 0)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    ctx.set_source_rgb(1, 1, 1)

    num_scratches = np.random.randint(50, 70)
    #TODO: remove
    print("number of scratches:", num_scratches)


    for scratch_idx in range(num_scratches):
        """
        if random.random() <= 0.95:
            brush_size =  np.random.uniform(1.96, 3.1)
        else:
            brush_size = np.random.uniform(5, 7)
        """
        brush_size =  np.random.uniform(1.96, 7)
                        
        scratch_sizes = ["small", "medium1", "medium2", "big1", "big2"]
        weights = [ 0.22, 0.25, 0.4, 0.1, 0.03]
        scratch_size = random.choices(scratch_sizes, weights=weights, k=1)[0]

        match scratch_size:
            case "small":
                    scratch_dim = np.array([width / 120, width / 120]) 
                    scratch_position = np.random.randint((0, 0), (width, height) - scratch_dim)
                    start_point, end_point = calc_endpoints(scratch_dim, width, height)
                    if random.random() <= 0.25:
                        # generate more pronounced curves
                        control_point_1 = start_point + (end_point - start_point) * 0.20 + np.random.randint(-50, 50, 2)
                        control_point_2 = start_point + (end_point - start_point) * 0.30 + np.random.randint(-60, 60, 2)          
                    else:
                        # generate more subtle curves
                        control_point_1 = start_point + (end_point - start_point) * 0.10 + np.random.randint(-30, 30, 2)
                        control_point_2 = start_point + (end_point - start_point) * 0.24 + np.random.randint(-47, 45, 2)             
            case "medium1":
                    scratch_dim = np.random.randint(width / 75, width / 50, 2)
                    scratch_position = np.random.randint((0, 0), (width, height) - scratch_dim)
                    start_point, end_point = calc_endpoints(scratch_dim, width, height)
                    if random.random() < 0.1:
                        control_point_1 = start_point + (end_point - start_point) * 0.33 + np.random.randint(-350, 350, 2)
                        control_point_2 = start_point + (end_point - start_point) * 0.67 + np.random.randint(-150, 150, 2)       
                    else:
                        control_point_1 = start_point + (end_point - start_point) * 0.20 + np.random.randint(-50, 50, 2)
                        control_point_2 = start_point + (end_point - start_point) * 0.30 + np.random.randint(-60, 60, 2)                    
            case "medium2":
                    scratch_dim = np.array([width / 30, width / 30]) 
                    scratch_position = np.random.randint((0, 0), (width, height) - scratch_dim)
                    start_point, end_point = calc_endpoints(scratch_dim, width, height)
                    control_point_1 = start_point + (end_point - start_point) * 0.33 + np.random.randint(-350, 350, 2)
                    control_point_2 = start_point + (end_point - start_point) * 0.67 + np.random.randint(-150, 150, 2)  
            case "big1":
                    scratch_dim = np.array([width / 14, width / 14]) 
                    scratch_position = np.random.randint((0, 0), (width, height) - scratch_dim)
                    start_point, end_point = calc_endpoints(scratch_dim, width, height)
                    control_point_1 = start_point + (end_point - start_point) * 0.33 + np.random.randint(-350, 350, 2)
                    control_point_2 = start_point + (end_point - start_point) * 0.67 + np.random.randint(-150, 150, 2)      
            case "big2":
                    scratch_dim = np.array([width / 7, width / 7]) 
                    scratch_position = np.random.randint((0, 0), (width, height) - scratch_dim)
                    start_point, end_point = calc_endpoints(scratch_dim, width, height)
                    control_point_1 = start_point + (end_point - start_point) * 0.20 + np.random.randint(-350, 350, 2)
                    control_point_2 = start_point + (end_point - start_point) * 0.67 + np.random.randint(-150, 150, 2)                     
        
        ctx.set_line_width(brush_size)
        ctx.move_to(start_point[0], start_point[1])
        ctx.curve_to(
            control_point_1[0],
            control_point_1[1],
            control_point_2[0],
            control_point_2[1],
            end_point[0],
            end_point[1],
        )
        ctx.stroke()        

    img = to_pil(surface).convert("L")
    img = img.filter(ImageFilter.GaussianBlur(radius=brush_size))
    img = img.resize([4096, 4096], Image.Resampling.LANCZOS)

    img_arr = np.array(img).astype("float")
    arr_max = img_arr.max()
    img_arr = img_arr * 255.0 / arr_max

    img = Image.fromarray(img_arr.astype("uint8"))
    img.save(mask_path)

    image = bpy.data.images.load(mask_path, check_existing=True)
    image.colorspace_settings.name = "Non-Color"

    return image

def calc_endpoints(scratch_dim, width, height):
    #TODO: remove
    """
    if np.random.random() < 0.99:  
        angle = np.radians(50) 
    else: 
        angle = np.random.uniform(0, 2 * np.pi) 
    """
    angle = np.random.uniform(0, 2 * np.pi) 
    rotation_matrix = np.array([
        [np.cos(angle), -np.sin(angle)],
        [np.sin(angle), np.cos(angle)]
    ])

    direction_vector = rotation_matrix @ scratch_dim

    # calculate valid bounds for start point 
    min_x = max(0, -direction_vector[0])
    max_x = min(width, width - direction_vector[0])
    min_y = max(0, -direction_vector[1])
    max_y = min(height, height - direction_vector[1])

    start_point = np.array([
        np.random.uniform(min_x, max_x),
        np.random.uniform(min_y, max_y)
    ])
    end_point = start_point + direction_vector

    return start_point, end_point


def randomize_material(random_texture):
    mat = bpy.data.materials["red_scratched_aluminium"]
    scratch_image = randomize_scratch_image()
    nodes = mat.node_tree.nodes
    shader_node_scratches_image = nodes["scratch_image"]
    shader_node_scratches_image.image = scratch_image

    shader_node_multiply_scratches_strength = nodes["scratch_strength"]
    shader_node_multiply_scratches_strength.inputs[1].default_value = 0.95 #0.09 #0.02 #0.10 #0.05 #0.15 
    shader_node_mapping_scratches = nodes["scratch_mapping"]
    scratch_scaling = 1

    shader_node_mapping_scratches.inputs["Scale"].default_value = (
        scratch_scaling,
        scratch_scaling,
        scratch_scaling,
    )

    colour_node = nodes["surface_rgb"]
    roughness_paint = nodes["roughness_paint"]
    roughness_scratch = nodes["roughness_scratch"]
    scratch_saturation = nodes["scratch_saturation"]

    roughness_scratch.inputs[1].default_value, scratch_saturation.inputs[1].default_value, shader_node_multiply_scratches_strength.inputs[1].default_value  = randomize_scratch()


    red_shades = [
        #E80610
        (0.806948, 0.001821, 0.005182, 1.000000),
        #CC1E00 - red orange
        (0.603824, 0.012983, 0.000000, 1.000000),
        #690011 - wine red
        (0.141263, 0.000000, 0.005605, 1.000000),
        #660F00 
        (0.132868, 0.004777, 0.000000, 1.000000),
        #5C0201 - dark red
        (0.107023, 0.000607, 0.000304, 1.000000),
        #choose random
        (random.uniform(0.050875, 1), 0.000607, 0.000304, 1.000000)
    ]

    red_shades_default = [
        #760201
        (0.181163, 0.000607, 0.000304, 1.000000),
        #820301
        (0.223227, 0.000911, 0.000304, 1.000000),
        #9C0401
        (0.395455, 0.001313, 0.000328, 1.000000),
        (0.270496, 0.001518, 0.0, 1)
    ]
    
    def apply_red_default(colour, roughness):
        colour.outputs[0].default_value = random.choice(red_shades_default)
        #metallic.inputs[1].default_value = 0.123
        #roughness.inputs[0].default_value = 0.004545

    def apply_red_random(colour, roughness):
        red = random.choice(red_shades)
        colour.outputs[0].default_value = red
        #metallic.inputs[1].default_value = 0.123
        #roughness.inputs[0].default_value = #0.004545 

    def apply_black(colour, metallic, roughness):
        colour.outputs[0].default_value = (0, 0, 0, 1)
        #metallic.inputs[1].default_value = 0
        roughness.inputs[0].default_value = 0

    def apply_silver(colour, metallic, roughness):
        colour.outputs[0].default_value = (0.4, 0.4, 0.4, 1)
        #metallic.inputs[1].default_value = 0.5
        roughness.inputs[0].default_value = 0

    def apply_random(colour, metallic, roughness):
        colour.outputs[0].default_value = list(np.random.rand(3)) + [1]
        #metallic.inputs[1].default_value = 0
        roughness.inputs[0].default_value = 0

    switch = {
        "red": apply_red_random,
        "black": apply_black,
        "silver": apply_silver,
    }

    if random_texture:
        apply_random(colour_node, roughness_paint)
    else:
        if random.random() <= 0.4:
            apply_red_random(colour_node, roughness_paint)
        else:
            apply_red_default(colour_node, roughness_paint)

strength = random.uniform(0.95, 1)
scratch_configs = {
    "exp5": (0.15, 0.01, strength),
    "exp6": (0.15, 0.02, strength),
    "exp3": (0.1, 0.005, strength),
}

def randomize_scratch():
    if random.random() <= 0.5:
        config = random.choice(list(scratch_configs.keys()))
        roughness_scratch, scratch_saturation, strength = scratch_configs[config]
    else:
        roughness_scratch, scratch_saturation, strength = random.uniform(0, 0.3), random.uniform(0.005, 0.07), random.uniform(0.1, 1)
    return roughness_scratch, scratch_saturation, strength