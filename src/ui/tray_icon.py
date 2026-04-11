from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import threading

class TrayIcon:
    def __init__(self, on_show, on_exit):
        self.on_show = on_show
        self.on_exit = on_exit
        self.icon = None

    def create_image(self):
        # Generate a simple purple square icon with a "C"
        width, height = 64, 64
        image = Image.new("RGB", (width, height), (123, 44, 191))
        dc = ImageDraw.Draw(image)
        dc.text((20, 10), "C", fill=(255, 255, 255), font_size=40)
        return image

    def run(self):
        menu = Menu(
            MenuItem("Show Search", self.on_show),
            MenuItem("Settings", lambda: print("Settings not implemented")),
            MenuItem("Exit", self.on_exit)
        )
        self.icon = Icon("Clipalyst", self.create_image(), "Clipalyst", menu)
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()
