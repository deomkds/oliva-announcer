import io
import os.path
import subprocess
import urllib.parse
from datetime import datetime
from io import BytesIO
from pathlib import Path

import alsaaudio
import requests
from PIL import Image
from gtts import gTTS
from lingua import Language, LanguageDetectorBuilder
from pydub import AudioSegment
from pydub.playback import play


# Configurações da estação.
# Pode ser a URL completa da Social Rádio (ex: https://www.socialradio.com.br/radio/verdeolivaresende/) ou apenas o slug (ex: verdeolivaresende)
RADIO_URL = "https://www.socialradio.com.br/radio/verdeolivaresende/"
CDN_BASE_URL = "https://cdn.socialradio.com.br/content/v1/radios"

# Configurações de voz.
READ_ALOUD = True    # Ativa ou desativa a leitura em voz alta.
VOICE_VOLUME = 60    # Volume do computador ao anunciar em voz alta.
SPEAK_HU3BR = False  # Ativa ou desativa o anúncio de nomes estrangeiros em português do Brasil.

# Configurações de notificação.
NOTIFY_DESKTOP = True                       # Ativa ou desativa a notificação da área de trabalho.
NOTIFY_KDE_CONNECT = True                   # Ativa ou desativa a notificação dos dispositivos no KDE Connect.
FETCH_LYRICS = False                        # Baixa e exibe a letra da música atual.

home_dir = Path.home()
art_path = os.path.join(home_dir, "temp_art.png")
log_path = os.path.join(home_dir, "oliva_log.txt")


def extract_radio_slug(url_or_slug):
    """
    Extrai o slug identificador da rádio a partir da URL da Social Rádio ou do próprio slug.
    Exemplo: 'https://www.socialradio.com.br/radio/verdeolivaresende/' -> 'verdeolivaresende'
    """
    cleaned = url_or_slug.strip().rstrip("/")
    if "/" in cleaned:
        path = urllib.parse.urlparse(cleaned).path.strip("/")
        parts = path.split("/")
        return parts[-1]
    return cleaned


def fetch_radio_metadata(slug):
    """
    Busca os metadados atuais transmitidos pela rádio (título, artista, capa, se é comercial).
    """
    url = f"{CDN_BASE_URL}/{slug}/metadata.json"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Erro ao buscar metadados da rádio: {e}")
    return None


def fetch_radio_config(slug):
    """
    Busca as configurações gerais da rádio (nome oficial, logo, stream URL).
    """
    url = f"{CDN_BASE_URL}/{slug}/config.json"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Erro ao buscar configuração da rádio: {e}")
    return None


def assemble_time():
    hour_24 = int(datetime.now().strftime("%H"))
    hour = int(datetime.now().strftime("%I"))
    minute = int(datetime.now().strftime("%M"))

    if hour == 1:
        hour = "uma"
    elif hour == 2:
        hour = "duas"

    if minute == 0:
        moment = f"{hour} em ponto"
    elif minute == 30:
        moment = f"{hour} e meia"
    else:
        moment = f"{hour} e {minute}"

    if hour_24 == 0:
        moment = "meia noite"
    elif hour_24 == 12:
        moment = "meio dia"

    return moment


def log(info):
    with open(log_path, "a") as log_file:
        log_file.write(f"{datetime.now()}: {info}\n")


def read_aloud(song_info, language, station_name="Verde Oliva"):
    log(song_info)
    if not READ_ALOUD:
        return None

    mixer = None
    volume = None
    try:
        mixer = alsaaudio.Mixer()
        volume = mixer.getvolume(0)
    except Exception as e:
        print(f"Aviso: Não foi possível acessar o mixer ALSA: {e}")

    if " - " in song_info:
        parts = song_info.split(" - ", 1)
        artist_name = parts[0].strip()
        song_name = parts[1].strip()
    else:
        artist_name = ""
        song_name = song_info.strip()

    is_station_announcement = (
        not artist_name
        or song_info == "Verde Oliva - Resende"
        or song_name.lower() in ["ao vivo", "verde oliva", station_name.lower()]
    )

    if is_station_announcement:
        time_now = assemble_time()
        texts = [f"Você está sintonizado na {station_name}. Agora, {time_now}."]
        languages = ["pt"]
    else:
        if SPEAK_HU3BR:
            language = "pt"
        texts = ["Você está ouvindo ", song_name, " na voz de ", artist_name, f" na {station_name}."]
        languages = ["pt", language, "pt", language, "pt"]

    fp = io.BytesIO()

    for num, text in enumerate(texts):
        print(f"{num}: {text} ({languages[num]})")
        gTTS(text, lang=languages[num]).write_to_fp(fp)

    fp.seek(0)

    try:
        if mixer and volume:
            mixer.setvolume(VOICE_VOLUME)
        play(AudioSegment.from_file(fp, format="mp3"))
    finally:
        if mixer and volume:
            mixer.setvolume(volume[0])


def detect_language(text):
    if SPEAK_HU3BR:
        return "Português", "pt"
    languages = [Language.ENGLISH, Language.PORTUGUESE, Language.SPANISH, Language.ITALIAN]
    detector = LanguageDetectorBuilder.from_languages(*languages).build()
    lang = detector.detect_language_of(text)
    if not lang:
        return "Português", "pt"
    name = lang.name.title()
    code = lang.iso_code_639_1.name.lower()
    return name, code


def get_connected_devices():
    try:
        results = subprocess.run(
            ["kdeconnect-cli", "--list-devices", "--id-only"],
            capture_output=True,
            text=True
        ).stdout.strip().split("\n")
        ids = [result.strip() for result in results if result.strip() and not result.strip().startswith("_")]
        return ids
    except Exception as e:
        print(f"Aviso: Não foi possível verificar dispositivos KDE Connect: {e}")
        return []


def get_lyrics(artist, title):
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get("lyrics", "Lyrics not found.")
    except Exception:
        pass
    return "Lyrics not found."


def notify_devices(song_info, art_url, language, station_name="Verde Oliva"):
    if FETCH_LYRICS and " - " in song_info:
        parts = song_info.split(" - ", 1)
        artist = parts[0].strip()
        song = parts[1].strip()
        lyrics = f"\nLyrics: {get_lyrics(artist, song)}"
    else:
        lyrics = ""

    message = f"Song: {song_info}\nLanguage: {language[0]} ({language[1]}){lyrics}"

    if NOTIFY_DESKTOP:
        if art_url:
            try:
                response = requests.get(art_url, timeout=10)
                if response.status_code == 200:
                    art_file = Image.open(BytesIO(response.content))
                    art_file.save(art_path, "PNG")
            except Exception as e:
                print(f"Aviso ao baixar imagem da capa: {e}")

        try:
            cmd = [
                "kdialog",
                "--passivepopup", message, "5",
                "--title", f"Tocando na {station_name}"
            ]
            if os.path.exists(art_path):
                cmd.extend(["--icon", art_path])
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"Aviso ao enviar notificação kdialog: {e}")

    if NOTIFY_KDE_CONNECT:
        try:
            device_ids = get_connected_devices()
            for device_id in device_ids:
                cmd = ["kdeconnect-cli", "--device", device_id, "--ping-msg", message]
                subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"Failed to send notification via KDE Connect: {e}")


def main():
    slug = extract_radio_slug(RADIO_URL)
    config_data = fetch_radio_config(slug)
    radio_info = config_data.get("radio", {}) if config_data else {}
    station_name = radio_info.get("name", "Verde Oliva")
    default_logo = radio_info.get("logo_url")

    metadata_resp = fetch_radio_metadata(slug)
    if not metadata_resp or not metadata_resp.get("metadata"):
        print("Falha na extração do conteúdo da página ou rádio fora do ar.")
        return

    meta = metadata_resp["metadata"]
    is_commercial = meta.get("is_commercial", False)
    title = meta.get("title")
    artist = meta.get("artist")
    album_art = meta.get("album_art_url") or default_logo

    if is_commercial or not title:
        tag_content = station_name
    elif artist:
        tag_content = f"{artist.strip().title()} - {title.strip().title()}"
    else:
        tag_content = title.strip().title()

    if "\ufffd" in tag_content:  # For when the web player shows garbage data.
        tag_content = station_name

    language = detect_language(tag_content)
    notify_devices(tag_content, album_art, language, station_name=station_name)
    read_aloud(tag_content, language[1], station_name=station_name)


if __name__ == "__main__":
    main()
