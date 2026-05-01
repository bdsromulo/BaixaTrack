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

O script baixa o instalador oficial mais recente do GitHub Releases e abre o assistente de instalação, onde você pode escolher a pasta de instalação, decidir se quer um atalho na Área de Trabalho e executar o app ao terminar. Caso ainda não exista release publicada, o script faz fallback para uma instalação via Python (sem janela de console).

> O **FFmpeg** (motor de conversão de áudio) é baixado automaticamente na primeira execução do app — nenhuma instalação manual necessária.

---

## ⚠️ Aviso do SmartScreen do Windows

Como o instalador não é assinado com certificado de code signing (custo anual de centenas de dólares), o Windows pode exibir uma tela azul **"O Windows protegeu seu computador"** na primeira execução.

Para prosseguir:

1. Clique em **"Mais informações"** na parte inferior do aviso
2. Clique em **"Executar mesmo assim"**

Isso só acontece na primeira vez. Não é um erro nem indício de malware — é o comportamento padrão do SmartScreen para qualquer executável sem reputação registrada na Microsoft. O código-fonte completo está aberto neste repositório.

---

## 🏗️ Arquitetura do projeto

```
BaixaTrack/
├── app.py                         # Interface gráfica principal
├── downloader.py                  # Módulo de extração e download de áudio
├── ffmpeg_manager.py              # Gerenciamento e auto-download do FFmpeg
├── requirements.txt               # Dependências do projeto
├── build.bat                      # Script de compilação (PyInstaller + Inno Setup)
├── installer.iss                  # Script Inno Setup que gera o BaixaTrack-Setup.exe
├── install.ps1                    # Instalador PowerShell one-liner
├── install.bat                    # Instalador batch alternativo
├── assets/
│   ├── logo.png                   # Logo original
│   └── logo.ico                   # Ícone multi-resolução (gerado pelo build)
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

## 📦 Gerar executável `.exe` e instalador

```bash
build.bat
```

Gera dois artefatos:

| Artefato | Caminho | Descrição |
|---|---|---|
| **Pasta portátil** | `dist\BaixaTrack\` | App empacotado com todas as dependências (executar `BaixaTrack.exe`) |
| **Instalador** | `dist\BaixaTrack-Setup.exe` | Instalador gráfico com escolha de pasta, atalho opcional, executar ao final e desinstalador no Painel de Controle |

> Para gerar o instalador é preciso ter o **Inno Setup 6** instalado (`winget install JRSoftware.InnoSetup`). Sem ele, o `build.bat` ainda gera a pasta portátil normalmente.

### Build e release automáticos (GitHub Actions)

Ao fazer push de uma tag de versão, o pipeline compila o executável, monta o instalador via Inno Setup e publica ambos como GitHub Release:

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
