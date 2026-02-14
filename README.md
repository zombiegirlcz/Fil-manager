# Renegade FM (Fil-manager)

Interaktivní, lehký a nekompromisní souborový manažer pro Termux.

## Vzhled
```text
+-------------------------------------------------------------+
| PATH: /data/data/com.termux/files/home           [RENEGADE] |
+------------------------------------------+------------------+
| ..                                       | RENEGADE FM      |
| [DIR]  ai_coder                          |                  |
| [FILE] renegade_fm.py                    | Enter : Otevrit  |
| [DIR]  storage                           | e     : Nano     |
|                                          | Ctrl+e: Rename   |
|                                          | r     : Smazat   |
|                                          | m     : Slozka   |
|                                          | n     : Soubor   |
|                                          | x     : Vyjmout  |
|                                          | v     : Vlozit   |
|                                          | q     : Konec    |
+------------------------------------------+------------------+
| MSG: Vybreno 1 pol.                                         |
+-------------------------------------------------------------+
```

## Instalace
1. Stáhni skript:
   ```bash
   git clone https://github.com/zombiegirlcz/Fil-manager.git
   cd Fil-manager
   ```
2. (Volitelné) Vytvoř si příkaz `fm`:
   ```bash
   su -c "cp renegade_fm.py /data/data/com.termux/files/usr/bin/fm && chmod +x /data/data/com.termux/files/usr/bin/fm"
   ```

## Ovládání
- **Šipky**: Pohyb v seznamu
- **Enter**: Otevřít složku nebo spustit soubor
- **e**: Editovat v `nano`
- **Ctrl+e**: Přejmenovat
- **r**: Smazat (s potvrzením)
- **m**: Vytvořit novou složku
- **n**: Vytvořit nový soubor a otevřít v `nano`
- **x**: Vyjmout (připravit k přesunu)
- **Ctrl+x**: Přidat další soubor do schránky
- **v**: Vložit (přesunout) vše ze schránky do aktuální složky
- **q**: Ukončit
