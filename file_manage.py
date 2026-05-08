#!/usr/bin/env python3
import os
import shutil
import asyncio
import shlex
import json
import tarfile
import subprocess
import pty
import fcntl
import termios
import struct
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML, ANSI, to_formatted_text
from prompt_toolkit.application import run_in_terminal, get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.widgets import Dialog, Label, Button, TextArea, RadioList
from prompt_toolkit.lexers import Lexer

class AnsiLexer(Lexer):
    def lex_document(self, document):
        def get_line(lineno):
            return to_formatted_text(ANSI(document.lines[lineno]))
        return get_line

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
            ".json": "yellow",
            ".jsonl": "yellow",
            ".yml": "yellow",
            ".yaml": "yellow",
            ".toml": "yellow",
            ".xml": "yellow",
            ".conf": "white",
            ".log": "gray",
            ".tar": "red",
            ".gz": "red",
            ".zip": "red",
            ".rar": "red",
            ".7z": "red",
            ".c": "cyan",
            ".cpp": "cyan",
            ".h": "cyan",
            ".hpp": "cyan",
            ".rs": "red",
            ".go": "cyan",
            ".java": "red",
            ".kt": "magenta",
            ".sql": "yellow",
            ".db": "yellow",
            ".sqlite": "yellow",
            ".jpg": "cyan",
            ".png": "cyan",
            ".gif": "cyan",
            ".svg": "cyan",
            ".mp3": "blue",
            ".mp4": "blue",
            ".pdf": "white",
            ".html": "green",
            ".css": "blue",
            ".js": "yellow",
            ".ts": "blue",
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
        self.tar_marks = set()
        self.clipboard = []
        self.clipboard_action = 'copy'
        
        self.message = "RenegadeFM - [Tab]Hledat [F2]Nastaveni [Ctrl+R]Mark [Ctrl+Q]Exit"
        self.supermod_active = False
        self.terminal_fullscreen = False
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

        # Log / Terminal
        self.terminal_buffer = Buffer()
        self.terminal_control = BufferControl(
            buffer=self.terminal_buffer,
            lexer=AnsiLexer(),
            focusable=True
        )
        self.terminal_window = Window(
            content=self.terminal_control,
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
        
        # Definice kontejnerů s filtry pro přepínání
        self.manager_view = HSplit([
            Window(height=1, content=FormattedTextControl(self.get_header), style="class:header"),
            top_split,
            Window(height=1, char='─', style="class:line"),
            ConditionalContainer(
                content=HSplit([
                    Window(height=1, content=FormattedTextControl(HTML(" <b>REAL TERMINAL SESSION</b>")), style="class:header"),
                    self.terminal_window,
                    Window(height=1, char='─', style="class:line"),
                ]),
                filter=Condition(lambda: self.settings["show_log"])
            ),
            self.search_input,
            Window(height=1, content=FormattedTextControl(self.get_footer), style="class:footer"),
        ])

        self.fullscreen_terminal_view = HSplit([
            Window(height=1, content=FormattedTextControl(HTML(" <b>TERMINAL FULLSCREEN (Ctrl+T pro návrat)</b>")), style="class:header"),
            self.terminal_window,
        ])

        # Hlavní tělo aplikace přepíná mezi manažerem a full-screen terminálem
        main_body = HSplit([
            ConditionalContainer(content=self.manager_view, filter=Condition(lambda: not self.terminal_fullscreen)),
            ConditionalContainer(content=self.fullscreen_terminal_view, filter=Condition(lambda: self.terminal_fullscreen)),
        ])

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
        self.setup_terminal() # Spuštění terminálu
        
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
            'tar-mark': '#0088ff bold',
            'preview-header': '#00ffff bold underline',
            'terminal': '#aaaaaa',
            'input': '#ffffff bold',
            'dialog': 'bg:#000088',
            'dialog.body': 'bg:#ffffff #000000',
            'button.focused': 'bg:#ff0000 #ffffff',
            'ansired': '#ff0000 bold',
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

    def setup_terminal(self):
        # Spuštění persistentní bash relace přes PTY
        try:
            self.master_fd, self.slave_fd = pty.openpty()
            self.terminal_proc = subprocess.Popen(
                ["bash"],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=self.path,
                env=os.environ.copy()
            )
            # Nastavení master_fd na neblokující čtení
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Přidání čtečky do asyncio loopu
            loop = asyncio.get_event_loop()
            loop.add_reader(self.master_fd, self._on_terminal_output)
            
            # Prvotní synchronizace cesty
            self.sync_terminal_path()
        except Exception as e:
            self.log_to_terminal(f"Chyba inicializace terminálu: {e}\n")

    def _on_terminal_output(self):
        try:
            data = os.read(self.master_fd, 8192).decode('utf-8', 'replace')
            if data:
                current_text = self.terminal_buffer.text
                new_text = current_text + data
                # Limitujeme velikost bufferu na 50000 znaků
                if len(new_text) > 50000:
                    new_text = new_text[-50000:]
                
                # Aktualizace bufferu (bypass_readonly=True umožní zápis i když je fokusovaný)
                self.terminal_buffer.set_document(Document(new_text, cursor_position=len(new_text)), bypass_readonly=True)
                get_app().invalidate()
        except Exception:
            pass

    def send_to_terminal(self, text):
        try:
            os.write(self.master_fd, text.encode())
        except Exception as e:
            self.log_to_terminal(f"Chyba zápisu do terminálu: {e}\n")

    def sync_terminal_path(self):
        # Synchronizace CWD terminálu s manažerem
        # Mezera před 'cd' zabrání uložení do historie v mnoha shell konfiguracích
        cmd = f" cd {shlex.quote(self.path)}\n"
        self.send_to_terminal(cmd)

    def log_to_terminal(self, text):
        if not self.settings["show_log"]:
            return
        # Logujeme přímo do bufferu terminálu s ANSI barvou pro odlišení (žlutá)
        fm_text = f"\x1b[33m[FM]: {text}\x1b[0m"
        if not fm_text.endswith('\n'):
            fm_text += '\n'
        
        current_text = self.terminal_buffer.text
        new_text = current_text + fm_text
        self.terminal_buffer.set_document(Document(new_text, cursor_position=len(new_text)), bypass_readonly=True)
        get_app().invalidate()

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
        except PermissionError:
            if not self.supermod_active:
                self.supermod_active = True
                self.log_to_terminal(f"[⚡ SUPERMOD] Permission denied → SuperMod aktivován pro {self.path}\n")
            entries = [".."] + self._supermod_scan()
        except Exception:
            entries = [".."]
        
        # Synchronizace terminálu při každém osvěžení souborů (včetně změny cesty)
        if hasattr(self, 'master_fd'):
            self.sync_terminal_path()
            
        self.all_files = entries
        self.apply_search_filter()

    def _supermod_scan(self):
        """Best-effort listing: scandir + pm list packages fallback."""
        import subprocess
        path = self.path
        results = []

        # Try scandir — may yield partial results before failing
        try:
            for entry in os.scandir(path):
                results.append(entry.name)
            return sorted(results)
        except PermissionError:
            pass

        # For /data/data specifically: use pm list packages
        if path.rstrip('/') in ('/data/data', '/data'):
            pkg_set = set()
            # Our own package is always accessible
            prefix = os.environ.get('PREFIX', '')
            if prefix:
                parts = prefix.split('/')
                if len(parts) > 3:
                    pkg_set.add(parts[3])  # e.g. com.termux
            try:
                r = subprocess.run(
                    ['pm', 'list', 'packages'],
                    capture_output=True, text=True, timeout=5
                )
                for line in r.stdout.splitlines():
                    if line.startswith('package:'):
                        pkg_set.add(line[8:].strip())
            except Exception:
                pass
            return sorted(pkg_set)

        return results

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
        if self.supermod_active:
            return HTML(f" <b>⚡ SUPERMOD</b> <ansired>{self.path}</ansired> | [i]→Home  [I]→Internal  [S] Deactivate")
        return HTML(f" <b>PATH:</b> {self.path} | <b>DEL:</b> {len(self.delete_marks)} | <b>TAR:</b> {len(self.tar_marks)}")

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
                accessible = os.access(full_path, os.R_OK)
                display = f"📁 {filename}" if accessible else f"🔒 {filename}"
                color_name = ext_colors.get("directory", "green")
                color = self.COLOR_PRESETS.get(color_name, "#00ff00")
                style_class = f"fg:{color}" if accessible else "fg:#ff6600"
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
                elif self.clipboard_action == 'symlink':
                    style_class += " fg:#00ffff bold"
                    display += " [LINK]"
                else:
                    style_class += " class:copy-mark"
                    display += " [COPY]"
            
            if full_path in self.delete_marks:
                style_class += " class:delete-mark"
                display += " [DEL]"
            
            if full_path in self.tar_marks:
                style_class += " class:tar-mark"
                display += " [TAR]"

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
        if self.supermod_active:
            return HTML(" <b>⚡ SUPERMOD</b> | <ansired>i</ansired>=→Home  <ansired>I</ansired>=→Internal  <ansired>S</ansired>=Deactivate  | 🔒=nedostupné")
        
        mode_map = {'copy': 'COPY', 'move': 'CUT/MOVE', 'symlink': 'SYMLINK'}
        mode = mode_map.get(self.clipboard_action, "NONE")
        clip_info = f"{len(self.clipboard)} ({mode})" if self.clipboard else "0"
        marked = f"{len(self.delete_marks)} k mazání" if self.delete_marks else "0"
        return HTML(f" <b>CLIP:</b> {clip_info} | <b>MARKED:</b> {marked} | Preview: {'ON' if self.settings['large_preview'] else 'OFF'}")

    def get_help_text(self):
        return """
 ZKRATKY
 -------
 Home        : Domovská složka
 End / Ctrl+Q: Ukončit aplikaci
 Tab         : Přepnout fokus (Soubory -> Hledat -> Terminál)
 Ctrl+T      : Full-screen Terminál (ZAP/VYP)
 Enter       : Otevřít/spustit
 Šipka vlevo : Zpět (..)
 
 PgUp        : Označit pro SYMLINK
 F2          : Nastavení
 
 Ctrl+R      : Přepnout označení ke smazání
 r           : Smazat (s potvrzením)
 c           : Kopírovat
 x           : Vyjmout
 v           : Vložit (Kopie/Přesun/Symlink)
 Ctrl+v      : Vložit Symlink s novým názvem
 
 z           : Označit k archivaci (TAR)
 Ctrl+z      : Vytvořit TAR archiv (TAR, GZ, BZ2)
 
 n           : Nový soubor
 m           : Nová složka
 e           : Editovat (nano)
 Ctrl+e      : Přejmenovat

 TERMINÁL
 --------
 - Spodní okno je nyní reálná bash relace.
 - Fokus se přepíná klávesou Tab.
 - Terminál automaticky následuje složku v manažeru.
 - Výstupy operací (mazání, kopírování) se zobrazují zde.

 ⚡ SUPERMOD
 -----------
 S           : Zapnout/vypnout SuperMod (/data/data/)
 i           : [SuperMod] Kopírovat → ~/Home
 I           : [SuperMod] Kopírovat → ~/storage/shared/
 🔒          : Složka/soubor bez přístupu

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
            
            # Programování
            self.settings["extension_colors"][".py"] = py_color_radio.current_value
            self.settings["extension_colors"][".sh"] = sh_color_radio.current_value
            self.settings["extension_colors"][".js"] = js_color_radio.current_value
            self.settings["extension_colors"][".rs"] = rs_color_radio.current_value
            self.settings["extension_colors"][".cpp"] = cpp_color_radio.current_value
            self.settings["extension_colors"][".c"] = cpp_color_radio.current_value
            self.settings["extension_colors"][".h"] = cpp_color_radio.current_value
            
            # Config / DB
            self.settings["extension_colors"][".json"] = json_color_radio.current_value
            self.settings["extension_colors"][".jsonl"] = json_color_radio.current_value
            self.settings["extension_colors"][".yml"] = yaml_color_radio.current_value
            self.settings["extension_colors"][".yaml"] = yaml_color_radio.current_value
            self.settings["extension_colors"][".sql"] = sql_color_radio.current_value
            self.settings["extension_colors"][".db"] = sql_color_radio.current_value
            
            # Text / Web
            self.settings["extension_colors"][".txt"] = txt_color_radio.current_value
            self.settings["extension_colors"][".md"] = md_color_radio.current_value
            self.settings["extension_colors"][".html"] = html_color_radio.current_value
            self.settings["extension_colors"][".log"] = log_color_radio.current_value
            
            # Média / Systém
            self.settings["extension_colors"]["directory"] = dir_color_radio.current_value
            
            # Sjednocené Archivy
            arc_color = tar_color_radio.current_value
            for ext in [".tar", ".gz", ".zip", ".rar", ".7z"]:
                self.settings["extension_colors"][ext] = arc_color
                
            # Obrázky
            img_color = img_color_radio.current_value
            for ext in [".jpg", ".png", ".gif", ".svg"]:
                self.settings["extension_colors"][ext] = img_color
            
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

        color_choices = [(k, k.upper()) for k in self.COLOR_PRESETS.keys()]

        # Barevné RadioListy
        py_color_radio = RadioList(color_choices); py_color_radio.current_value = self.settings["extension_colors"].get(".py", "magenta")
        sh_color_radio = RadioList(color_choices); sh_color_radio.current_value = self.settings["extension_colors"].get(".sh", "magenta")
        js_color_radio = RadioList(color_choices); js_color_radio.current_value = self.settings["extension_colors"].get(".js", "yellow")
        rs_color_radio = RadioList(color_choices); rs_color_radio.current_value = self.settings["extension_colors"].get(".rs", "red")
        cpp_color_radio = RadioList(color_choices); cpp_color_radio.current_value = self.settings["extension_colors"].get(".cpp", "cyan")
        
        json_color_radio = RadioList(color_choices); json_color_radio.current_value = self.settings["extension_colors"].get(".json", "yellow")
        yaml_color_radio = RadioList(color_choices); yaml_color_radio.current_value = self.settings["extension_colors"].get(".yml", "yellow")
        sql_color_radio = RadioList(color_choices); sql_color_radio.current_value = self.settings["extension_colors"].get(".sql", "yellow")
        
        txt_color_radio = RadioList(color_choices); txt_color_radio.current_value = self.settings["extension_colors"].get(".txt", "white")
        md_color_radio = RadioList(color_choices); md_color_radio.current_value = self.settings["extension_colors"].get(".md", "green")
        html_color_radio = RadioList(color_choices); html_color_radio.current_value = self.settings["extension_colors"].get(".html", "green")
        log_color_radio = RadioList(color_choices); log_color_radio.current_value = self.settings["extension_colors"].get(".log", "gray")
        
        dir_color_radio = RadioList(color_choices); dir_color_radio.current_value = self.settings["extension_colors"].get("directory", "green")
        tar_color_radio = RadioList(color_choices); tar_color_radio.current_value = self.settings["extension_colors"].get(".tar", "red")
        img_color_radio = RadioList(color_choices); img_color_radio.current_value = self.settings["extension_colors"].get(".jpg", "cyan")

        # Layout se 4 sloupci
        col1 = HSplit([
            Label(text="[ PROGR. 1 ]", style="class:header"),
            Label(text=".py:"), py_color_radio,
            Label(text=".sh:"), sh_color_radio,
            Label(text=".js:"), js_color_radio,
        ], padding=0)

        col2 = HSplit([
            Label(text="[ PROGR. 2 ]", style="class:header"),
            Label(text=".rs:"), rs_color_radio,
            Label(text="C/C++:"), cpp_color_radio,
            Label(text="SQL/DB:"), sql_color_radio,
        ], padding=0)

        col3 = HSplit([
            Label(text="[ CONFIG/TXT ]", style="class:header"),
            Label(text="JSON:"), json_color_radio,
            Label(text="YAML:"), yaml_color_radio,
            Label(text="TEXT:"), txt_color_radio,
            Label(text="MD:"), md_color_radio,
        ], padding=0)

        col4 = HSplit([
            Label(text="[ SYSTÉM/MÉDIA ]", style="class:header"),
            Label(text="Složky:"), dir_color_radio,
            Label(text="Archivy:"), tar_color_radio,
            Label(text="Obrázky:"), img_color_radio,
            Label(text="HTML/Log:"), html_color_radio,
        ], padding=0)

        dialog_body = VSplit([
            col1, Window(width=1, char='│', style="class:line"),
            col2, Window(width=1, char='│', style="class:line"),
            col3, Window(width=1, char='│', style="class:line"),
            col4,
        ], padding=1)

        dialog = Dialog(
            title="NASTAVENÍ BAREV (Tab přepíná sloupce)",
            body=dialog_body,
            buttons=[
                Button(text="Uložit", handler=apply_settings),
                Button(text="Zrušit", handler=cancel),
            ],
            with_background=True,
        )

        self.active_dialog = {"type": "settings"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(py_color_radio)
        get_app().invalidate()

        return await future

    def setup_bindings(self):
        kb = self.kb

        panel_focus = Condition(lambda: self.layout.has_focus(self.file_list_control)) & Condition(lambda: self.active_dialog is None)
        allow_focus_toggle = Condition(lambda: self.active_dialog is None)

        @kb.add('f1', filter=panel_focus)
        @kb.add('?', filter=panel_focus)
        @kb.add('c-h', filter=panel_focus)
        def _(event): 
            self.toggle_help()

        @kb.add('tab', filter=allow_focus_toggle)
        def _(event):
            if self.terminal_fullscreen:
                return # V full-screenu tabulátor posíláme do terminálu
            if self.layout.has_focus(self.file_list_control):
                self.layout.focus(self.search_input)
            elif self.layout.has_focus(self.search_input):
                if self.settings["show_log"]:
                    self.layout.focus(self.terminal_control)
                else:
                    self.layout.focus(self.file_list_control)
            else:
                self.layout.focus(self.file_list_control)
        
        @kb.add('c-t', filter=allow_focus_toggle)
        def _(event):
            self.terminal_fullscreen = not self.terminal_fullscreen
            if self.terminal_fullscreen:
                self.layout.focus(self.terminal_control)
            else:
                self.layout.focus(self.file_list_control)
            self._invalidate_ui()

        @kb.add('f2', filter=panel_focus)
        def _(event):
            asyncio.create_task(self.show_settings_dialog())

        not_in_terminal = (~has_focus(self.terminal_control)) & allow_focus_toggle

        @kb.add('end', filter=not_in_terminal)
        def _(event):
            self._save_last_path()
            event.app.exit()

        @kb.add('c-q', filter=not_in_terminal)
        def _(event):
            self._save_last_path()
            self.log_to_terminal(f"\n[EXIT] Ukončení - poslední složka: {self.path}\n")
            event.app.exit()

        @kb.add('c-c', filter=not_in_terminal)
        def _(event):
            self._save_last_path()
            self.log_to_terminal(f"\n[EXIT] Ctrl+C - poslední složka: {self.path}\n")
            event.app.exit()

        @kb.add('q', filter=not_in_terminal)
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self._save_last_path()
                self.log_to_terminal(f"\n[EXIT] Konec - poslední složka: {self.path}\n")
                event.app.exit()

        # TERMINAL BINDINGS
        # Přidáváme podmínku allow_focus_toggle (žádný dialog), aby terminál nepolykal klávesy v dialozích
        in_terminal = has_focus(self.terminal_control) & allow_focus_toggle

        @kb.add('<any>', filter=in_terminal)
        def _(event):
            for char in event.data:
                self.send_to_terminal(char)

        @kb.add('tab', filter=in_terminal)
        def _(event):
            # Poslat skutečný TAB do terminálu
            self.send_to_terminal('\t')

        @kb.add('enter', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\r')

        @kb.add('backspace', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x7f')
        
        @kb.add('c-c', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x03')

        @kb.add('c-d', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x04')

        @kb.add('c-l', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x0c')
            
        @kb.add('up', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x1b[A')

        @kb.add('down', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x1b[B')

        @kb.add('right', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x1b[C')

        @kb.add('left', filter=in_terminal)
        def _(event):
            self.send_to_terminal('\x1b[D')

        in_file_list = Condition(lambda: self.layout.has_focus(self.file_list_control)) & allow_focus_toggle

        @kb.add('up', filter=in_file_list)
        def _(event): 
            self.selected_index = max(0, self.selected_index - 1)

        @kb.add('down', filter=in_file_list)
        def _(event): 
            self.selected_index = min(len(self.files) - 1, self.selected_index + 1)

        @kb.add('pageup', filter=in_file_list)
        def _(event):
            self.toggle_selection('symlink')

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

        @kb.add('c-v', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_paste_symlink_custom())

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

        @kb.add('s', filter=in_file_list)
        def _(event):
            if self.supermod_active:
                self.supermod_active = False
                self.path = os.path.expanduser("~")
                self.log_to_terminal("[⚡ SUPERMOD] Deaktivován\n")
            else:
                self.supermod_active = True
                self.path = "/data/data"
                self.log_to_terminal("[⚡ SUPERMOD] Aktivován — /data/data/\n")
            self.refresh_files()

        @kb.add('i', filter=in_file_list)
        def _(event):
            if self.supermod_active:
                asyncio.create_task(self.supermod_copy_to_home())

        @kb.add('I', filter=in_file_list)
        def _(event):
            if self.supermod_active:
                asyncio.create_task(self.supermod_copy_to_internal())

        @kb.add('z', filter=in_file_list)
        def _(event):
            self.toggle_tar_mark()

        @kb.add('c-z', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_tar_marked())

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

    def toggle_tar_mark(self):
        if not self.files:
            return
        filename = self.files[self.selected_index]
        if filename == "..":
            return
        full_path = os.path.join(self.path, filename)
        if full_path in self.tar_marks:
            self.tar_marks.remove(full_path)
        else:
            self.tar_marks.add(full_path)
        self._invalidate_ui()

    async def action_tar_marked(self):
        if not self.tar_marks:
            self.log_to_terminal("Žádné soubory k zabalení.\n")
            return
        
        # Výběr formátu komprese
        choice = await self._show_radiolist_dialog(
            title="Vytvořit Archiv",
            text="Vyberte formát archivu:",
            values=[
                ("tar", "Jen TAR (bez komprese)"),
                ("tar.gz", "TAR.GZ (Gzip komprese)"),
                ("tar.bz2", "TAR.BZ2 (Bzip2 komprese)")
            ]
        )
        
        if not choice:
            self.log_to_terminal("Vytváření archivu zrušeno.\n")
            return

        archive_name = await self._show_input_dialog(
            title="Název archivu",
            label_text=f"Zadejte název souboru (bez .{choice}):",
            default="archive"
        )

        if not archive_name:
            self.log_to_terminal("Vytváření archivu zrušeno.\n")
            return

        archive_path = os.path.join(self.path, f"{archive_name}.{choice}")
        mode = "w:gz" if choice == "tar.gz" else ("w:bz2" if choice == "tar.bz2" else "w")
        
        try:
            with tarfile.open(archive_path, mode) as tar:
                for file_path in self.tar_marks:
                    arcname = os.path.basename(file_path)
                    tar.add(file_path, arcname=arcname)
            
            self.tar_marks.clear()
            self.refresh_files()
            self.log_to_terminal(f"Archiv '{archive_name}.{choice}' vytvořen.\n")
        except Exception as e:
            self.log_to_terminal(f"Chyba při vytváření archivu: {e}\n")


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
            try:
                os.listdir(full_path)  # Test access
                self.path = full_path
            except PermissionError:
                self.supermod_active = True
                self.path = full_path
                self.log_to_terminal(f"[⚡ SUPERMOD] Auto-aktivován pro {full_path}\n")
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
                elif action == 'symlink':
                    os.symlink(src, dst)
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

    async def action_paste_symlink_custom(self):
        if not self.clipboard or self.clipboard_action != 'symlink':
            self.log_to_terminal("Nic není označeno pro symlink.\n")
            return
        
        src = self.clipboard[0] # Bereme první označený pro přejmenování
        default_name = os.path.basename(src)
        
        new_name = await self._show_input_dialog(
            title="Nový název symlinku",
            label_text=f"Zadejte název symlinku pro '{default_name}':",
            default=default_name
        )
        
        if new_name:
            dst = os.path.join(self.path, new_name)
            try:
                os.symlink(src, dst)
                self.log_to_terminal(f"Symlink '{new_name}' vytvořen.\n")
                self.clipboard = []
                self.refresh_files()
            except Exception as e:
                self.log_to_terminal(f"Chyba symlinku: {e}\n")

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

    async def supermod_copy_to_home(self):
        if not self.files:
            return
        f = self.files[self.selected_index]
        if f == "..":
            return
        src = os.path.join(self.path, f)
        dst = os.path.join(os.path.expanduser("~"), os.path.basename(src))
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            self.log_to_terminal(f"[⚡ SUPERMOD] Zkopírováno → ~/: {f}\n")
        except Exception as e:
            self.log_to_terminal(f"[⚡ SUPERMOD] Chyba kopírování: {e}\n")

    async def supermod_copy_to_internal(self):
        if not self.files:
            return
        f = self.files[self.selected_index]
        if f == "..":
            return
        src = os.path.join(self.path, f)
        internal = os.path.expanduser("~/storage/shared/")
        dst = os.path.join(internal, os.path.basename(src))
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            self.log_to_terminal(f"[⚡ SUPERMOD] Zkopírováno → Internal: {f}\n")
        except Exception as e:
            self.log_to_terminal(f"[⚡ SUPERMOD] Chyba kopírování: {e}\n")

if __name__ == "__main__":
    try:
        # Explicitní vytvoření a nastavení loopu pro eliminaci DeprecationWarning
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        fm = RenegadeFM_Ultimate()
        fm.app.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
