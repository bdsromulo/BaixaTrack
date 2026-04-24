<div align="center">

# 🎵 BaixaTrack

### *Conecta a música do seu streaming de vídeo do SeuTubo pro seu aparelinho MP3*

[![Release](https://img.shields.io/github/v/release/bdsromulo/BaixaTrack?style=flat-square&color=ef4444)](https://github.com/bdsromulo/BaixaTrack/releases)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows)](https://github.com/bdsromulo/BaixaTrack/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

</div>

---

**BaixaTrack** é um aplicativo desktop para Windows com interface gráfica moderna que converte faixas de playlists de streaming de vídeo em arquivos de áudio MP3 — perfeito para quem quer ouvir sua música favorita offline, no carro, no mp3 player, ou em qualquer lugar que não dependa de internet.

Cole um link, veja a lista de músicas, selecione o que quiser e pronto. Simples assim.

---

## ⚡ Instalação em um comando

Abra o **PowerShell** e execute:

```powershell
irm https://raw.githubusercontent.com/bdsromulo/BaixaTrack/main/install.ps1 | iex
```

O script detecta automaticamente se há uma versão compilada disponível e, caso haja, instala o executável diretamente. Se não, faz a instalação via Python. Em ambos os casos, um atalho é criado na sua Área de Trabalho.

> O **FFmpeg** (motor de conversão de áudio) é baixado automaticamente na primeira execução do app — nenhuma instalação manual necessária.

---

## 🏗️ Arquitetura do projeto

```
BaixaTrack/
├── app.py                         # Interface gráfica principal
├── downloader.py                  # Módulo de extração e download de áudio
├── ffmpeg_manager.py              # Gerenciamento e auto-download do FFmpeg
├── requirements.txt               # Dependências do projeto
├── build.bat                      # Script de compilação para Windows
├── install.ps1                    # Instalador PowerShell one-liner
├── install.bat                    # Instalador batch alternativo
└── .github/
    └── workflows/
        └── release.yml            # Pipeline CI/CD para build automático
```

### Camadas da aplicação

```
┌──────────────────────────────────────────────────┐
│              app.py  (View / Controller)          │
│   customtkinter · tkinter · threading · Pillow    │
├──────────────────────────────────────────────────┤
│           downloader.py  (Download Engine)        │
│             yt-dlp · ffmpeg_manager               │
├──────────────────────────────────────────────────┤
│         ffmpeg_manager.py  (FFmpeg Layer)         │
│          detecção de PATH · download auto         │
└──────────────────────────────────────────────────┘
```

---

## 📦 Bibliotecas utilizadas

| Biblioteca | Papel no projeto |
|---|---|
| [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Motor principal: extrai metadados (título, duração, thumbnail) e faz o download do stream de áudio em alta qualidade |
| [`customtkinter`](https://github.com/TomSchimansky/CustomTkinter) | Widgets modernos sobre o `tkinter` nativo — responsável pela interface dark mode, botões, barras de progresso e scrollable frames |
| [`Pillow`](https://python-pillow.org/) | Carrega e redimensiona thumbnails das faixas para exibir na interface |
| [`requests`](https://requests.readthedocs.io/) | Requisições HTTP para buscar as miniaturas dos vídeos |
| [`tkinter`](https://docs.python.org/3/library/tkinter.html) | Base da janela principal, file dialog e messageboxes (incluído no Python) |
| [`threading`](https://docs.python.org/3/library/threading.html) | Mantém a interface responsiva durante downloads — cada operação pesada roda em thread separada |
| [`yt-dlp + FFmpeg`](https://ffmpeg.org/) | Juntos fazem a extração e conversão: o yt-dlp baixa o stream de áudio e o FFmpeg converte para MP3 192kbps |

---

## 🖥️ Como usar o app

1. **Abra o BaixaTrack** pelo atalho da Área de Trabalho
2. **Cole o link** de um vídeo ou playlist no campo de URL
3. Clique em **Buscar** — o app busca título, duração e thumbnail de cada faixa
4. **Selecione** as faixas individualmente (ou use "Selecionar Todos")
5. Escolha a **pasta de destino** clicando no ícone 📁
6. Clique em **⬇ Baixar MP3** e acompanhe o progresso faixa a faixa
7. Ao finalizar, clique em **Abrir Pasta** para acessar seus arquivos

---

## 🔧 Instalação manual (desenvolvedores)

### Pré-requisitos
- Python 3.8 ou superior ([python.org](https://www.python.org/downloads/) — marque **"Add Python to PATH"**)

```bash
git clone https://github.com/bdsromulo/BaixaTrack.git
cd BaixaTrack
pip install -r requirements.txt
python app.py
```

> O FFmpeg é detectado automaticamente. Se não estiver no PATH, o app oferece baixá-lo na primeira execução.

---

## 📦 Gerar executável `.exe`

```bash
build.bat
```

Gera `dist\YouTube MP3 Extractor\YouTube MP3 Extractor.exe` com todas as dependências empacotadas.

### Build e release automáticos (GitHub Actions)

Ao fazer push de uma tag de versão, o pipeline compila o executável e publica como GitHub Release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## ✨ Funcionalidades

- 🎵 Suporte a faixas únicas ou playlists completas
- ✅ Seleção individual de faixas dentro de uma playlist
- 📊 Barra de progresso por faixa + velocidade de download + ETA
- 🖼️ Exibição de thumbnail, título e duração antes do download
- 🔴 Interface dark mode com tema moderno
- 📁 Escolha livre da pasta de destino
- 🔧 Download automático do FFmpeg na primeira execução
- 🧵 Interface 100% responsiva — downloads rodam em background

---

## 📄 Licença

MIT © [bdsromulo](https://github.com/bdsromulo)
