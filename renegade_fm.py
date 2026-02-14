import curses
import os
import shutil
import subprocess
import sys

# Konfigurace barev a klaves
KEY_ENTER = 10
KEY_ESC = 27
CTRL_E = 5
CTRL_X = 24

class RenegadeFM:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.current_path = os.getcwd()
        self.files = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.clipboard = []  # Seznam cest k souborum pro presun
        self.message = ""
        
        # Nastaveni curses
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Slozky
        curses.init_pair(2, curses.COLOR_WHITE, -1)  # Soubory
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Vyber
        curses.init_pair(4, curses.COLOR_RED, -1)    # Schranka (Cut)
        curses.init_pair(5, curses.COLOR_YELLOW, -1) # Zpravy

        self.refresh_files()
        self.main_loop()

    def refresh_files(self):
        try:
            self.files = sorted(os.listdir(self.current_path))
            self.files.insert(0, "..")
        except PermissionError:
            self.files = [".."]
            self.message = "Pristup odepren!"
        self.selected_index = 0
        self.scroll_offset = 0

    def draw_help_panel(self, max_y, max_x, left_width):
        help_win = curses.newwin(max_y, max_x - left_width, 0, left_width)
        help_win.box()
        help_win.addstr(1, 2, "RENEGADE FM", curses.A_BOLD)
        
        keys = [
            ("Enter", "Otevrit/Spustit"),
            ("e", "Editovat (nano)"),
            ("Ctrl+e", "Prejmenovat"),
            ("r", "Smazat"),
            ("m", "Nova slozka"),
            ("n", "Novy soubor"),
            ("x", "Vyjmout (Cut)"),
            ("Ctrl+x", "Vyjmout (+dalsi)"),
            ("v", "Vlozit (Paste)"),
            ("q", "Ukoncit")
        ]
        
        for idx, (key, desc) in enumerate(keys):
            if 3 + idx < max_y - 1:
                help_win.addstr(3 + idx, 2, f"{key:8} : {desc}")
        
        # Zobrazeni stavu schranky
        if self.clipboard:
            help_win.addstr(max_y - 4, 2, f"Schranka: {len(self.clipboard)} pol.", curses.color_pair(4))
            
        help_win.refresh()

    def draw_main_panel(self, max_y, left_width):
        self.stdscr.clear()
        
        # Cesta nahore
        self.stdscr.addstr(0, 0, f" PATH: {self.current_path} ", curses.A_REVERSE)
        
        # Zpravy
        if self.message:
            self.stdscr.addstr(max_y - 1, 0, f" MSG: {self.message} ", curses.color_pair(5))
            self.message = "" # Reset zpravy po zobrazeni

        # Vypocet viditelne oblasti
        display_h = max_y - 2
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
                style = curses.color_pair(4)

            # Pokud je vybran kurzorem
            if file_idx == self.selected_index:
                style = curses.color_pair(3)

            # Vykresleni
            try:
                self.stdscr.addstr(idx + 1, 1, filename[:left_width-2], style)
            except curses.error:
                pass

    def prompt_user(self, prompt_text):
        curses.echo()
        curses.curs_set(1)
        self.stdscr.addstr(self.stdscr.getmaxyx()[0]-1, 0, prompt_text)
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
            # Spustit
            curses.endwin()
            os.system(f"'{full_path}'")
            # Cekani po spusteni, aby uzivateli nezmizel vystup
            input("
Stiskni Enter pro navrat...")
            curses.doupdate()
        else:
            # Editovat nebo otevrit
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
                os.rename(os.path.join(self.current_path, target), os.path.join(self.current_path, new_name))
                self.refresh_files()
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
            except Exception as e:
                self.message = str(e)

    def action_new_folder(self):
        name = self.prompt_user("Nazev slozky: ")
        if name:
            try:
                os.mkdir(os.path.join(self.current_path, name))
                self.refresh_files()
            except Exception as e:
                self.message = str(e)

    def action_new_file(self):
        name = self.prompt_user("Nazev souboru: ")
        if name:
            full_path = os.path.join(self.current_path, name)
            try:
                open(full_path, 'a').close() # touch
                curses.endwin()
                os.system(f"nano '{full_path}'")
                self.refresh_files()
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
            self.message = f"Vybreno {len(self.clipboard)} pol."
        else:
            self.clipboard.remove(full_path) # Toggle pri multiselect
    
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
        self.message = f"Presunuto {success_count} polozek."

    def main_loop(self):
        while True:
            max_y, max_x = self.stdscr.getmaxyx()
            left_width = int(max_x * 0.70)
            
            self.draw_main_panel(max_y, left_width)
            self.draw_help_panel(max_y, max_x, left_width)

            key = self.stdscr.getch()

            if key == curses.KEY_UP:
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

if __name__ == "__main__":
    curses.wrapper(RenegadeFM)
