# 📂 RenegadeFM Ultimate

**RenegadeFM** je ultra-moderní, transparentní a plně vybavený správce souborů pro terminál (TUI), navržený speciálně pro **Termux** a Linux prostředí. Je postaven na **Prompt Toolkit**, což zaručuje stabilitu, nulové blikání a moderní vzhled.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Termux](https://img.shields.io/badge/Platform-Termux%20%7C%20Linux-orange.svg)

---

## ✨ Klíčové Vlastnosti

### 🖥️ Moderní UI
- **Dvousloupcový layout**: Vlevo seznam souborů, vpravo **živý náhled** (obsah složek, text souborů).
- **Split-Screen Terminál**: Ve spodní části obrazovky běží integrovaný terminál/log, kde vidíš výstupy spouštěných skriptů v reálném čase.
- **Transparentní Design**: Průhledné pozadí, které respektuje tvůj wallpaper v Termuxu.
- **Žádné blikání**: Díky Prompt Toolkit je vykreslování naprosto plynulé.

### 🚀 Funkce
- **Multi-Select**: Označ více souborů pro kopírování (`c`) nebo přesun (`x`).
- **ZIP Archivace**: Označ soubory klávesou `z` a sbal je do zipu klávesou `Ctrl+z`.
- **Rychlé Aliasy**: Stiskni `PgUp` na souboru a okamžitě vytvoř alias do `.bashrc`!
- **Integrovaný CMD**: Přepni se `Tab` do příkazové řádky a spouštěj `git`, `pkg`, `pip` příkazy přímo ze správce.
- **Spouštění skriptů**: Stačí `Enter` na `.py` nebo `.sh` souboru – spustí se asynchronně na pozadí a výstup vidíš dole.
- **Editor**: Vestavěná integrace s `nano` pro rychlé úpravy.

---

## ⌨️ Klávesové Zkratky

| Klávesa | Akce |
|---------|------|
| **Navigace** | |
| `↑` / `↓` | Pohyb v seznamu |
| `←` / `→` | Zpět (..) / Otevřít složku |
| `Home` | Skok do domovské složky (`~`) |
| `End` | Ukončit aplikaci |
| `Tab` | Přepnout mezi soubory a příkazovým řádkem |
| **Akce** | |
| `Enter` | Otevřít složku / Spustit skript / Editovat soubor |
| `PgUp` | **Vytvořit Alias** (automaticky přidá do .bashrc) |
| `Ctrl+h` | Zobrazit nápovědu |
| **Editace** | |
| `c` | **Kopírovat** (přidat do výběru) |
| `x` | **Vyjmout** (přidat do výběru) |
| `v` | **Vložit** (provést akci) |
| `z` | **Označit k zabalení** (přidat do ZIP výběru) |
| `Ctrl+z` | **Zabalit do ZIP** (vytvoří archiv ze označených souborů) |
| `Ctrl+r` | **Označit k smazání** |
| `r` | **Smazat** (potvrzení dialogem) |
| `Ctrl+e` | **Přejmenovat** |
| `n` | Nový soubor |
| `m` | Nová složka |
| `e` | Editovat v Nano |

---

## 📦 Instalace

### Požadavky
- Python 3.8+
- Knihovna `prompt_toolkit`

### Rychlý Start (Termux)

1. **Naklonuj repozitář:**
   ```bash
   git clone https://github.com/zombiegirlcz/Fil-manager.git
   cd Fil-manager
   ```

2. **Nainstaluj závislosti:**
   ```bash
   bash install.sh
   # nebo: pip install -r requirements.txt
   ```

3. **Spusť:**
   ```bash
   python3 file_manage.py
   ```

4. **(Volitelné) Vytvoř si alias:**
   ```bash
   echo "alias fm='python3 ~/Fil-manager/file_manage.py'" >> ~/.bashrc
   source ~/.bashrc
   ```
   Nyní stačí napsat `fm`!

---

## 🛠️ Pokročilé Použití

### Vytváření Aliasů (`PgUp`)
RenegadeFM umí automaticky detekovat typ souboru a vytvořit správný alias.
1. Najeď na `script.py`.
2. Stiskni `PgUp`.
3. Zadej název (např. `muj_skript`).
4. Hotovo! Nyní můžeš v terminálu psát `muj_skript` a spustí se to.

### Integrovaný Terminál
Potřebuješ rychle nainstalovat balíček? Nemusíš ukončovat správce.
1. Stiskni `Tab` -> kurzor skočí dolů do `CMD >`.
2. Napiš `pkg install git`.
3. Sleduj výstup v logu nad tím.

---

## 🐛 Řešení Problémů

- **Nefungují barvy?** Ujisti se, že tvůj terminál podporuje 256 barev (Termux to umí defaultně).
- **Chyba `cbreak`?** Tato verze (Ultimate) nepoužívá `curses`, takže by se tato chyba neměla nikdy objevit.

## 🔁 Zachování aktuálního adresáře (Termux)

Aby po ukončení správce zůstalo aktuální pracovní adresář v původním shellu, přidej do svého `~/.bashrc` (nebo `~/.zshrc`) jednoduchou funkci:

```bash
fm() {
  python3 ~/Fil-manager/file_manage.py
  local last_path
  last_path=$(cat ~/.renegadefm_last_path 2>/dev/null)
  if [[ -n $last_path && -d $last_path ]]; then
    cd "$last_path"
  fi
}
```

Po spuštění `source ~/.bashrc` a použití `fm` se po ukončení správce vrátíš zpět do složky, ve které jsi naposledy pracoval. Pokud potřebuješ spustit renagent, stačí napsat `fm`.

---

**Autor:** zombiegirlcz  
**Licence:** MIT
