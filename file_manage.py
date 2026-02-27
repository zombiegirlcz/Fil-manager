#!/usr/bin/env python3
import os
import shutil
import asyncio
import shlex
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

    def __init__(self):
        self.path = self._load_last_path() or os.getcwd()
        self.all_files = []
        self.files = []
        self.selected_index = 0
        self.search_query = ""
        self.ignore_search_buffer_change = False
        
        # Schránka a akce
        self.clipboard = []
        self.clipboard_action = 'copy'
        
        self.message = "RenegadeFM (Transparent) - [Tab] Hledat [Home] Domu [PgUp] Alias"
        self.show_help = False
        self.active_dialog = None  # hlídá aktivní dialog (confirm/input), aby neprobublávaly zkratky
        self.refresh_files()
        
        # --- KOMPONENTY ---
        
        # 1. Vyhledávací řádek
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

        # 2. Spodní terminál (Log)
        self.terminal_buffer = Buffer()
        self.terminal_window = Window(
            content=BufferControl(buffer=self.terminal_buffer),
            wrap_lines=True,
            style="class:terminal",
            height=Dimension(min=5)
        )
        
        # 3. Levý panel (Seznam)
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
        
        # 4. Pravý panel (Náhled)
        self.preview_window = Window(
            content=FormattedTextControl(self.get_preview_content), 
            wrap_lines=True, 
            width=Dimension(weight=50)
        )

        # --- LAYOUT ---
        top_split = VSplit([
            self.file_window,
            Window(width=1, char='│', style="class:line"),
            self.preview_window,
        ])
        
        main_body = HSplit([
            Window(height=1, content=FormattedTextControl(self.get_header), style="class:header"),
            top_split,
            Window(height=1, char='─', style="class:line"),
            Window(height=1, content=FormattedTextControl(HTML(" <b>LOG / TERMINAL OUTPUT</b>")), style="class:header"),
            self.terminal_window,
            Window(height=1, char='─', style="class:line"),
            self.search_input,
            Window(height=1, content=FormattedTextControl(self.get_footer), style="class:footer"),
        ])

        # Popup (Nápověda) - OPRAVA: Použití ConditionalContainer uvnitř Float
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
        
        # STYLY
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

    def accept_command(self, buff):
        cmd = buff.text.strip()
        if cmd:
            get_app().create_background_task(self.run_script_async(cmd))
        return True

    def log_to_terminal(self, text):
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
                if not line: break
                self.log_to_terminal(line.decode('utf-8', errors='replace'))
                get_app().invalidate()

            await process.wait()
            self.log_to_terminal(f"\n[EXIT] Code: {process.returncode}\n")
            self.refresh_files()
        except Exception as e:
            self.log_to_terminal(f"\n[ERR]: {str(e)}\n")

    async def run_command_with_output(self, command):
        self.log_to_terminal(f"\n[CMD]: {command}\n" + "-"*40 + "\n")
        try:
            process = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.path
            )
            stdout, stderr = await process.communicate()
            
            if stdout:
                self.log_to_terminal(stdout.decode('utf-8', errors='replace'))
            if stderr:
                self.log_to_terminal(stderr.decode('utf-8', errors='replace'))

            self.log_to_terminal(f"\n[EXIT] Code: {process.returncode}\n")
            self.refresh_files()

            return stdout.decode('utf-8', errors='replace').strip(), stderr.decode('utf-8', errors='replace').strip(), process.returncode
        except Exception as e:
            self.log_to_terminal(f"\n[ERR]: {str(e)}\n")
            return "", str(e), 1
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

        if text.startswith("$$"):
            cmd = text[2:].strip()
            if cmd:
                self.log_to_terminal(f"[CMD] Spoustim v nove session: {cmd}\n")
                run_in_terminal(lambda: os.system(f"bash -lc {shlex.quote(cmd)}"))
            self._reset_search_buffer()
            self._focus_file_list()
            return True

        if text.startswith("$"):
            cmd = text[1:].strip()
            if cmd:
                self.log_to_terminal(f"[CMD] Spoustim: {cmd}\n")
                get_app().create_background_task(self.run_script_async(cmd))
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
        return HTML(f" <b>PATH:</b> {self.path} ")

    def get_file_content(self):
        lines = []
        try: term_height = shutil.get_terminal_size().lines
        except: term_height = 24
        max_h = (term_height // 2) - 2
        
        start_idx = max(0, self.selected_index - max_h // 2)
        end_idx = start_idx + max_h
        visible_files = self.files[start_idx:end_idx]
        
        for i, filename in enumerate(visible_files):
            real_idx = start_idx + i
            full_path = os.path.join(self.path, filename)
            
            style_class = ""
            display = filename
            
            if filename == "..":
                display = "⬆ .. (Zpet)"
                style_class = "class:dir"
            elif os.path.isdir(full_path):
                display = f"📁 {filename}"
                style_class = "class:dir"
            elif os.access(full_path, os.X_OK) or filename.endswith(('.py', '.sh','js')):
                display = f"🚀 {filename}"
                style_class = "class:exec"
            else:
                display = f"📄 {filename}"
                style_class = "class:file"
            
            if full_path in self.clipboard:
                if self.clipboard_action == 'move':
                    style_class += " class:move-mark"
                    display += " [CUT]"
                else:
                    style_class += " class:copy-mark"
                    display += " [COPY]"

            if real_idx == self.selected_index and self.layout.has_focus(self.file_list_control):
                style_class = "class:selected " + style_class
            
            lines.append((style_class, f" {display} \n"))
        return lines

    def get_preview_content(self):
        if not self.files: return []
        filename = self.files[self.selected_index]
        full_path = os.path.join(self.path, filename)
        
        lines = [("class:preview-header", f" {filename} \n"), ("", "\n")]
        
        if os.path.isdir(full_path):
            try:
                items = os.listdir(full_path)[:15]
                lines.append(("", f" Slozka ({len(os.listdir(full_path))} polozek):\n"))
                for item in items:
                    lines.append(("", f"  - {item}\n"))
            except: pass
        elif os.path.isfile(full_path):
            try:
                sz = os.path.getsize(full_path)
                lines.append(("", f" Velikost: {sz} B\n"))
                if sz < 20000:
                    lines.append(("", "-"*20 + "\n"))
                    with open(full_path, 'r', errors='ignore') as f:
                        lines.append(("class:terminal", f.read(800)))
            except: pass
        return lines

    def get_footer(self):
        mode = "COPY" if self.clipboard_action == 'copy' else "CUT/MOVE"
        clip_info = f"{len(self.clipboard)} ({mode})" if self.clipboard else "0"
        search_state = self.search_query or "-"
        return HTML(f" <b>MSG:</b> {self.message} | <b>CLIP:</b> {clip_info} | <b>Hledat:</b> {search_state} | <b>[PgUp]</b> Alias")

    def get_help_text(self):
        return """
 ZKRATKY (v seznamu souboru)
 ---------------------------
 Home        : Domovska slozka (~)
 End         : Ukoncit aplikaci
 Tab         : Fokus na vyhledavani
 Enter       : Otevrit/spustit (v plovoucim okne, pokud je skript)
 Sipka Vlevo : Zpet (..)
 Hledat >    : Filtruje soubory podle zadaneho textu
 
 PgUp        : Vytvorit ALIAS (.bashrc)
 
 r           : Smazat (Enter potvrdit)
 c           : Kopirovat (Copy)
 x           : Vyjmout (Cut)
 v           : Vlozit (Paste)
 n           : Novy soubor
 m           : Nova slozka
 
 Ctrl+e      : Prejmenovat
 Alt+G       : Git Push Dialog
 F1 / ?      : Tato napoveda
 q           : Konec
        """

    async def _show_input_dialog(self, title, label_text, default=""):
        """
        Asynchronně zobrazí dialog pro zadání textu a vrátí výsledek.
        """
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
                Button(text="Zrusit", handler=cancel),
            ],
            with_background=True,
        )

        self.active_dialog = {"type": "input"}
        self.root_container.floats.append(Float(content=dialog))
        self.layout.focus(input_field)
        get_app().invalidate()

        return await future

    async def _show_confirm_dialog(self, title, text):
        """
        Zobrazí potvrzovací dialog a vrátí True pokud uživatel stiskne OK.
        """
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
        # Focus default: Ne
        self.layout.focus(btn_no)
        get_app().invalidate()

        return await future

    async def _show_radiolist_dialog(self, title, text, values):
        """
        Zobrazí dialog s výběrem a vrátí vybranou hodnotu.
        """
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
                Button(text="Zrusit", handler=cancel),
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


    def setup_bindings(self):
        kb = self.kb

        # --- GLOBALNI ---
        panel_focus = Condition(lambda: self.layout.has_focus(self.file_list_control))
        allow_focus_toggle = Condition(lambda: self.active_dialog is None)
        @kb.add('f1', filter=panel_focus)
        @kb.add('?', filter=panel_focus)
        @kb.add('c-h', filter=panel_focus)
        def _(event): self.toggle_help()

        @kb.add('tab', filter=allow_focus_toggle)
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self.layout.focus(self.search_input)
            else:
                self.layout.focus(self.file_list_control)
        
        @kb.add('end')
        def _(event):
            self._save_last_path()
            event.app.exit()

        @kb.add('c-c')
        def _(event):
            if event.key_sequence[0].key == 'c-c':
                self._save_last_path()
                self.log_to_terminal(f"\n[EXIT] Ukonceni pres Ctrl+C - {self.path}\n")
                event.app.exit()

        @kb.add('q')
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self._save_last_path()
                self.log_to_terminal(f"\n[EXIT] Ukonceni - otevreny adresar: {self.path}\n")
                event.app.exit()

        # --- FILE LIST ONLY ---
        in_file_list = Condition(lambda: self.layout.has_focus(self.file_list_control))

        @kb.add('up', filter=in_file_list)
        def _(event): self.selected_index = max(0, self.selected_index - 1)

        @kb.add('down', filter=in_file_list)
        def _(event): self.selected_index = min(len(self.files) - 1, self.selected_index + 1)

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
        def _(event): self.action_enter()

        @kb.add('c', filter=in_file_list)
        def _(event): self.toggle_selection('copy')

        @kb.add('x', filter=in_file_list)
        def _(event): self.toggle_selection('move')

        @kb.add('v', filter=in_file_list)
        def _(event): self.action_paste()

        @kb.add('r', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_delete())
            
        @kb.add('c-e', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_rename())

        @kb.add('escape', 'g', filter=in_file_list)
        def _(event):
            asyncio.create_task(self.action_git_push_dialog())

        @kb.add('m', filter=in_file_list)
        async def _(event):
            name = await self._show_input_dialog("Nova slozka", "Zadejte nazev slozky:")
            if name:
                try:
                    os.mkdir(os.path.join(self.path, name))
                    self.refresh_files()
                    self.log_to_terminal(f"Slozka '{name}' vytvorena.\n")
                except Exception as e:
                    self.log_to_terminal(str(e)+"\n")

        @kb.add('n', filter=in_file_list)
        async def _(event):
            name = await self._show_input_dialog("Novy soubor", "Zadejte nazev souboru:")
            if name:
                try:
                    open(os.path.join(self.path, name), 'a').close()
                    self.refresh_files()
                    self.log_to_terminal(f"Soubor '{name}' vytvoren.\n")
                except Exception as e:
                    self.log_to_terminal(str(e)+"\n")
        
        @kb.add('e', filter=in_file_list)
        def _(event):
            f = self.files[self.selected_index]
            if f != "..":
                run_in_terminal(lambda: os.system(f"nano '{os.path.join(self.path, f)}'"))

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
            archive_cmd = self._build_archive_command(filename, full_path)
            if archive_cmd:
                self.log_to_terminal(f"[ARCHIVE] Rozbaluji '{filename}'\n")
                get_app().create_background_task(self.run_script_async(archive_cmd))
                return

            script_cmd = self._build_script_command(filename, full_path)
            if not script_cmd and os.access(full_path, os.X_OK):
                script_cmd = shlex.quote(full_path)

            if script_cmd:
                float_cmd = f"am start -n com.termux.window/.TermuxFloatActivity -e com.termux.execute \"{script_cmd}\""
                run_in_terminal(lambda: os.system(float_cmd))
                self.log_to_terminal(f"[INFO] Spoustim '{filename}' v plovoucim okne...\n")
                return
                
            run_in_terminal(lambda: os.system(f"nano '{full_path}'"))

    async def action_git_push_dialog(self):
        # Step 1: Check for .git directory
        stdout, stderr, returncode = await self.run_command_with_output("git rev-parse --is-inside-work-tree")
        
        is_git_repo = returncode == 0 and stdout.strip() == "true"

        if not is_git_repo:
            confirmed = await self._show_confirm_dialog(
                title="Git Repozitar",
                text="Toto neni Git repozitar. Chcete jej inicializovat?"
            )
            if confirmed:
                await self.run_script_async("git init")
            else:
                self.log_to_terminal("Operace Git Push zrusena.\n")
                return
        
        # Step 2: Check for remote
        remote_url, _, returncode = await self.run_command_with_output("git remote get-url origin")
        if returncode != 0:
            remote_url_input = await self._show_input_dialog(
                title="Vzdaleny repozitar",
                label_text="Zadejte URL pro 'origin':"
            )
            if remote_url_input:
                await self.run_script_async(f"git remote add origin {shlex.quote(remote_url_input)}")
            else:
                self.log_to_terminal("Operace Git Push zrusena.\n")
                return
        
        # Step 3: Get Branch
        current_branch, _, _ = await self.run_command_with_output("git branch --show-current")
        branch_choices = [("main", "main"), ("master", "master")]
        if current_branch and (current_branch, current_branch) not in branch_choices:
            branch_choices.insert(0, (current_branch, current_branch))
        
        branch_choices.append(("custom", "Vlastni..."))

        branch = await self._show_radiolist_dialog(
            title="Vyberte vetev",
            text="Do ktere vetve chcete pushovat?",
            values=branch_choices
        )

        if not branch:
            self.log_to_terminal("Operace Git Push zrusena.\n")
            return
        
        if branch == "custom":
            branch = await self._show_input_dialog(
                title="Vlastni vetev",
                label_text="Zadejte nazev vetve:"
            )
            if not branch:
                self.log_to_terminal("Operace Git Push zrusena.\n")
                return

        # Step 4: Commit changes
        status_output, _, _ = await self.run_command_with_output("git status --porcelain")
        if status_output:
            commit_confirmed = await self._show_confirm_dialog(
                title="Commit",
                text="Mate necommitnute zmeny. Chcete je pridat a commitnout?"
            )
            if commit_confirmed:
                commit_message = await self._show_input_dialog(
                    title="Commit zprava",
                    label_text="Zadejte zpravu pro commit:"
                )
                if commit_message:
                    await self.run_script_async("git add .")
                    await self.run_script_async(f"git commit -m {shlex.quote(commit_message)}")
                else:
                    self.log_to_terminal("Operace Git Push zrusena - prazdna commit zprava.\n")
                    return
            else:
                self.log_to_terminal("Push pokracuje bez commitu...\n")

        # Step 5: Push
        push_confirmed = await self._show_confirm_dialog(
            title="Git Push",
            text=f"Opravdu chcete pushovat do 'origin/{branch}'?"
        )
        if push_confirmed:
            await self.run_script_async(f"git push origin {shlex.quote(branch)}")
        else:
            self.log_to_terminal("Operace Git Push zrusena.\n")

    def _build_archive_command(self, filename, full_path):
        lower = filename.lower()
        quote_path = shlex.quote(full_path)
        quote_dir = shlex.quote(self.path)
        if lower.endswith(('.tar.gz', '.tgz')):
            return f"tar -xzf {quote_path} -C {quote_dir}"
        if lower.endswith('.tar.bz2'):
            return f"tar -xjf {quote_path} -C {quote_dir}"
        if lower.endswith(('.tar.xz', '.txz')):
            return f"tar -xJf {quote_path} -C {quote_dir}"
        if lower.endswith('.tar'):
            return f"tar -xf {quote_path} -C {quote_dir}"
        if lower.endswith('.zip'):
            return f"unzip -o {quote_path} -d {quote_dir}"
        return None

    def _build_script_command(self, filename, full_path):
        ext = os.path.splitext(filename)[1].lower()
        cmd = self.SCRIPT_COMMAND_MAP.get(ext)
        if cmd:
            return f"{cmd} {shlex.quote(full_path)}"
        return None

    def toggle_selection(self, mode):
        f = self.files[self.selected_index]
        if f == "..": return
        if self.clipboard and self.clipboard_action != mode:
            self.clipboard_action = mode
        self.clipboard_action = mode
        p = os.path.join(self.path, f)
        if p in self.clipboard: self.clipboard.remove(p)
        else:
            self.clipboard.append(p)
            self.selected_index = min(len(self.files)-1, self.selected_index + 1)

    def action_paste(self):
        if not self.clipboard: return
        count = 0
        action = self.clipboard_action
        for src in self.clipboard:
            try:
                dst = os.path.join(self.path, os.path.basename(src))
                if action == 'move': shutil.move(src, dst)
                else:
                    if os.path.isdir(src): shutil.copytree(src, dst)
                    else: shutil.copy2(src, dst)
                count += 1
            except Exception as e: self.log_to_terminal(f"Chyba {src}: {e}\n")
        self.clipboard = []
        self.refresh_files()
        self.log_to_terminal(f"Hotovo ({action} {count}).\n")

    async def action_delete(self):
        f = self.files[self.selected_index]
        if f == "..": return
        
        confirmed = await self._show_confirm_dialog(
            title="Smazat",
            text=f"Opravdu si prejete smazat '{f}'?"
        )

        if confirmed:
            try:
                p = os.path.join(self.path, f)
                if os.path.isdir(p): shutil.rmtree(p)
                else: os.remove(p)
                self.refresh_files()
                self.log_to_terminal(f"Smazano: {f}\n")
            except Exception as e:
                self.log_to_terminal(f"Chyba: {e}\n")
        else:
            self.log_to_terminal("Mazani zruseno.\n")

    async def action_rename(self):
        f = self.files[self.selected_index]
        if f == "..": return
        
        new_name = await self._show_input_dialog(
            title="Prejmenovat",
            label_text=f"Novy nazev pro '{f}':",
            default=f
        )

        if new_name and new_name != f:
            try:
                os.rename(os.path.join(self.path, f), os.path.join(self.path, new_name))
                self.refresh_files()
                self.log_to_terminal(f"Prejmenovano: {f} -> {new_name}\n")
            except Exception as e:
                self.log_to_terminal(f"Chyba: {e}\n")

    async def action_create_alias(self):
        f = self.files[self.selected_index]
        if f == "..": return
        
        full_path = os.path.join(self.path, f)
        default_name = os.path.splitext(f)[0]
        
        alias_name = await self._show_input_dialog(
            title="Vytvorit alias",
            label_text=f"Zadejte nazev aliasu pro '{f}':",
            default=default_name
        )
        
        if alias_name:
            if f.endswith('.py'): cmd = f"python3 '{full_path}'"
            elif f.endswith('.sh'): cmd = f"bash '{full_path}'"
            elif f.endswith('.js'): cmd = f"node '{full_path}'"
            else: cmd = f"'{full_path}'"
            
            line = f"\nalias {alias_name}=\"{cmd}\"\n"
            rc_path = os.path.expanduser("~/.bashrc")
            
            try:
                with open(rc_path, "a") as rc:
                    rc.write(line)
                self.log_to_terminal(f"Alias '{alias_name}' pridan do .bashrc\n")
                get_app().create_background_task(self.run_script_async(f"source {rc_path} && echo 'Konfigurace nactena'"))
            except Exception as e:
                self.log_to_terminal(f"Chyba zapisu aliasu: {e}\n")

if __name__ == "__main__":
    try:
        fm = RenegadeFM_Ultimate()
        fm.app.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
