from PIL import Image, ImageDraw, ImageFont

# --- settings ---
grid_size = 50
line_color = (255, 0, 0, 120)
line_width = 1
text_color = (255, 0, 0, 200)
font_size = 20
# -----------------

img = Image.open("research/input.png").convert("RGBA")
w, h = img.size

overlay = Image.new("RGBA", img.size, (0,0,0,0))
draw = ImageDraw.Draw(overlay)

# load font
try:
    font = ImageFont.truetype("arial.ttf", font_size)
except:
    font = ImageFont.load_default()

# draw grid lines
for x in range(0, w, grid_size):
    draw.line((x, 0, x, h), fill=line_color, width=line_width)

for y in range(0, h, grid_size):
    draw.line((0, y, w, y), fill=line_color, width=line_width)

# draw numbers
cell_index = 0
for y in range(0, h, grid_size):
    for x in range(0, w, grid_size):

        center_x = x + grid_size // 2
        center_y = y + grid_size // 2

        text = str(cell_index)

        # get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # draw centered text
        draw.text(
            (center_x - tw/2, center_y - th/2),
            text,
            fill=text_color,
            font=font,
        )

        cell_index += 1

# combine and save
result = Image.alpha_composite(img, overlay)
result.save("output_with_grid_numbers.png")
