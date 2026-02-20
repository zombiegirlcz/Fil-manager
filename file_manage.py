import curses
import os
import shutil
import subprocess
import sys

# Konfigurace barev a klaves
KEY_ENTER = 10
KEY_ESC = 27
KEY_TAB = 9
CTRL_E = 5
CTRL_X = 24

class RenegadeFM:
    last_path = os.getcwd()  # Pamatuje si poslední cestu
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.current_path = os.getcwd()
        self.files = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.clipboard = []
        self.message = ""
        self.command_buffer = ""
        self.active_panel = "files"  # "files" nebo "command"
        
        # Nastaveni curses
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)      # Slozky
        curses.init_pair(2, curses.COLOR_WHITE, -1)      # Soubory
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Vyber
        curses.init_pair(4, curses.COLOR_RED, -1)        # Schranka
        curses.init_pair(5, curses.COLOR_YELLOW, -1)     # Zpravy
        curses.init_pair(6, curses.COLOR_CYAN, -1)       # Info/highlight
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Command bar

        self.refresh_files()
        self.main_loop()

    def refresh_files(self):
        RenegadeFM.last_path = self.current_path  # Pamatuj si cestu
        try:
            self.files = sorted(os.listdir(self.current_path))
            self.files.insert(0, "..")
        except PermissionError:
            self.files = [".."]
            self.message = "Pristup odepren!"
        self.selected_index = 0
        self.scroll_offset = 0

    def draw_command_bar(self, max_y, max_x):
        """Prikazovy radek na vrcholu"""
        bar_height = 2
        bar_win = curses.newwin(bar_height, max_x, 0, 0)
        
        if self.active_panel == "command":
            bar_win.addstr(0, 0, " > ", curses.color_pair(6) | curses.A_BOLD)
            bar_win.addstr(0, 3, self.command_buffer[:max_x-5], curses.color_pair(7))
            curses.curs_set(1)
        else:
            bar_win.addstr(0, 0, " > ", curses.color_pair(6) | curses.A_BOLD)
            bar_win.addstr(0, 3, self.command_buffer[:max_x-5], curses.color_pair(7))
            curses.curs_set(0)
        
        # Info line
        if self.active_panel == "command":
            info = "[TAB] Zpet na soubory | [Enter] Spustit prikaz | [Esc] Zrusit"
        else:
            info = "[TAB] Prikazovy radek | [Arrows] Navigace | [q] Ukoncit"
        
        bar_win.addstr(1, 0, info[:max_x], curses.color_pair(6))
        bar_win.clrtoeol()
        bar_win.refresh()
        
        return bar_height

    def draw_help_panel(self, max_y, max_x, left_width, top_offset):
        """Nápověda na dolní pravé straně"""
        help_h = max_y - top_offset - 3  # Prostor pro nápovědu
        
        if help_h < 5:
            return
        
        help_win = curses.newwin(help_h, max_x - left_width, 
                                 max_y - help_h + 2, left_width)
        help_win.box()
        help_win.addstr(0, 2, " NAPOVEDA ", curses.color_pair(6) | curses.A_BOLD)
        
        keys = [
            ("↑/↓", "Navigace"),
            ("Enter", "Otevrit"),
            ("e", "Editovat (nano)"),
            ("Ctrl+e", "Prejmenovat"),
            ("r", "Smazat"),
            ("m", "Nova slozka"),
            ("n", "Novy soubor"),
            ("x", "Vyjmout"),
            ("Ctrl+x", "Vybrat vice"),
            ("v", "Vlozit"),
            ("Tab", "Prikazy"),
            ("q", "Ukoncit"),
        ]
        
        row = 1
        for key, desc in keys:
            if row < help_h - 1:
                try:
                    help_win.addstr(row, 2, f"{key:8} {desc}", curses.color_pair(2))
                except:
                    pass
                row += 1
        
        # Stav schranky
        if self.clipboard:
            try:
                help_win.addstr(help_h - 2, 2, f"Schranka: {len(self.clipboard)}", 
                              curses.color_pair(4) | curses.A_BOLD)
            except:
                pass
        
        help_win.refresh()

    def draw_files_panel(self, max_y, max_x, left_width, top_offset):
        """Soubory na pravé straně"""
        content_h = max_y - top_offset - 3
        
        if content_h < 2:
            return
        
        files_win = curses.newwin(content_h, max_x - left_width,
                                  top_offset, left_width)
        files_win.box()
        
        # Titulka
        title = f" {os.path.basename(self.current_path) or '/'} "
        files_win.addstr(0, 2, title, curses.color_pair(6) | curses.A_BOLD)
        
        # Vypocet viditelne oblasti
        display_h = content_h - 2
        if self.selected_index >= self.scroll_offset + display_h:
            self.scroll_offset = self.selected_index - display_h + 1
        elif self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index

        for idx in range(display_h):
            file_idx = idx + self.scroll_offset
            if file_idx >= len(self.files):
                break
                
            filename = self.files[file_idx]
            full_path = os.path.join(self.current_path, filename)
            
            # Styl radku
            style = curses.color_pair(2)
            if os.path.isdir(full_path):
                style = curses.color_pair(1) | curses.A_BOLD
            
            # Pokud je ve schrance
            if full_path in self.clipboard:
                style = curses.color_pair(4) | curses.A_DIM
            
            # Pokud je vybran kurzorem
            if file_idx == self.selected_index:
                style = curses.color_pair(3) | curses.A_BOLD

            # Vykresleni
            try:
                display_name = filename
                if filename == "..":
                    display_name = ".. (Parent)"
                elif os.path.isdir(full_path):
                    display_name = f"[{filename}]"
                
                files_win.addstr(idx + 1, 2, display_name[:max_x - left_width - 5], style)
            except curses.error:
                pass

        files_win.refresh()

    def draw_left_panel(self, max_y, max_x, left_width, top_offset):
        """Levá strana - budoucí rozšíření (zatím prázdná)"""
        left_h = max_y - top_offset - 3
        
        if left_h < 2:
            return
        
        left_win = curses.newwin(left_h, left_width,
                                 top_offset, 0)
        left_win.box()
        left_win.addstr(0, 2, " INFO ", curses.color_pair(6) | curses.A_BOLD)
        
        # Cesta
        try:
            left_win.addstr(2, 2, "Cesta:", curses.A_BOLD)
            left_win.addstr(3, 2, self.current_path[:left_width-4], curses.color_pair(2))
        except:
            pass
        
        # Info o souboru
        if 0 <= self.selected_index < len(self.files):
            target = self.files[self.selected_index]
            if target != "..":
                full_path = os.path.join(self.current_path, target)
                try:
                    left_win.addstr(5, 2, "Soubor:", curses.A_BOLD)
                    left_win.addstr(6, 2, target[:left_width-4], curses.color_pair(2))
                    
                    if os.path.isfile(full_path):
                        size = os.path.getsize(full_path)
                        left_win.addstr(7, 2, f"Velikost: {size} B", curses.color_pair(6))
                    elif os.path.isdir(full_path):
                        items = len(os.listdir(full_path))
                        left_win.addstr(7, 2, f"Polozek: {items}", curses.color_pair(6))
                except:
                    pass
        
        left_win.refresh()

    def draw_message_bar(self, max_y, max_x):
        """Zpravy na spodu"""
        if self.message:
            try:
                self.stdscr.addstr(max_y - 1, 0, f" {self.message} ", 
                                 curses.color_pair(5) | curses.A_BOLD)
                self.stdscr.clrtoeol()
            except:
                pass

    def draw_screen(self):
        self.stdscr.clear()
        max_y, max_x = self.stdscr.getmaxyx()
        
        # Prikazovy radek
        top_offset = self.draw_command_bar(max_y, max_x)
        
        # Vypocet sirky levej stranky
        left_width = int(max_x * 0.35)
        
        # Vykresli panely
        self.draw_left_panel(max_y, max_x, left_width, top_offset)
        self.draw_files_panel(max_y, max_x, left_width, top_offset)
        self.draw_help_panel(max_y, max_x, left_width, top_offset)
        
        # Zpravy
        self.draw_message_bar(max_y, max_x)
        
        self.stdscr.refresh()

    def execute_command(self, command):
        """Spustí příkaz z command baru"""
        if not command.strip():
            return
        
        try:
            curses.endwin()
            result = subprocess.run(command, shell=True, capture_output=False)
            input("\nStiskni Enter pro navrat...")
            curses.doupdate()
            self.message = f"Prikaz proveden (exit: {result.returncode})"
            self.refresh_files()
        except Exception as e:
            self.message = f"Chyba: {str(e)}"

    def prompt_user(self, prompt_text):
        curses.echo()
        curses.curs_set(1)
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.addstr(max_y - 1, 0, prompt_text)
        self.stdscr.clrtoeol()
        input_bytes = self.stdscr.getstr()
        curses.noecho()
        curses.curs_set(0)
        return input_bytes.decode('utf-8')

    def action_enter(self):
        target = self.files[self.selected_index]
        full_path = os.path.join(self.current_path, target)
        
        if target == "..":
            self.current_path = os.path.dirname(self.current_path)
            self.refresh_files()
        elif os.path.isdir(full_path):
            self.current_path = full_path
            self.refresh_files()
        elif os.access(full_path, os.X_OK):
            curses.endwin()
            os.system(f"'{full_path}'")
            input("Stiskni Enter pro navrat...")
            curses.doupdate()
        else:
            self.action_edit()

    def action_edit(self):
        target = self.files[self.selected_index]
        if target == "..": return
        full_path = os.path.join(self.current_path, target)
        curses.endwin()
        os.system(f"nano '{full_path}'")

    def action_rename(self):
        target = self.files[self.selected_index]
        if target == "..": return
        new_name = self.prompt_user(f"Rename '{target}' to: ")
        if new_name:
            try:
                os.rename(os.path.join(self.current_path, target), 
                         os.path.join(self.current_path, new_name))
                self.refresh_files()
                self.message = f"Prejmenovno na '{new_name}'"
            except Exception as e:
                self.message = str(e)

    def action_delete(self):
        target = self.files[self.selected_index]
        if target == "..": return
        confirm = self.prompt_user(f"Smazat '{target}'? (y/n): ")
        if confirm.lower() == 'y':
            full_path = os.path.join(self.current_path, target)
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
                self.refresh_files()
                self.message = f"Smazano: {target}"
            except Exception as e:
                self.message = str(e)

    def action_new_folder(self):
        name = self.prompt_user("Nazev slozky: ")
        if name:
            try:
                os.mkdir(os.path.join(self.current_path, name))
                self.refresh_files()
                self.message = f"Slozka vytvorena: {name}"
            except Exception as e:
                self.message = str(e)

    def action_new_file(self):
        name = self.prompt_user("Nazev souboru: ")
        if name:
            full_path = os.path.join(self.current_path, name)
            try:
                open(full_path, 'a').close()
                curses.endwin()
                os.system(f"nano '{full_path}'")
                self.refresh_files()
                self.message = f"Soubor vytvoreny: {name}"
            except Exception as e:
                self.message = str(e)

    def action_cut(self, append=False):
        target = self.files[self.selected_index]
        if target == "..": return
        full_path = os.path.join(self.current_path, target)
        
        if not append:
            self.clipboard = []
        
        if full_path not in self.clipboard:
            self.clipboard.append(full_path)
            self.message = f"Vybrrano: {len(self.clipboard)} polozek"
        else:
            self.clipboard.remove(full_path)
            self.message = f"Zruseno: {len(self.clipboard)} polozek zbyva"
    
    def action_paste(self):
        if not self.clipboard:
            self.message = "Schranka je prazdna"
            return
            
        success_count = 0
        for src in self.clipboard:
            try:
                if os.path.exists(src):
                    dst = os.path.join(self.current_path, os.path.basename(src))
                    shutil.move(src, dst)
                    success_count += 1
            except Exception as e:
                self.message = f"Chyba: {str(e)}"
        
        self.clipboard = []
        self.refresh_files()
        self.message = f"Presunuto {success_count} polozek"

    def main_loop(self):
        while True:
            self.draw_screen()

            key = self.stdscr.getch()

            if self.active_panel == "command":
                # Prikazovy radek je aktivni
                if key == KEY_TAB:
                    self.active_panel = "files"
                    self.command_buffer = ""
                elif key == KEY_ESC:
                    self.active_panel = "files"
                    self.command_buffer = ""
                    self.message = "Prikaz zrusen"
                elif key == KEY_ENTER:
                    self.active_panel = "files"
                    self.execute_command(self.command_buffer)
                    self.command_buffer = ""
                elif key == curses.KEY_BACKSPACE or key == 127:
                    self.command_buffer = self.command_buffer[:-1]
                elif 32 <= key <= 126:  # Tisknutelne znaky
                    self.command_buffer += chr(key)
            else:
                # Soubory jsou aktivni
                if key == KEY_TAB:
                    self.active_panel = "command"
                    self.command_buffer = ""
                elif key == curses.KEY_UP:
                    if self.selected_index > 0:
                        self.selected_index -= 1
                elif key == curses.KEY_DOWN:
                    if self.selected_index < len(self.files) - 1:
                        self.selected_index += 1
                elif key == KEY_ENTER:
                    self.action_enter()
                elif key == ord('e'):
                    self.action_edit()
                elif key == CTRL_E:
                    self.action_rename()
                elif key == ord('r'):
                    self.action_delete()
                elif key == ord('m'):
                    self.action_new_folder()
                elif key == ord('n'):
                    self.action_new_file()
                elif key == ord('x'):
                    self.action_cut(append=False)
                elif key == CTRL_X:
                    self.action_cut(append=True)
                elif key == ord('v'):
                    self.action_paste()
                elif key == ord('q'):
                    break
                elif key == ord('c'):
                    # Clear message
                    self.message = ""

if __name__ == "__main__":
    try:
        curses.wrapper(RenegadeFM)
    finally:
        # Po ukonceni spravce zmeni shell do posledni otevrene slozky
        os.chdir(RenegadeFM.last_path if hasattr(RenegadeFM, 'last_path') else os.getcwd())
