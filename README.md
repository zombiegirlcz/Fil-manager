# 📂 RenegadeFM Ultimate

**RenegadeFM** je ultra-moderní, transparentní a plně vybavený správce souborů pro terminál (TUI), navržený speciálně pro **Termux** a Linux prostředí. Je postaven na **Prompt Toolkit**, což zaručuje stabilitu, nulové blikání a moderní vzhled.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Termux](https://img.shields.io/badge/Platform-Termux%20%7C%20Linux-orange.svg)

---

## ✨ Klíčové Vlastnosti

### 🖥️ Moderní UI
- **Dvousloupcový layout**: Vlevo seznam souborů, vpravo **živý náhled** (obsah složek, text souborů).
- **Persistentní Terminál**: Ve spodní části obrazovky běží reálná relace `bash`, která automaticky sleduje tvou polohu v manažeru.
- **Full-screen Režim**: Pomocí `Ctrl+T` přepni terminál na celou obrazovku pro pohodlnou práci v shellu.
- **Transparentní Design**: Průhledné pozadí, které respektuje tvůj wallpaper v Termuxu.

### 🚀 Funkce
- **Multi-Select**: Označ více souborů pro kopírování (`c`) nebo přesun (`x`).
- **TAR Archivace**: Označ soubory klávesou `z` a sbal je do archivu klávesou `Ctrl+z` (podpora `.tar`, `.tar.gz`, `.tar.bz2`).
- **Rozšířené barvy**: Barevné odlišení pro JSON, archivy, obrázky, videa a další.
- **Symbolické odkazy (Symlinky)**: Stiskni `PgUp` pro označení a `v` pro vložení symlinku. `Ctrl+V` umožní vložit symlink s novým názvem.
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
| `Tab` | Přepnout mezi soubory, hledáním a terminálem |
| `Ctrl+T` | **Full-screen Terminál** (ZAP/VYP) |
| **Akce** | |
| `Enter` | Otevřít složku / Spustit skript / Editovat soubor |
| `PgUp` | **Označit pro Symlink** |
| `Ctrl+h` | Zobrazit nápovědu |
| **Editace** | |
| `c` | **Kopírovat** (přidat do výběru) |
| `x` | **Vyjmout** (přidat do výběru) |
| `v` | **Vložit** (provést akci) |
| `z` | **Označit k archivaci** (TAR) |
| `Ctrl+z` | **Vytvořit Archiv** (TAR, GZ, BZ2) |
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

2. **Nainstaluj vše (včetně spouštěče rfm):**
   ```bash
   bash install.sh
   ```

3. **Spusť odkudkoliv:**
   ```bash
   rfm
   ```

---

## 🛠️ Pokročilé Použití

### Vytváření Symlinků (`PgUp`)
RenegadeFM umožňuje snadné vytváření symbolických odkazů:
1. Najeď na soubor/složku a stiskni `PgUp`.
2. Přejdi do cílové složky.
3. Stiskni `v` pro okamžitý symlink nebo `Ctrl+V` pro symlink s vlastním názvem.

### Integrovaný Terminál
Zapomeň na statické logy. Spodní okno je reálná relace tvého oblíbeného shellu.
1. Stiskni `Tab` dokud se kurzor nepřesune do terminálu (nebo použij `Ctrl+T` pro celou obrazovku).
2. Piš příkazy jako v běžném terminálu. Podporujeme doplňování tabulátorem!
3. Manažer automaticky posílá `cd` příkazy na pozadí, takže jsi v terminálu vždy tam, kde jsi v manažeru.

---

## 🐛 Řešení Problémů

- **Nefungují barvy?** Ujisti se, že tvůj terminál podporuje 256 barev (Termux to umí defaultně).
- **Chyba `cbreak`?** Tato verze (Ultimate) nepoužívá `curses`, takže by se tato chyba neměla nikdy objevit.

## 🔁 Zachování adresáře po ukončení

Aby po ukončení správce zůstalo aktuální pracovní adresář v původním shellu, přidej do svého `~/.bashrc` (nebo `~/.zshrc`) tuto funkci:

```bash
rfm() {
  command rfm "$@"
  local last_path
  last_path=$(cat ~/.renegadefm_last_path 2>/dev/null)
  if [[ -n $last_path && -d $last_path ]]; then
    cd "$last_path"
  fi
}
```

---

**Autor:** zombiegirlcz  
**Licence:** MIT
