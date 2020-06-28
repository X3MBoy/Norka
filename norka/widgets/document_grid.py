# document_grid.py
#
# MIT License
#
# Copyright (c) 2020 Andrey Maksimov <meamka@ya.ru>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import os
from urllib.parse import urlparse, unquote_plus

import cairo
from gi.repository import Gtk, GObject, Gdk
from gi.repository.GdkPixbuf import Pixbuf, Colorspace

from norka.services.storage import storage
from norka.widgets.document_context_menu import DocumentContextMenu

TARGET_ENTRY_TEXT = 1


class DocumentGrid(Gtk.Grid):
    __gtype_name__ = 'DocumentGrid'

    __gsignals__ = {
        'document-create': (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        'document-import': (GObject.SIGNAL_RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__()

        self.model = Gtk.ListStore(Pixbuf, str, str, int)

        self.selected_path = None
        self.selected_document = None

        self.view = Gtk.IconView()
        self.view.set_model(self.model)
        self.view.set_pixbuf_column(0)
        self.view.set_text_column(1)
        self.view.set_item_width(80)
        self.view.set_activate_on_single_click(True)
        self.view.set_selection_mode(Gtk.SelectionMode.BROWSE)

        self.view.connect('show', self.reload_items)
        self.view.connect('button-press-event', self.on_button_pressed)

        # Enable drag-drop
        enforce_target = Gtk.TargetEntry.new('text/plain', Gtk.TargetFlags.OTHER_APP, TARGET_ENTRY_TEXT)
        self.view.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP | Gtk.DestDefaults.HIGHLIGHT,
                                [enforce_target], Gdk.DragAction.COPY)
        self.view.connect('drag-data-received', self.on_drag_data_received)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add(self.view)

        self.add(scrolled)

    def reload_items(self, sender: Gtk.Widget = None):
        self.model.clear()
        for document in storage.all():
            # icon = Gtk.IconTheme.get_default().load_icon('text-x-generic', 64, 0)
            icon = self.gen_preview(document.content[:200], size=8)
            self.model.append([icon, document.title, document.content, document._id])

        if self.selected_path:
            self.view.select_path(self.selected_path)

    def gen_preview(self, text, size=12) -> Pixbuf:
        pix = Pixbuf.new(Colorspace.RGB, True, 8, 60, 80)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pix.get_width(), pix.get_height())
        context = cairo.Context(surface)

        # Gdk.cairo_set_source_pixbuf(context, pix, 0, 0)
        # context.paint()  # paint the pixbuf
        # context.select_font_face('sans-serif')
        context.set_font_size(size)

        # grad = cairo.LinearGradient(0, 0, 0, pix.get_height())
        # grad.add_color_stop_rgb(0, 0.95, 0.95, 0.95)
        # grad.add_color_stop_rgb(pix.get_height(), 0.86, 0.86, 0.86)
        # context.set_source(grad)
        context.set_source_rgba(1, 1, 1, 1)
        context.fill()

        # add the text
        for num, line in enumerate(text.split('\n'), 1):
            context.set_source_rgba(0, 0, 0, 1)

            if line.startswith('\r'):
                line = line[1:]

            if num == 1:
                context.select_font_face('monospace', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            else:
                context.select_font_face('monospace',  cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            print(4 + size * num, line)
            context.move_to(4, size / 4 + size * num)
            context.show_text(line)

        context.rectangle(0, 0, pix.get_width(), pix.get_height())
        context.set_source_rgb(0.9, 0.9, 0.9)
        context.stroke()

        # get the resulting pixbuf
        surface = context.get_target()
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())

    def on_button_pressed(self, widget: Gtk.Widget, event: Gdk.EventButton):
        self.selected_path = self.view.get_path_at_pos(event.x, event.y)

        if not self.selected_path:
            self.selected_document = None
            return self.view.unselect_all()

        if event.button == Gdk.BUTTON_SECONDARY:
            self.view.select_path(self.selected_path)

            self.selected_document = storage.get(self.model.get_value(
                self.model.get_iter(self.selected_path), 3
            ))

            menu = DocumentContextMenu(self.view)
            menu.popup(None, None, None, None, event.button, event.time)

            return

        self.view.unselect_all()
        self.selected_document = None

    def on_drag_data_received(self, widget: Gtk.Widget, drag_context: Gdk.DragContext, x: int, y: int,
                              data: Gtk.SelectionData, info: int, time: int) -> None:
        if info == TARGET_ENTRY_TEXT:
            uris = data.get_text().split('\n')

            for uri in uris:
                # Skip empty items
                if not uri:
                    continue

                p = urlparse(unquote_plus(uri))
                filename = os.path.abspath(os.path.join(p.netloc, p.path))

                self.emit('document-import', filename)
