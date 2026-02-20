# 📁 Fil-Manager - Terminal File Manager

Elegantní a intuitivní správce souborů pro terminál s moderním TUI rozhraním postaveným na **curses**.

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## ✨ Vlastnosti

### 🎨 Moderní TUI Rozhraní
- **Příkazový řádek** na vrcholu pro spouštění externích příkazů (TAB pro přepnutí)
- **Třídílný layout**:
  - 📝 Levá strana: Informace o cestě a vybraném souboru
  - 📂 Horní pravá: Obsah aktuální složky s barevným zvýrazněním
  - ❓ Dolní pravá: Stálá nápověda s klávesovými zkratkami

### 📋 Správa Souborů
- ✅ Procházení adresářů (↑/↓ navigace)
- ✅ Otevírání souborů (Enter)
- ✅ Spouštění skriptů
- ✅ Vytváření nových souborů a složek
- ✅ Přejmenování (Ctrl+E)
- ✅ Mazání souborů a složek (R)
- ✅ Vyjímání a vkládání (X/Ctrl+X/V) - multi-select

### 🎯 Speciální Funkce
- 🔧 Vestavěný editor (Nano) pro editaci textových souborů
- 🖥️ Spouštění vlastních příkazů přes command bar
- 📌 Multi-select vyjímání (Ctrl+X)
- 🎨 Barevné zvýrazňování souborů a složek
- 📊 Zobrazování informací o souborech (velikost, počet položek ve složce)
- 💾 Zůstane v poslední otevřené složce po ukončení

## 🚀 Instalace

### Požadavky
- Python 3.7+
- Terminál s podporou ANSI barev
- Nano (doporučeno pro editaci)

### Rychlá instalace
```bash
# Klonuj repozitář
git clone https://github.com/zombiegirlcz/Fil-manager.git
cd Fil-manager

# Spusť správce
python3 file_manage.py
```

### Alias (doporučeno)
Přidej do svého `~/.bashrc`:
```bash
alias fm='python3 ~/file_manage.py'
```

Pak spusť:
```bash
source ~/.bashrc
fm
```

## ⌨️ Klávesové Zkratky

| Klávesa | Funkce |
|---------|--------|
| ↑/↓ | Navigace v seznamu |
| Enter | Otevřít soubor/složku |
| Tab | Přepnout na command bar / zpět |
| E | Editovat soubor (Nano) |
| Ctrl+E | Přejmenovat soubor |
| R | Smazat soubor/složku |
| M | Nová složka |
| N | Nový soubor |
| X | Vyjmout (Cut) |
| Ctrl+X | Vybrat více (Multi-select) |
| V | Vložit (Paste) |
| Q | Ukončit |
| C | Vyčistit zprávu |

## 🎮 Příkazový Řádek

Stiskni **Tab** pro přepnutí na command bar:
```
> ls -la
> mkdir test
> python3 script.py
> chmod +x program
```

Spusť příkaz **Enter** a vrátí se automaticky do správce souborů.

## 📦 Architektura

```
file_manage.py
├── RenegadeFM
│   ├── __init__()              # Inicializace
│   ├── draw_command_bar()      # Příkazový řádek
│   ├── draw_left_panel()       # Informační panel
│   ├── draw_files_panel()      # Seznam souborů
│   ├── draw_help_panel()       # Nápověda
│   ├── action_*()              # Akce (cut, paste, delete...)
│   └── main_loop()             # Hlavní smyčka
```

## 🎨 Barevné Schéma

- 🟢 **Zelená**: Složky
- ⚪ **Bílá**: Soubory
- 🔵 **Cyan**: Vybraný prvek
- 🔴 **Červená**: Položky ve schránce (Cut)
- 🟡 **Žlutá**: Zprávy a informace

## 💡 Tipy a Triky

### Hromadné operace
```
1. Stiskni X na prvním souboru
2. Stiskni ↓↓↓ pro navigaci
3. Stiskni Ctrl+X na dalších souborech
4. Stiskni V pro vložení všech najednou
```

### Spouštění skriptů
```
1. Naviguj na skript
2. Stiskni Enter (a skript se spustí)
3. Výstup se zobrazí v terminálu
```

### Práce s editorem
- Klikni na soubor a stiskni **E** pro editaci
- Nebo stiskni **Enter** na textovém souboru
- Změny se automaticky uloží v Nanu

## 🐛 Známé Problémy

- V některých terminálu může být klávesa Delete reprezentována jako klávesa Backspace
- SSH terminály mohou mít problémy s barevným výstupem

## 🤝 Přispívání

Máš nápad na vylepšení? 
```bash
git checkout -b feature/tvoje-funkcionalita
git commit -am "Přidej novou funkcionalitu"
git push origin feature/tvoje-funkcionalita
```

## 📝 Autor

**zombiegirlcz** 🧟‍♀️

## 📄 Licence

MIT License - vidíš detaily v souboru LICENSE

---

**Užívej si správu souborů v terminálu!** 🚀

Made with ❤️ for terminal enthusiasts
