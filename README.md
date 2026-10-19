# Shazam-Oliva

Shazam-Oliva é um script em Python que identifica a música transmitida em tempo real na [Rádio Verde Oliva](https://www.socialradio.com.br/radio/verdeolivaresende/) (ou qualquer outra estação hospedada na Social Rádio).

Ao receber a informação, o script anuncia, em voz alta, o nome da música e do intérprete. Também envia uma notificação para a área de trabalho (kdialog) com a imagem da capa do álbum e para todos os dispositivos pareados no [KDE Connect](https://kdeconnect.kde.org/).

### Observações

1. **Outras estações:** Caso queira consultar outra estação do Social Rádio, altere a URL ou slug dentro do script alterando a variável `RADIO_URL` (por exemplo: `"https://www.socialradio.com.br/radio/verdeolivaresende/"` ou apenas `"verdeolivaresende"`).
2. O script possui várias opções de personalização logo no topo de `main.py` (volume, leitura em voz alta, notificações, busca de letras, etc.).

### Instalação e Uso

1. Crie e ative o ambiente virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Execute o script:
   ```bash
   python main.py
   ```

### Dependências Externas

1. [Requests](https://pypi.org/project/requests/)
2. [Lingua](https://pypi.org/project/lingua-language-detector/)
3. [gTTS](https://pypi.org/project/gTTS/)
4. [pydub](https://pypi.org/project/pydub/)
5. [Pillow](https://pypi.org/project/pillow/)
6. [pyalsaaudio](https://pypi.org/project/pyalsaaudio/)
7. [audioop-lts](https://pypi.org/project/audioop-lts/) (suporte a áudio para Python 3.13+)
8. Utilitários do sistema Linux (opcionais para notificações e áudio): `kdialog`, `kdeconnect-cli`.
