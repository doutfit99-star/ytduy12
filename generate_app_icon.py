# -*- coding: utf-8 -*-
"""
Generate Cyberpunk HD Application Icon for DUY DOW v4.0 PRO
"""

import math
from PIL import Image, ImageDraw, ImageFilter

def create_cyberpunk_icon(size=512):
    # Base dark canvas with high quality antialiasing
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(size * 0.05)
    rect = [margin, margin, size - margin, size - margin]
    radius = int(size * 0.22)

    # 1. Background Rounded Card with Dark Gradient Fill
    bg_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_img)
    
    bg_draw.rounded_rectangle(rect, radius=radius, fill=(11, 13, 25, 255))

    # Add gradient glow overlay
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    
    # Outer neon ring border glow
    glow_draw.rounded_rectangle(
        [margin - 4, margin - 4, size - margin + 4, size - margin + 4],
        radius=radius + 4,
        outline=(99, 102, 241, 200),
        width=int(size * 0.035)
    )
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=int(size * 0.02)))
    
    img = Image.alpha_composite(img, glow_img)
    img = Image.alpha_composite(img, bg_img)

    # Re-bind draw handle
    draw = ImageDraw.Draw(img)

    # Border gradient stroke
    draw.rounded_rectangle(
        rect,
        radius=radius,
        outline=(6, 182, 212, 255),
        width=int(size * 0.025)
    )

    # 2. Draw Stylized Cyberpunk Downloader Symbol (Cloud + Down Arrow)
    center_x = size / 2
    center_y = size / 2

    # Draw Cloud Arcs
    cloud_color = (99, 102, 241, 255)  # Vibrant Indigo
    glow_cloud = (6, 182, 212, 255)    # Neon Cyan

    # Main Down Arrow
    arrow_width = int(size * 0.14)
    arrow_top = int(size * 0.32)
    arrow_bottom = int(size * 0.58)
    head_size = int(size * 0.16)

    # Arrow Shaft
    shaft_rect = [
        center_x - arrow_width / 2,
        arrow_top,
        center_x + arrow_width / 2,
        arrow_bottom
    ]
    draw.rounded_rectangle(shaft_rect, radius=int(arrow_width / 4), fill=(59, 130, 246, 255))

    # Arrow Head Triangle
    head_points = [
        (center_x - head_size * 1.3, arrow_bottom - int(size * 0.02)),
        (center_x + head_size * 1.3, arrow_bottom - int(size * 0.02)),
        (center_x, arrow_bottom + head_size * 1.2)
    ]
    draw.polygon(head_points, fill=(6, 182, 212, 255))

    # Base tray / dish line (Under arrow)
    tray_y = int(size * 0.74)
    tray_h = int(size * 0.045)
    tray_w = int(size * 0.52)
    tray_rect = [
        center_x - tray_w / 2,
        tray_y,
        center_x + tray_w / 2,
        tray_y + tray_h
    ]
    draw.rounded_rectangle(tray_rect, radius=int(tray_h / 2), fill=(139, 92, 246, 255))

    # Save PNG and multi-resolution ICO
    img.save("static/icon.png", format="PNG")
    
    # Generate multi-size icon
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save("app_icon.ico", format="ICO", sizes=icon_sizes)
    img.save("static/favicon.ico", format="ICO", sizes=icon_sizes)

    print("Icon generated successfully: app_icon.ico, static/favicon.ico, static/icon.png")

if __name__ == "__main__":
    create_cyberpunk_icon(512)
