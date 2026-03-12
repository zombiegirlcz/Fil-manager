#!/usr/bin/env python3
import os
import shutil
import asyncio
import shlex
import json
import zipfile
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.application import run_in_terminal, get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.widgets import Dialog, Label, Button, TextArea, RadioList

class RenegadeFM_Ultimate:
    SCRIPT_COMMAND_MAP = {
        '.py': 'python3',
        '.sh': 'bash',
        '.js': 'node',
        '.rb': 'ruby',
        '.pl': 'perl',
        '.php': 'php',
        '.jar': 'java -jar',
    }
    LAST_PATH_FILE = os.path.expanduser("~/.renegadefm_last_path")
    SETTINGS_FILE = os.path.expanduser("~/.renegadefm_settings.json")
    
    COLOR_PRESETS = {
        "magenta": "#ff00ff",
        "cyan": "#00ffff",
        "green": "#00ff00",
        "yellow": "#ffff00",
        "red": "#ff0000",
        "blue": "#0000ff",
        "white": "#ffffff",
        "gray": "#888888",
    }
    
    DEFAULT_SETTINGS = {
        "large_preview": False,
        "preview_columns": 3,
        "show_log": True,
        "extension_colors": {
            ".py": "magenta",
            ".sh": "magenta", 
            ".txt": "white",
            ".md": "green",
            "directory": "green",
            "executable": "magenta",
            "default": "white",
        },
        "script_command_mode": "tmux",
        "confirm_delete": True,
    }

    def __init__(self):
        self.path = self._load_last_path() or os.getcwd()
        self.settings = self._load_settings()
        self.all_files = []
        self.files = []
        self.selected_index = 0
        self.search_query = ""
        self.ignore_search_buffer_change = False
        self.delete_marks = set()
        self.zip_marks = set()
        self.clipboard = []
        self.clipboard_action = 'copy'
        
        self.message = "RenegadeFM - [Tab]Hledat [F2]Nastaveni [Ctrl+R]Mark [Ctrl+Q]Exit"
        self.show_help = False
        self.active_dialog = None
        self.refresh_files()
        
        # Vyhledávací řádek
        self.search_input = TextArea(
            height=1,
            prompt='Hledat > ',
            style='class:input',
            multiline=False,
            wrap_lines=False,
            accept_handler=self.handle_search_enter
        )
        self.search_buffer = self.search_input.buffer
        self.search_buffer.on_text_changed += self._on_search_change

        # Log
        self.terminal_buffer = Buffer()
        self.terminal_window = Window(
            content=BufferControl(buffer=self.terminal_buffer),
            wrap_lines=True,
            style="class:terminal",
            height=Dimension(min=5)
        )
        
        # Levý panel (seznam)
        self.file_list_control = FormattedTextControl(
            self.get_file_content,
            focusable=True,
            show_cursor=False
        )
        self.file_window = Window(
            content=self.file_list_control, 
            wrap_lines=False, 
            width=Dimension(weight=50)
        )
        
        # Pravý panel (náhled)
        self.preview_window = Window(
            content=FormattedTextControl(self.get_preview_content), 
            wrap_lines=True, 
            width=Dimension(weight=50)
        )

        # LAYOUT
        top_split = VSplit([
            self.file_window,
            Window(width=1, char='│', style="class:line"),
            self.preview_window,
        ])
        
        self.body_components = [
            Window(height=1, content=FormattedTextControl(self.get_header), style="class:header"),
            top_split,
            Window(height=1, char='─', style="class:line"),
        ]
        
        # Log se přidá pokud je povoleno
        if self.settings["show_log"]:
            self.body_components.extend([
                Window(height=1, content=FormattedTextControl(HTML(" <b>LOG / TERMINAL OUTPUT</b>")), style="class:header"),
                self.terminal_window,
                Window(height=1, char='─', style="class:line"),
            ])
        
        self.body_components.extend([
            self.search_input,
            Window(height=1, content=FormattedTextControl(self.get_footer), style="class:footer"),
        ])
        
        main_body = HSplit(self.body_components)

        self.root_container = FloatContainer(
            content=main_body,
            floats=[
                Float(
                    content=ConditionalContainer(
                        content=Dialog(
                            title="NAPOVEDA",
                            body=Label(self.get_help_text()),
                            buttons=[Button("ZAVRIT", handler=self.toggle_help)],
                            with_background=True
                        ),
                        filter=Condition(lambda: self.show_help)
                    )
                )
            ]
        )
        
        self.layout = Layout(self.root_container)
        
        self.kb = KeyBindings()
        self.setup_bindings()
        
        self.style = Style.from_dict({
            'header': '#00ffff bold',
            'footer': '#ffff00 bold',
            'line':   '#888888',
            'dir':    '#00ff00 bold',
            'file':   '#ffffff',
            'exec':   '#ff00ff bold',
            'selected': 'reverse',
            'copy-mark': '#ffff00 bold', 
            'move-mark': '#ff0000 bold',
            'delete-mark': '#ff6600 bold',
            'zip-mark': '#0088ff bold',
            'preview-header': '#00ffff bold underline',
            'terminal': '#aaaaaa',
            'input': '#ffffff bold',
            'dialog': 'bg:#000088',
            'dialog.body': 'bg:#ffffff #000000',
            'button.focused': 'bg:#ff0000 #ffffff',
        })
        
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=False
        )
        
        self.layout.focus(self.file_list_control)

    def _load_settings(self):
        try:
            if os.path.isfile(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    settings = self.DEFAULT_SETTINGS.copy()
                    settings.update(loaded)
                    return settings
        except:
            pass
        return self.DEFAULT_SETTINGS.copy()
    
    def _save_settings(self):
        try:
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.log_to_terminal(f"Chyba ukládání nastavení: {e}\n")

    def log_to_terminal(self, text):
        if not self.settings["show_log"]:
            return
        new_text = self.terminal_buffer.text + text
        self.terminal_buffer.set_document(Document(new_text, cursor_position=len(new_text)), bypass_readonly=True)

    async def run_script_async(self, command):
        self.log_to_terminal(f"\n[CMD]: {command}\n" + "-"*40 + "\n")
        try:
            process = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.path
            )
            while True:
                line = await process.stdout.readline()
                if not line: 
                    break
                self.log_to_terminal(line.decode('utf-8', errors='replace'))
                get_app().invalidate()

            await process.wait()
            self.log_to_terminal(f"\n[EXIT] Code: {process.returncode}\n")
            self.refresh_files()
        except Exception as e:
            self.log_to_terminal(f"\n[ERR]: {str(e)}\n")

    def refresh_files(self):
        try:
            entries = sorted(os.listdir(self.path))
            entries.insert(0, "..")
        except:
            entries = [".."]
        self.all_files = entries
        self.apply_search_filter()

    def _on_search_change(self, buffer):
        if self.ignore_search_buffer_change:
            return
        self.search_query = buffer.text
        self.apply_search_filter()

    def handle_search_enter(self, buff):
        text = buff.text.strip()
        if not text:
            self._focus_file_list()
            return True

        if text.startswith("@"):
            query = text[1:].strip()
            if query:
                self.log_to_terminal(f"[SEARCH] Hledám '{query}' rekurzivně...\n")
                get_app().create_background_task(self.recursive_search(query))
            self._reset_search_buffer()
            self._focus_file_list()
            return True

        self.search_query = text
        self.apply_search_filter(select_first=True)
        self._reset_search_buffer()
        self._focus_file_list()
        return True

    def _reset_search_buffer(self):
        self.ignore_search_buffer_change = True
        self.search_buffer.document = Document("", 0)
        self.search_query = ""
        self.ignore_search_buffer_change = False

    def _focus_file_list(self):
        try:
            self.layout.focus(self.file_list_control)
        except Exception:
            pass

    async def recursive_search(self, query):
        results = []
        normalized = query.lower()
        try:
            for root, dirs, files in os.walk(self.path):
                dirs[:] = dirs[:10]
                for f in files:
                    if normalized in f.lower():
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, self.path)
                        results.append(rel)
                        if len(results) >= 50:
                            break
                if len(results) >= 50:
                    break
        except:
            pass
        
        if results:
            self.log_to_terminal(f"Nalezeno {len(results)} souborů:\n")
            for r in results[:30]:
                self.log_to_terminal(f"  {r}\n")
        else:
            self.log_to_terminal(f"Žádné soubory nenalezeny.\n")
        self._invalidate_ui()

    def apply_search_filter(self, select_first=False):
        previous_selection = None
        if self.files and 0 <= self.selected_index < len(self.files):
            previous_selection = self.files[self.selected_index]

        query = self.search_query.strip()
        if query.startswith("$"):
            filtered = list(self.all_files)
        elif query:
            normalized = query.lower()
            filtered = [f for f in self.all_files if f == ".." or normalized in f.lower()]
        else:
            filtered = list(self.all_files)

        if not filtered:
            filtered = [".."]

        self.files = filtered
        if select_first:
            first_match = next((idx for idx, name in enumerate(self.files) if name != ".."), 0)
            self.selected_index = first_match
        else:
            if previous_selection in self.files:
                self.selected_index = self.files.index(previous_selection)
            else:
                self.selected_index = 0

        if self.selected_index >= len(self.files):
            self.selected_index = max(0, len(self.files) - 1)

        self._invalidate_ui()

    def _invalidate_ui(self):
        try:
            get_app().invalidate()
        except Exception:
            pass

    def _load_last_path(self):
        try:
            if os.path.isfile(self.LAST_PATH_FILE):
                with open(self.LAST_PATH_FILE, 'r') as f:
                    path = f.read().strip()
                    if path and os.path.isdir(path):
                        return path
        except Exception:
            pass
        return None

    def _save_last_path(self):
        try:
            dirpath = os.path.dirname(self.LAST_PATH_FILE)
            if dirpath and not os.path.isdir(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(self.LAST_PATH_FILE, 'w') as f:
                f.write(self.path)
        except Exception as e:
            self.log_to_terminal(f"[SAVE PATH ERR] {e}\n")

    def get_header(self):
        return HTML(f" <b>PATH:</b> {self.path} | <b>DEL:</b> {len(self.delete_marks)} | <b>ZIP:</b> {len(self.zip_marks)}")

    def get_file_content(self):
        lines = []
        try: 
            term_height = shutil.get_terminal_size().lines
        except: 
            term_height = 24
        max_h = (term_height // 2) - 2
        
        start_idx = max(0, self.selected_index - max_h // 2)
        end_idx = start_idx + max_h
        visible_files = self.files[start_idx:end_idx]
        
        ext_colors = self.settings.get("extension_colors", {})
        
        for i, filename in enumerate(visible_files):
            real_idx = start_idx + i
            full_path = os.path.join(self.path, filename)
            
            style_class = ""
            display = filename
            color = ""
            
            if filename == "..":
                display = "⬆ .. (Zpět)"
                style_class = "class:dir"
            elif os.path.isdir(full_path):
                display = f"📁 {filename}"
                color_name = ext_colors.get("directory", "green")
                color = self.COLOR_PRESETS.get(color_name, "#00ff00")
                style_class = f"fg:{color}"
            elif os.access(full_path, os.X_OK) or filename.endswith(('.py', '.sh','js')):
                display = f"🚀 {filename}"
                _, ext = os.path.splitext(filename)
                color_name = ext_colors.get(ext.lower(), ext_colors.get("executable", "magenta"))
                color = self.COLOR_PRESETS.get(color_name, "#ff00ff")
                style_class = f"fg:{color}"
            else:
                display = f"📄 {filename}"
                _, ext = os.path.splitext(filename)
                color_name = ext_colors.get(ext.lower(), ext_colors.get("default", "white"))
                color = self.COLOR_PRESETS.get(color_name, "#ffffff")
                style_class = f"fg:{color}"
            
            if full_path in self.clipboard:
                if self.clipboard_action == 'move':
                    style_class += " class:move-mark"
                    display += " [CUT]"
                else:
                    style_class += " class:copy-mark"
                    display += " [COPY]"
            
            if full_path in self.delete_marks:
                style_class += " class:delete-mark"
                display += " [DEL]"
            
            if full_path in self.zip_marks:
                style_class += " class:zip-mark"
                display += " [ZIP]"

            if real_idx == self.selected_index and self.layout.has_focus(self.file_list_control):
                style_class = "class:selected " + style_class
            
            lines.append((style_class, f" {display} \n"))
        return lines

    def get_preview_content(self):
        if not self.files: 
            return []
        filename = self.files[self.selected_index]
        full_path = os.path.join(self.path, filename)
        
        lines = [("class:preview-header", f" {filename} \n"), ("", "\n")]
        
        if os.path.isdir(full_path):
            try:
                items = os.listdir(full_path)
                cols = self.settings.get("preview_columns", 3)
                lines.append(("", f" Složka ({len(items)} položek):\n"))
                
                # Render v sloupcích
                for i in range(0, len(items), cols):
                    row_items = items[i:i+cols]
                    row_text = "  " + " | ".join(f"{item[:15]:15}" for item in row_items) + "\n"
                    lines.append(("", row_text))
            except: 
                pass
        elif os.path.isfile(full_path):
            try:
                sz = os.path.getsize(full_path)
                lines.append(("", f" Velikost: {sz} B\n"))
                if sz < 20000:
                    lines.append(("", "-"*20 + "\n"))
                    with open(full_path, 'r', errors='ignore') as f:
                        lines.append(("class:terminal", f.read(800)))
            except: 
                pass
        return lines

    def get_footer(self):
        mode = "COPY" if self.clipboard_action == 'copy' else "CUT/MOVE"
        clip_info = f"{len(self.clipboard)} ({mode})" if self.clipboard else "0"
        marked = f"{len(self.delete_marks)} k mazání" if self.delete_marks else "0"
        return HTML(f" <b>CLIP:</b> {clip_info} | <b>MARKED:</b> {marked} | Preview: {'ON' if self.settings['large_preview'] else 'OFF'}")

    def get_help_text(self):
        return """
 ZKRATKY
 -------
 Home        : Domovská složka
 End / Ctrl+Q: Ukončit aplikaci
 Tab         : Fokus na vyhledávání
 Enter       : Otevřít/spustit
 Šipka vlevo : Zpět (..)
 
 PgUp        : Vytvořit ALIAS
 F2          : Nastavení
 
 Ctrl+R      : Přepnout označení ke smazání
 r           : Smazat (s potvrzením)
 c           : Kopírovat
 x           : Vyjmout
 v           : Vložit
 
 n           : Nový soubor
 m           : Nová složka
 e           : Editovat (nano)
 Ctrl+e      : Přejmenovat
 
 F1 / ?      : Tato nápověda
 q           : Konec
        """

    async def _show_input_dialog(self, title, label_text, default=""):
        future = asyncio.Future()

        def accept(buf=None):
            self.root_container.floats.pop()
            future.set_result(input_field.text)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        def cancel():
            self.root_container.floats.pop()
            future.set_result(None)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        input_field = TextArea(
            text=default,
            multiline=False,
            password=False,
            accept_handler=accept,
        )

        dialog = Dialog(
            title=title,
            body=HSplit([
                Label(text=label_text),
                input_field,
            ]),
            buttons=[
                Button(text="OK", handler=lambda: accept(input_field.buffer)),
                Button(text="Zrušit", handler=cancel),
            ],
            with_background=True,
        )

        self.active_dialog = {"type": "input"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(input_field)
        get_app().invalidate()

        return await future

    async def _show_confirm_dialog(self, title, text):
        future = asyncio.Future()

        def accept():
            self.root_container.floats.pop()
            future.set_result(True)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        def cancel():
            self.root_container.floats.pop()
            future.set_result(False)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        btn_yes = Button(text="Ano", handler=accept)
        btn_no = Button(text="Ne", handler=cancel)

        dialog = Dialog(
            title=title,
            body=Label(text=text),
            buttons=[btn_yes, btn_no],
            with_background=True,
        )

        self.active_dialog = {"type": "confirm"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(btn_no)
        get_app().invalidate()

        return await future

    async def _show_radiolist_dialog(self, title, text, values):
        future = asyncio.Future()

        def accept():
            self.root_container.floats.pop()
            future.set_result(radio_list.current_value)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        def cancel():
            self.root_container.floats.pop()
            future.set_result(None)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        radio_list = RadioList(values)
        dialog = Dialog(
            title=title,
            body=HSplit([
                Label(text=text),
                radio_list,
            ]),
            buttons=[
                Button(text="OK", handler=accept),
                Button(text="Zrušit", handler=cancel),
            ],
            with_background=True,
        )

        self.active_dialog = {"type": "input"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(radio_list)
        get_app().invalidate()

        return await future

    def toggle_help(self):
        self.show_help = not self.show_help

    async def show_settings_dialog(self):
        future = asyncio.Future()

        def apply_settings():
            self.root_container.floats.pop()
            self.settings["large_preview"] = large_preview_radio.current_value == "true"
            self.settings["show_log"] = show_log_radio.current_value == "true"
            self.settings["script_command_mode"] = cmd_mode_radio.current_value
            
            self.settings["extension_colors"][".py"] = py_color_radio.current_value
            self.settings["extension_colors"][".sh"] = sh_color_radio.current_value
            self.settings["extension_colors"][".txt"] = txt_color_radio.current_value
            self.settings["extension_colors"][".md"] = md_color_radio.current_value
            self.settings["extension_colors"]["directory"] = dir_color_radio.current_value
            
            self._save_settings()
            future.set_result(True)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None
            self._invalidate_ui()

        def cancel():
            self.root_container.floats.pop()
            future.set_result(False)
            self.layout.focus(self.file_list_control)
            self.active_dialog = None

        large_preview_radio = RadioList([("true", "Velký náhled (vypne log)"), ("false", "Běžný náhled")])
        large_preview_radio.current_value = "true" if self.settings["large_preview"] else "false"

        show_log_radio = RadioList([("true", "Zobrazit log"), ("false", "Skrýt log")])
        show_log_radio.current_value = "true" if self.settings["show_log"] else "false"

        cmd_mode_radio = RadioList([("tmux", "$$ = Tmux"), ("termux_float", "$ = Termux Float")])
        cmd_mode_radio.current_value = self.settings["script_command_mode"]

        color_choices = [(k, k.upper()) for k in self.COLOR_PRESETS.keys()]

        py_color_radio = RadioList(color_choices)
        py_color_radio.current_value = self.settings["extension_colors"].get(".py", "magenta")

        sh_color_radio = RadioList(color_choices)
        sh_color_radio.current_value = self.settings["extension_colors"].get(".sh", "magenta")

        txt_color_radio = RadioList(color_choices)
        txt_color_radio.current_value = self.settings["extension_colors"].get(".txt", "white")

        md_color_radio = RadioList(color_choices)
        md_color_radio.current_value = self.settings["extension_colors"].get(".md", "green")

        dir_color_radio = RadioList(color_choices)
        dir_color_radio.current_value = self.settings["extension_colors"].get("directory", "green")

        dialog = Dialog(
            title="NASTAVENÍ",
            body=HSplit([
                Label(text="Náhled složek:"),
                large_preview_radio,
                Label(text="\nLog panel:"),
                show_log_radio,
                Label(text="\nMód příkazů ($$ a $):"),
                cmd_mode_radio,
                Label(text="\nBarvy - .py:"),
                py_color_radio,
                Label(text=".sh:"),
                sh_color_radio,
                Label(text=".txt:"),
                txt_color_radio,
                Label(text=".md:"),
                md_color_radio,
                Label(text="Složky:"),
                dir_color_radio,
            ]),
            buttons=[
                Button(text="Uložit", handler=apply_settings),
                Button(text="Zrušit", handler=cancel),
            ],
            with_background=True,
        )

        self.active_dialog = {"type": "settings"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(large_preview_radio)
        get_app().invalidate()

        return await future

    def setup_bindings(self):
        kb = self.kb

        panel_focus = Condition(lambda: self.layout.has_focus(self.file_list_control))
        allow_focus_toggle = Condition(lambda: self.active_dialog is None)

        @kb.add('f1', filter=panel_focus)
        @kb.add('?', filter=panel_focus)
        @kb.add('c-h', filter=panel_focus)
        def _(event): 
            self.toggle_help()

        @kb.add('tab', filter=allow_focus_toggle)
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self.layout.focus(self.search_input)
            else:
                self.layout.focus(self.file_list_control)
        
        @kb.add('f2', filter=panel_focus)
        def _(event):
            asyncio.create_task(self.show_settings_dialog())

        @kb.add('end')
        def _(event):
            self._save_last_path()
            event.app.exit()

        @kb.add('c-q')
        def _(event):
            self._save_last_path()
            self.log_to_terminal(f"\n[EXIT] Ukončení - poslední složka: {self.path}\n")
            event.app.exit()

        @kb.add('c-c')
        def _(event):
            self._save_last_path()
            self.log_to_terminal(f"\n[EXIT] Ctrl+C - poslední složka: {self.path}\n")
            event.app.exit()

        @kb.add('q')
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self._save_last_path()
                self.log_to_terminal(f"\n[EXIT] Konec - poslední složka: {self.path}\n")
                event.app.exit()

        in_file_list = Condition(lambda: self.layout.has_focus(self.file_list_control))

        @kb.add('up', filter=in_file_list)
        def _(event): 
            self.selected_index = max(0, self.selected_index - 1)

        @kb.add('down', filter=in_file_list)
        def _(event): 
            self.selected_index = min(len(self.files) - 1, self.selected_index + 1)

        @kb.add('pageup', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_create_alias())

        @kb.add('home', filter=in_file_list)
        def _(event):
            self.path = os.path.expanduser("~")
            self.refresh_files()

        @kb.add('left', filter=in_file_list)
        def _(event):
            self.path = os.path.dirname(self.path)
            self.refresh_files()

        @kb.add('right', filter=in_file_list)
        @kb.add('enter', filter=in_file_list)
        def _(event): 
            self.action_enter()

        @kb.add('c', filter=in_file_list)
        def _(event): 
            self.toggle_selection('copy')

        @kb.add('x', filter=in_file_list)
        def _(event): 
            self.toggle_selection('move')

        @kb.add('v', filter=in_file_list)
        def _(event): 
            self.action_paste()

        @kb.add('c-r', filter=in_file_list)
        def _(event):
            self.toggle_delete_mark()

        @kb.add('r', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_delete_marked())
            
        @kb.add('c-e', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_rename())

        @kb.add('m', filter=in_file_list)
        async def _(event):
            name = await self._show_input_dialog("Nová složka", "Zadejte název složky:")
            if name:
                try:
                    os.mkdir(os.path.join(self.path, name))
                    self.refresh_files()
                    self.log_to_terminal(f"Složka '{name}' vytvořena.\n")
                except Exception as e:
                    self.log_to_terminal(str(e)+"\n")

        @kb.add('n', filter=in_file_list)
        async def _(event):
            name = await self._show_input_dialog("Nový soubor", "Zadejte název souboru:")
            if name:
                try:
                    open(os.path.join(self.path, name), 'a').close()
                    self.refresh_files()
                    self.log_to_terminal(f"Soubor '{name}' vytvořen.\n")
                except Exception as e:
                    self.log_to_terminal(str(e)+"\n")
        
        @kb.add('e', filter=in_file_list)
        def _(event):
            f = self.files[self.selected_index]
            if f != "..":
                run_in_terminal(lambda: os.system(f"nano '{os.path.join(self.path, f)}'"))

        @kb.add('z', filter=in_file_list)
        def _(event):
            self.toggle_zip_mark()

        @kb.add('c-z', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_zip_marked())

    def toggle_delete_mark(self):
        if not self.files:
            return
        filename = self.files[self.selected_index]
        if filename == "..":
            return
        full_path = os.path.join(self.path, filename)
        if full_path in self.delete_marks:
            self.delete_marks.remove(full_path)
        else:
            self.delete_marks.add(full_path)
        self._invalidate_ui()

    def toggle_zip_mark(self):
        if not self.files:
            return
        filename = self.files[self.selected_index]
        if filename == "..":
            return
        full_path = os.path.join(self.path, filename)
        if full_path in self.zip_marks:
            self.zip_marks.remove(full_path)
        else:
            self.zip_marks.add(full_path)
        self._invalidate_ui()

    async def action_zip_marked(self):
        if not self.zip_marks:
            self.log_to_terminal("Žádné soubory k zabalení.\n")
            return
        
        count_text = f"{len(self.zip_marks)} položky" if len(self.zip_marks) > 1 else "1 položku"
        zip_name = await self._show_input_dialog(
            title="Vytvořit ZIP",
            label_text="Zadejte název souboru ZIP (bez .zip):",
            default="archive"
        )

        if not zip_name:
            self.log_to_terminal("Vytváření ZIP zrušeno.\n")
            return

        zip_path = os.path.join(self.path, f"{zip_name}.zip")
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in self.zip_marks:
                    if os.path.isfile(file_path):
                        arcname = os.path.basename(file_path)
                        zf.write(file_path, arcname=arcname)
                    elif os.path.isdir(file_path):
                        for root, dirs, files in os.walk(file_path):
                            for file in files:
                                file_full_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_full_path, self.path)
                                zf.write(file_full_path, arcname=arcname)
            
            self.zip_marks.clear()
            self.refresh_files()
            self.log_to_terminal(f"ZIP archiv '{zip_name}.zip' vytvořen ({len(self.zip_marks)} položek).\n")
        except Exception as e:
            self.log_to_terminal(f"Chyba při vytváření ZIP: {e}\n")


    async def action_delete_marked(self):
        if not self.delete_marks:
            self.log_to_terminal("Žádné soubory k smazání.\n")
            return
        
        count_text = f"{len(self.delete_marks)} položky" if len(self.delete_marks) > 1 else "1 položku"
        confirmed = await self._show_confirm_dialog(
            title="Smazat",
            text=f"Opravdu si přejete smazat {count_text}?"
        )

        if confirmed:
            deleted = 0
            for path in list(self.delete_marks):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    deleted += 1
                except Exception as e:
                    self.log_to_terminal(f"Chyba: {e}\n")
            self.delete_marks.clear()
            self.refresh_files()
            self.log_to_terminal(f"Smazáno: {deleted}\n")
        else:
            self.log_to_terminal("Mazání zrušeno.\n")

    def action_enter(self):
        if not self.files:
            return
        filename = self.files[self.selected_index]
        full_path = os.path.join(self.path, filename)
        
        self._reset_search_buffer()

        if filename == "..":
            self.path = os.path.dirname(self.path)
            self.refresh_files()
        elif os.path.isdir(full_path):
            self.path = full_path
            self.refresh_files()
        elif os.path.isfile(full_path):
            script_cmd = self._build_script_command(filename, full_path)
            if not script_cmd and os.access(full_path, os.X_OK):
                script_cmd = shlex.quote(full_path)

            if script_cmd:
                mode = self.settings.get("script_command_mode", "tmux")
                if mode == "tmux":
                    run_in_terminal(lambda: os.system(f"tmux new-window -c {shlex.quote(self.path)} {shlex.quote(script_cmd)}"))
                else:
                    run_in_terminal(lambda: os.system(f"am start -n com.termux.window/.TermuxFloatActivity -e com.termux.execute {shlex.quote(script_cmd)}"))
                self.log_to_terminal(f"[INFO] Spouštím '{filename}' v {mode}...\n")
                return
                
            run_in_terminal(lambda: os.system(f"nano '{full_path}'"))

    def _build_script_command(self, filename, full_path):
        ext = os.path.splitext(filename)[1].lower()
        cmd = self.SCRIPT_COMMAND_MAP.get(ext)
        if cmd:
            return f"{cmd} {shlex.quote(full_path)}"
        return None

    def toggle_selection(self, mode):
        if not self.files:
            return
        f = self.files[self.selected_index]
        if f == "..": 
            return
        if self.clipboard and self.clipboard_action != mode:
            self.clipboard_action = mode
        self.clipboard_action = mode
        p = os.path.join(self.path, f)
        if p in self.clipboard: 
            self.clipboard.remove(p)
        else:
            self.clipboard.append(p)
            self.selected_index = min(len(self.files)-1, self.selected_index + 1)
        self._invalidate_ui()

    def action_paste(self):
        if not self.clipboard: 
            return
        count = 0
        action = self.clipboard_action
        for src in self.clipboard:
            try:
                dst = os.path.join(self.path, os.path.basename(src))
                if action == 'move': 
                    shutil.move(src, dst)
                else:
                    if os.path.isdir(src): 
                        shutil.copytree(src, dst)
                    else: 
                        shutil.copy2(src, dst)
                count += 1
            except Exception as e: 
                self.log_to_terminal(f"Chyba {src}: {e}\n")
        self.clipboard = []
        self.refresh_files()
        self.log_to_terminal(f"Hotovo ({action} {count}).\n")

    async def action_rename(self):
        f = self.files[self.selected_index]
        if f == "..": 
            return
        
        new_name = await self._show_input_dialog(
            title="Přejmenovat",
            label_text=f"Nový název pro '{f}':",
            default=f
        )

        if new_name and new_name != f:
            try:
                os.rename(os.path.join(self.path, f), os.path.join(self.path, new_name))
                self.refresh_files()
                self.log_to_terminal(f"Přejmenováno: {f} -> {new_name}\n")
            except Exception as e:
                self.log_to_terminal(f"Chyba: {e}\n")

    async def action_create_alias(self):
        f = self.files[self.selected_index]
        if f == "..": 
            return
        
        full_path = os.path.join(self.path, f)
        default_name = os.path.splitext(f)[0]
        
        alias_name = await self._show_input_dialog(
            title="Vytvořit alias",
            label_text=f"Zadejte název aliasu pro '{f}':",
            default=default_name
        )
        
        if alias_name:
            if f.endswith('.py'): 
                cmd = f"python3 '{full_path}'"
            elif f.endswith('.sh'): 
                cmd = f"bash '{full_path}'"
            elif f.endswith('.js'): 
                cmd = f"node '{full_path}'"
            else: 
                cmd = f"'{full_path}'"
            
            line = f"\nalias {alias_name}=\"{cmd}\"\n"
            rc_path = os.path.expanduser("~/.bashrc")
            
            try:
                with open(rc_path, "a") as rc:
                    rc.write(line)
                self.log_to_terminal(f"Alias '{alias_name}' přidán do .bashrc\n")
                get_app().create_background_task(self.run_script_async(f"source {rc_path} && echo 'Konfigurace načtena'"))
            except Exception as e:
                self.log_to_terminal(f"Chyba zápisu aliasu: {e}\n")

if __name__ == "__main__":
    try:
        fm = RenegadeFM_Ultimate()
        fm.app.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
