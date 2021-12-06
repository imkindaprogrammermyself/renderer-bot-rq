import os
from functools import wraps
from importlib.resources import open_binary

from PIL import Image, ImageDraw, ImageColor, ImageFont


def delete_temp_files(*files):
    try:
        for file in files:
            if os.path.exists(file):
                os.remove(file)
    except Exception:
        pass


def catch_exception(f):
    """
    This wraps the generators for exception catching so render will still continue if there's an error while rendering.
    :param f: generator
    :return: generator
    """

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            generator = f(self, *args, **kwargs)
            for res in generator:
                yield res
        except Exception:
            yield None

    return wrapper


def catch_exception_non_generator(f):
    """
    This wraps the generators for exception catching so render will still continue if there's an error while rendering.
    :param f: generator
    :return: generator
    """

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except Exception:
            return None

    return wrapper


def memoize(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        to_hash = []

        for arg in args:
            if isinstance(arg, list):
                to_hash.extend(i for i in arg)
            else:
                to_hash.append(arg)

        obj_hash = hash(tuple(to_hash) + (f.__name__,))

        if obj_hash not in self._cache:
            result = f(self, *args, **kwargs), self._iterations
            self._cache[obj_hash] = result
        else:
            result = self._cache[obj_hash]
        return result[0]

    return wrapper


def memoize_image_gen(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        to_hash = []

        for arg in args:
            if isinstance(arg, list):
                to_hash.extend(i for i in arg)
            elif isinstance(arg, Image.Image):
                continue
            elif isinstance(arg, tuple) and any(isinstance(i, Image.Image) for i in arg):
                continue
            else:
                to_hash.append(arg)

        obj_hash = hash(tuple(to_hash) + (f.__name__,))

        if obj_hash not in self._cache:
            result = f(self, *args, **kwargs), self._iterations
            self._cache[obj_hash] = result
        else:
            result = self._cache[obj_hash]
        return result[0]

    return wrapper


def load_image(obj: object, resource: tuple[str, str], return_copy=False):
    index_name = f"image_{hash(resource)}"

    if im := getattr(obj, index_name, None):
        image = im
    else:
        image: Image.Image = Image.open(open_binary(*resource))
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        setattr(obj, index_name, image)
    if return_copy:
        return image.copy()
    else:
        return image


def draw_grid(size=(760, 760)):
    """
    Draws the grid on the minimap.
    :param size:
    :return:
    """
    image: Image.Image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    for x in range(0, 760, round(760 / 10)):
        # if x == 0:
        #     continue
        draw.line([(x, 0), (x, image.height)], fill="#ffffff40")
        draw.line([(0, x), (image.width, x)], fill="#ffffff40")
    draw.rectangle([(0, 0), (image.width - 1, image.height - 1)], outline="#ffffff40", width=1)
    return image


def draw_circle(size: tuple, fill, outline=None, width=1, aliasing_strength=4):
    """
    Generates circle, yep.
    :param size:
    :param fill:
    :param outline:
    :param width:
    :param aliasing_strength:
    :return:
    """
    base = Image.new("RGBA", size)
    als = 100 * aliasing_strength
    circle = Image.new("RGBA", (base.width + als, base.height + als), color=None)
    circle_draw = ImageDraw.Draw(circle)
    circle_draw.ellipse([(0, 0), circle.size], fill=fill, outline=outline,
                        width=round(width * ((base.width + als) / base.width)) if width else width)
    circle = circle.resize(base.size, resample=Image.LANCZOS)
    base.paste(circle, mask=circle)
    return base


@memoize_image_gen
def generate_torus(obj: object, from_color, to_color, outer_radius: int = 0, inner_radius: int = 0,
                   progress: float = 0.0):
    """
    Bakes doughnuts.
    :param obj:
    :param from_color:
    :param to_color:
    :param outer_radius:
    :param inner_radius:
    :param progress:
    :return:
    """
    if progress > 0:
        bg_circle = draw_circle((outer_radius * 2,) * 2, fill="#00000000", aliasing_strength=1)
    else:
        bg_circle = draw_circle((outer_radius * 2,) * 2, fill=from_color, aliasing_strength=1)

    bg_circle_outline = draw_circle((outer_radius * 2,) * 2, outline=from_color, fill="#00000000", width=4,
                                    aliasing_strength=1)
    bg_circle_draw = ImageDraw.Draw(bg_circle)

    if progress > 0:
        bg_circle_draw.pieslice([(0, 0), (bg_circle.width, bg_circle.height)], start=(-90 + 360 * progress),
                                end=-90, fill=f"{from_color}80")
        bg_circle_draw.pieslice([(0, 0), (bg_circle.width, bg_circle.height)], start=-90,
                                end=(-90 + 360 * progress), fill=f"{to_color}80")

    if inner_radius > 0:
        hole_mask = draw_circle((inner_radius * 2,) * 2, fill="black", aliasing_strength=1)
        hole = draw_circle((inner_radius * 2,) * 2, fill="#00000000", aliasing_strength=1)
        bg_circle.paste(hole,
                        (
                            round(bg_circle.width / 2 - hole.width / 2),
                            round(bg_circle.height / 2 - hole.height / 2)),
                        hole_mask)

    bg_circle.paste(bg_circle_outline, mask=bg_circle_outline)
    return bg_circle


def get_map_size(tree):
    """
    Some map stuff.
    :param tree:
    :return:
    """
    space_bounds, = tree.xpath('/space.settings/bounds')
    if space_bounds.attrib:
        min_x = int(space_bounds.get('minX'))
        min_y = int(space_bounds.get('minY'))
        max_x = int(space_bounds.get('maxX'))
        max_y = int(space_bounds.get('maxY'))
    else:
        min_x = int(space_bounds.xpath('minX/text()')[0])
        min_y = int(space_bounds.xpath('minY/text()')[0])
        max_x = int(space_bounds.xpath('maxX/text()')[0])
        max_y = int(space_bounds.xpath('maxY/text()')[0])

    chunk_size_elements = tree.xpath('/space.settings/chunkSize')
    if chunk_size_elements:
        chunk_size = float(chunk_size_elements[0].text)
    else:
        chunk_size = 100.0

    w = len(range(min_x, max_x + 1)) * chunk_size - 4 * chunk_size
    h = len(range(min_y, max_y + 1)) * chunk_size - 4 * chunk_size
    return w, h


def replace_color(img: Image.Image, from_color: str, to_color: str):
    """
    Replaces the color from the image. The image should not be anti-aliased.
    :param img:
    :param from_color:
    :param to_color:
    :return:
    """
    from_color = ImageColor.getrgb(from_color)
    to_color = ImageColor.getrgb(to_color)

    data = img.__array__()
    red, green, blue = data[:, :, 0], data[:, :, 1], data[:, :, 2]
    mask = (red == from_color[0]) & (blue == from_color[1]) & (green == from_color[2])
    data[:, :, :3][mask] = to_color
    return Image.fromarray(data)


def paste_centered(bg: Image.Image, fg: Image.Image, masked=False):
    """
    Pastes the fg image to bg centered.
    :param bg:
    :param fg:
    :param masked:
    :return:
    """
    x = round(bg.width / 2 - fg.width / 2)
    y = round(bg.height / 2 - fg.height / 2)
    bg.paste(fg, (x, y), mask=fg if masked else None)
    return bg


def paste_args_centered(image: Image.Image, x, y, masked=False) -> tuple:
    """
    Returns a tuple for unpacking for Image.paste method.
    :param image:
    :param x:
    :param y:
    :param masked:
    :return:
    """
    o = 20  # offset for the legends
    if masked:
        return image, ((x - round(image.width / 2)) + o, (y - round(image.height / 2)) + o), image
    else:
        return image, ((x - round(image.width / 2)) + o, (y - round(image.height / 2)) + o)


def paste_args(image: Image.Image, x, y, masked=False) -> tuple:
    if masked:
        return image, (x, y), image
    else:
        return image, (x, y)


def generate_holder(text: str, font: ImageFont.FreeTypeFont, text_offset=16, holder_size=(100, 80),
                    font_color="#ffffff"):
    hw, hh = holder_size
    holder: Image.Image = Image.new("RGBA", (hw, hh))
    holder_draw: ImageDraw.ImageDraw = ImageDraw.Draw(holder)
    text_w, text_h = holder_draw.textsize(text=text, font=font)
    text_x = round((hw / 2) - (text_w / 2))
    text_y = round((hh - text_h) - text_offset)
    holder_draw.text(xy=(text_x, text_y), text=text, fill=font_color, font=font)
    return holder


def check_trim(text_str: str, font, max_w=136):
    w, h = font.getsize(text_str)

    if w >= max_w:
        for i in range(1, len(text_str)):
            __w, __h = font.getsize(text_str[:-i])
            if __w <= max_w:
                return text_str[:-i], __w, __h
    else:
        return text_str, w, h
