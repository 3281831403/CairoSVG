"""
Clipping path test suite.

Pixels are read back from the ``ImageSurface`` to check that clipping
follows the SVG specification.

"""

from . import parser, surface

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def render_pixels(bytestring, points):
    """Render ``bytestring`` and return ``(x, y): (r, g, b, a)`` pixels."""
    tree = parser.Tree(bytestring=bytestring)
    png_surface = surface.PNGSurface(tree, None, dpi=96)
    image_surface = png_surface.cairo
    data = image_surface.get_data()
    stride = image_surface.get_stride()
    pixels = {}
    for x, y in points:
        offset = y * stride + x * 4
        blue, green, red, alpha = data[offset:offset + 4]
        pixels[(x, y)] = (red, green, blue, alpha)
    return pixels


def svg_with_clip(clip_path, element, extra_defs=''):
    """Build an SVG document with a clip path applied to an element."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        f'<defs>{clip_path}{extra_defs}</defs>{element}</svg>').encode()


def test_clip_path_object_bounding_box_shapes():
    """objectBoundingBox units use the bounding box of any shape."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    shapes = (
        # Bounding box is (10, 10, 80, 80): clip keeps x in [10, 50)
        '<circle cx="50" cy="50" r="40" fill="red" clip-path="url(#c)"/>',
        '<ellipse cx="50" cy="50" rx="40" ry="30" fill="red" '
        'clip-path="url(#c)"/>',
        '<path d="M10 10 L90 10 L90 90 L10 90 Z" fill="red" '
        'clip-path="url(#c)"/>',
        '<polygon points="10,10 90,10 90,90 10,90" fill="red" '
        'clip-path="url(#c)"/>',
    )
    for shape in shapes:
        pixels = render_pixels(
            svg_with_clip(clip, shape), [(20, 50), (70, 50)])
        assert pixels[(20, 50)] == RED
        assert pixels[(70, 50)] == TRANSPARENT


def test_clip_path_object_bounding_box_rect():
    """objectBoundingBox units keep working on rect elements."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x=".25" y=".5" width=".6" height="1"/></clipPath>')
    rect = ('<rect x="10" y="10" width="430" height="80" fill="red" '
            'clip-path="url(#c)"/>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
        f'{clip}{rect}</svg>').encode()
    # Clip region is (10 + .25 * 430, 10 + .5 * 80, .6 * 430, 80)
    #              = (117.5, 50, 258, 80)
    pixels = render_pixels(svg, [(120, 60), (100, 60), (120, 40)])
    assert pixels[(120, 60)] == RED
    assert pixels[(100, 60)] == TRANSPARENT
    assert pixels[(120, 40)] == TRANSPARENT


def test_clip_path_object_bounding_box_text():
    """objectBoundingBox units use the ink bounding box of text."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    text = ('<text x="10" y="40" font-size="30" fill="red" '
            'clip-path="url(#c)">Hello</text>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
        f'{clip}{text}</svg>').encode()
    points = [(x, y) for x in range(200) for y in range(60)]
    pixels = render_pixels(svg, points)
    red_x = [x for (x, y), pixel in pixels.items() if pixel[3] > 0]
    # The left half of the text ink is drawn…
    assert red_x
    # …but nothing past half of the text's ink bounding box
    assert max(red_x) < 60


def test_clip_path_object_bounding_box_use():
    """objectBoundingBox units of a use include its x/y offset."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    extra_defs = '<circle id="s" cx="0" cy="0" r="30"/>'
    use = '<use href="#s" x="50" y="50" fill="red" clip-path="url(#c)"/>'
    # Bounding box is (50 - 30, 50 - 30, 60, 60): clip keeps x in [20, 50)
    pixels = render_pixels(
        svg_with_clip(clip, use, extra_defs), [(30, 50), (70, 50), (10, 50)])
    assert pixels[(30, 50)] == RED
    assert pixels[(70, 50)] == TRANSPARENT
    assert pixels[(10, 50)] == TRANSPARENT


def test_clip_path_object_bounding_box_group():
    """objectBoundingBox units use the bounding box of a group."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    group = ('<g clip-path="url(#c)" fill="red">'
             '<rect x="10" y="10" width="30" height="80"/>'
             '<rect x="60" y="10" width="30" height="80"/>'
             '</g>')
    # Bounding box is (10, 10, 80, 80): clip keeps x in [10, 50)
    pixels = render_pixels(svg_with_clip(clip, group), [(20, 50), (70, 50)])
    assert pixels[(20, 50)] == RED
    assert pixels[(70, 50)] == TRANSPARENT


def test_clip_path_object_bounding_box_degenerate():
    """A degenerate bounding box clips everything instead of crashing."""
    clip = ('<clipPath id="c" clipPathUnits="objectBoundingBox">'
            '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    # A horizontal line has an empty bounding box (height is 0)
    line = ('<line x1="10" y1="50" x2="90" y2="50" stroke="red" '
            'stroke-width="10" clip-path="url(#c)"/>')
    pixels = render_pixels(svg_with_clip(clip, line), [(50, 50), (10, 50)])
    assert pixels[(50, 50)] == TRANSPARENT
    assert pixels[(10, 50)] == TRANSPARENT


def test_clip_path_user_space_on_use():
    """userSpaceOnUse units use the current user coordinate system."""
    clip = ('<clipPath id="c" clipPathUnits="userSpaceOnUse">'
            '<rect x="0" y="0" width="50" height="100"/></clipPath>')
    rect = ('<rect x="0" y="0" width="100" height="100" fill="red" '
            'clip-path="url(#c)"/>')
    pixels = render_pixels(svg_with_clip(clip, rect), [(25, 50), (75, 50)])
    assert pixels[(25, 50)] == RED
    assert pixels[(75, 50)] == TRANSPARENT


def test_clip_path_clip_rule_evenodd():
    """clip-rule="evenodd" cuts holes in the clipping path."""
    ring = '<path d="M10 10 h80 v80 h-80 Z M30 30 h40 v40 h-40 Z" %s/>'
    rect = ('<rect x="0" y="0" width="100" height="100" fill="red" '
            'clip-path="url(#c)"/>')
    clips = (
        # clip-rule as a presentation attribute
        '<clipPath id="c">%s</clipPath>' % ring % 'clip-rule="evenodd"',
        # clip-rule inherited from the clipPath element
        '<clipPath id="c" clip-rule="evenodd">%s</clipPath>' % ring % '',
        # clip-rule in a style attribute
        '<clipPath id="c">%s</clipPath>' % ring % 'style="clip-rule:evenodd"',
    )
    for clip in clips:
        pixels = render_pixels(
            svg_with_clip(clip, rect), [(20, 20), (50, 50)])
        assert pixels[(20, 20)] == RED
        assert pixels[(50, 50)] == TRANSPARENT


def test_clip_path_nested_clip_path():
    """A clip-path on clipPath content intersects the clipping paths."""
    inner = ('<clipPath id="inner">'
             '<rect x="0" y="0" width="50" height="100"/></clipPath>')
    outer = ('<clipPath id="outer">'
             '<rect x="0" y="0" width="100" height="100" '
             'clip-path="url(#inner)"/>'
             '<circle cx="80" cy="80" r="15"/>'
             '</clipPath>')
    rect = ('<rect x="0" y="0" width="100" height="100" fill="red" '
            'clip-path="url(#outer)"/>')
    svg = svg_with_clip(outer, rect, extra_defs=inner)
    points = [(x, y) for x in range(100) for y in range(100)]
    pixels = render_pixels(svg, points)
    # The rect child is intersected with the inner clipping path…
    assert pixels[(25, 50)] == RED
    assert pixels[(75, 20)] == TRANSPARENT
    # …and the circle child is unioned with it
    assert pixels[(80, 80)] == RED
    # The clipping path content is never painted: no black pixel anywhere
    assert not any(
        pixel[:3] == (0, 0, 0) and pixel[3] for pixel in pixels.values())


def test_clip_path_nested_clip_path_object_bounding_box():
    """Nested clip paths work with objectBoundingBox units."""
    inner = ('<clipPath id="inner">'
             '<rect x="0" y="0" width="0.5" height="1"/></clipPath>')
    outer = ('<clipPath id="outer" clipPathUnits="objectBoundingBox">'
             '<rect x="0" y="0" width="1" height="1" '
             'clip-path="url(#inner)"/>'
             '</clipPath>')
    rect = ('<rect x="0" y="0" width="100" height="100" fill="red" '
            'clip-path="url(#outer)"/>')
    svg = svg_with_clip(outer, rect, extra_defs=inner)
    pixels = render_pixels(svg, [(25, 50), (75, 50)])
    assert pixels[(25, 50)] == RED
    assert pixels[(75, 50)] == TRANSPARENT


def test_clip_path_content_not_painted():
    """The content of a clipPath is never painted."""
    clip = ('<clipPath id="c">'
            '<rect x="0" y="0" width="100" height="100"/></clipPath>')
    rect = ('<rect x="10" y="10" width="20" height="20" fill="blue" '
            'clip-path="url(#c)"/>')
    pixels = render_pixels(svg_with_clip(clip, rect), [(15, 15), (50, 50)])
    assert pixels[(15, 15)] == BLUE
    assert pixels[(50, 50)] == TRANSPARENT
