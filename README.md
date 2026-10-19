# Shazam-Oliva

Shazam-Oliva é um script em Python que identifica a música transmitida em tempo real na [Rádio Verde Oliva](https://www.socialradio.com.br/radio/verdeolivaresende/) (ou qualquer outra estação hospedada na Social Rádio).

Ao receber a informação, o script anuncia, em voz alta, o nome da música e do intérprete. Também envia uma notificação para a área de trabalho (`kdialog` ou `notify-send`) com a imagem da capa do álbum e para todos os dispositivos pareados no [KDE Connect](https://kdeconnect.kde.org/).

### Recursos e Melhorias

- **Consulta Instantânea via API:** Lê metadados diretamente do CDN Cloudflare da Social Rádio sem precisar carregar navegador ou emulador.
- **Modo Monitor Contínuo (`--watch`):** Monitora a rádio em segundo plano e só anuncia/notifica quando a música realmente mudar.
- **Interface CLI com Parâmetros (`argparse`):** Alterne estações, volume, modo silencioso e intervalos diretamente pelo terminal.
- **Detector de Idioma Otimizado:** Singleton de modelos `lingua` para detecção em milissegundos.
- **Multi-Desktop:** Suporte automático ao `kdialog` (KDE Plasma) com fallback para `notify-send` (GNOME, XFCE, Sway, etc.).
- **Padrão XDG:** Capas em `~/.cache/shazam-oliva/` e registros em `~/.local/state/shazam-oliva/oliva_log.txt`.
- **Áudio Sem Cortes:** Costura de frases de idiomas mistos através do `pydub.AudioSegment`.

---

### Instalação

1. Crie e ative o ambiente virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

---

### Exemplos de Uso

1. **Consulta única (padrão):**
   ```bash
   python main.py
   ```

2. **Modo contínuo (monitorando a cada 15 segundos):**
   ```bash
   python main.py --watch
   ```

3. **Modo contínuo com intervalo customizado (ex: a cada 10s):**
   ```bash
   python main.py --watch --interval 10
   ```

4. **Consultar outra rádio da Social Rádio:**
   ```bash
   python main.py --radio outra-radio-slug
   # Ou com a URL completa:
   python main.py --radio https://www.socialradio.com.br/radio/outra-radio-slug/
   ```

5. **Modo silencioso (sem anúncio por voz, apenas notificações e terminal):**
   ```bash
   python main.py --no-voice
   ```

6. **Dry Run (apenas imprime no terminal sem áudio ou notificações):**
   ```bash
   python main.py --dry-run
   ```

---

### Testes Automatizados

Para executar a suíte de testes unitários:
```bash
pytest
```

---

### Dependências Externas

1. [Requests](https://pypi.org/project/requests/)
2. [Lingua](https://pypi.org/project/lingua-language-detector/)
3. [gTTS](https://pypi.org/project/gTTS/)
4. [pydub](https://pypi.org/project/pydub/)
5. [Pillow](https://pypi.org/project/pillow/)
6. [pyalsaaudio](https://pypi.org/project/pyalsaaudio/)
7. [audioop-lts](https://pypi.org/project/audioop-lts/) (suporte a áudio para Python 3.13+)
8. [pytest](https://pypi.org/project/pytest/) (testes unitários)
9. Utilitários do sistema Linux (opcionais para notificações): `kdialog` ou `notify-send`, e `kdeconnect-cli`.
