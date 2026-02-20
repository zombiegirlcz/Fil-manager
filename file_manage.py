#!/usr/bin/env python3
import os
import shutil
import asyncio
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
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.widgets import Dialog, Label, Button, TextArea

class RenegadeFM_Ultimate:
    def __init__(self):
        self.path = os.getcwd()
        self.files = []
        self.selected_index = 0
        
        # Schránka a akce
        self.clipboard = []
        self.clipboard_action = 'copy'
        
        self.message = "RenegadeFM (Transparent) - [Tab] CMD [Home] Domu [PgUp] Alias"
        self.show_help = False
        self.refresh_files()
        
        # --- KOMPONENTY ---
        
        # 1. Příkazový řádek
        self.command_input = TextArea(
            height=1,
            prompt='CMD > ',
            style='class:input',
            multiline=False,
            accept_handler=self.accept_command
        )

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
            self.command_input,
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
                stderr=asyncio.subprocess.STDOUT
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

    def refresh_files(self):
        try:
            self.files = sorted(os.listdir(self.path))
            self.files.insert(0, "..")
        except:
            self.files = [".."]
        self.selected_index = 0

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
            elif os.access(full_path, os.X_OK) or filename.endswith(('.py', '.sh')):
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
        return HTML(f" <b>MSG:</b> {self.message} | <b>CLIP:</b> {clip_info} | <b>[PgUp]</b> Alias")

    def get_help_text(self):
        return """
 ZKRATKY (v seznamu souboru)
 ---------------------------
 Home        : Domovska slozka (~)
 End         : Ukoncit aplikaci
 Tab         : Prikazovy radek
 Enter       : Otevrit / Spustit
 Sipka Vlevo : Zpet (..)
 
 PgUp        : Vytvorit ALIAS (.bashrc)
 
 r           : Smazat (Enter potvrdit)
 c           : Kopirovat (Copy)
 x           : Vyjmout (Cut)
 v           : Vlozit (Paste)
 n           : Novy soubor
 m           : Nova slozka
 
 Ctrl+e      : Prejmenovat
 Ctrl+h      : Tato napoveda
 q           : Konec
        """

    async def _show_input_dialog(self, title, label_text, default=""):
        """
        Asynchronně zobrazí dialog pro zadání textu a vrátí výsledek.
        """
        future = asyncio.Future()

        def accept(buf):
            self.root_container.floats.pop()
            future.set_result(input_field.text)
            self.layout.focus(self.file_list_control)

        def cancel():
            self.root_container.floats.pop()
            future.set_result(None)
            self.layout.focus(self.file_list_control)

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

        def cancel():
            self.root_container.floats.pop()
            future.set_result(False)
            self.layout.focus(self.file_list_control)

        dialog = Dialog(
            title=title,
            body=Label(text=text, dont_extend_height=True),
            buttons=[
                Button(text="Ano", handler=accept),
                Button(text="Ne", handler=cancel),
            ],
            with_background=True,
        )

        self.root_container.floats.append(Float(content=dialog))
        # Focus a button, e.g., the 'No' button by default
        self.layout.focus(dialog.buttons[1])
        get_app().invalidate()

        return await future

    def toggle_help(self):
        self.show_help = not self.show_help


    def setup_bindings(self):
        kb = self.kb

        # --- GLOBALNI ---
        @kb.add('c-h')
        def _(event): self.toggle_help()

        @kb.add('tab')
        def _(event):
            if self.layout.has_focus(self.file_list_control):
                self.layout.focus(self.command_input)
            else:
                self.layout.focus(self.file_list_control)
        
        @kb.add('end')
        def _(event):
            event.app.exit()

        @kb.add('c-c')
        @kb.add('q')
        def _(event):
            if self.layout.has_focus(self.file_list_control) or event.key_sequence[0].key == 'c-c':
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
        filename = self.files[self.selected_index]
        full_path = os.path.join(self.path, filename)
        
        if filename == "..":
            self.path = os.path.dirname(self.path)
            self.refresh_files()
        elif os.path.isdir(full_path):
            self.path = full_path
            self.refresh_files()
        elif os.path.isfile(full_path):
            if os.access(full_path, os.X_OK) or filename.endswith(('.py', '.sh')):
                cmd = f"python3 '{full_path}'" if filename.endswith('.py') else f"bash '{full_path}'"
                get_app().create_background_task(self.run_script_async(cmd))
            else:
                run_in_terminal(lambda: os.system(f"nano '{full_path}'"))

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
