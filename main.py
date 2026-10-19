import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
from pydub.utils import get_player_name


# Configurações padrão da estação.
RADIO_URL = "https://www.socialradio.com.br/radio/verdeolivaresende/"
CDN_BASE_URL = "https://cdn.socialradio.com.br/content/v1/radios"

# Configurações padrão de voz.
READ_ALOUD = True    # Ativa ou desativa a leitura em voz alta.
VOICE_VOLUME = 60    # Volume do computador ao anunciar em voz alta.
SPEAK_HU3BR = False  # Ativa ou desativa o anúncio de nomes estrangeiros em português do Brasil.

# Configurações padrão de notificação.
NOTIFY_DESKTOP = True                       # Ativa ou desativa a notificação da área de trabalho.
NOTIFY_KDE_CONNECT = True                   # Ativa ou desativa a notificação dos dispositivos no KDE Connect.
FETCH_LYRICS = False                        # Baixa e exibe a letra da música atual.

# Cache global do detector de idioma (singleton).
_LANGUAGE_DETECTOR = None


def get_app_paths():
    """
    Retorna os caminhos de cache e log em conformidade com a especificação XDG Base Directory.
    Evita poluir o diretório raiz do usuário (~/).
    """
    cache_base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    state_base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")

    cache_dir = os.path.join(cache_base, "oliva-announcer")
    log_dir = os.path.join(state_base, "oliva-announcer")

    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    art_path = os.path.join(cache_dir, "temp_art.png")
    log_path = os.path.join(log_dir, "oliva_log.txt")

    return art_path, log_path


def extract_radio_slug(url_or_slug: str) -> str:
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


def fetch_radio_metadata(slug: str):
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


def fetch_radio_config(slug: str):
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


def format_track_info(metadata, station_name="Verde Oliva") -> str:
    """
    Formata o nome da faixa e artista a partir do payload de metadados da rádio.
    Retorna o nome da estação caso seja comercial, vinheta ou informação ausente.
    """
    if not metadata:
        return station_name

    is_commercial = metadata.get("is_commercial", False)
    title = metadata.get("title")
    artist = metadata.get("artist")

    if is_commercial or not title:
        return station_name

    title_clean = title.strip().title()
    if artist:
        track = f"{artist.strip().title()} - {title_clean}"
    else:
        track = title_clean

    if "\ufffd" in track:
        return station_name

    return track


def assemble_time(dt: datetime = None) -> str:
    """
    Gera uma frase amigável com a hora falada em português (ex: 'duas e meia', 'uma em ponto').
    """
    if dt is None:
        dt = datetime.now()

    hour_24 = int(dt.strftime("%H"))
    hour = int(dt.strftime("%I"))
    minute = int(dt.strftime("%M"))

    hour_str = str(hour)
    if hour == 1:
        hour_str = "uma"
    elif hour == 2:
        hour_str = "duas"

    if minute == 0:
        moment = f"{hour_str} em ponto"
    elif minute == 30:
        moment = f"{hour_str} e meia"
    else:
        moment = f"{hour_str} e {minute}"

    if hour_24 == 0:
        moment = "meia noite"
    elif hour_24 == 12:
        moment = "meio dia"

    return moment


def log(info: str, log_path: str):
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now()}: {info}\n")
    except Exception as e:
        print(f"Aviso ao salvar log: {e}")


def get_language_detector():
    """
    Inicializa o detector de idioma como singleton para evitar overhead de recarga em cada execução.
    """
    global _LANGUAGE_DETECTOR
    if _LANGUAGE_DETECTOR is None:
        languages = [Language.ENGLISH, Language.PORTUGUESE, Language.SPANISH, Language.ITALIAN]
        _LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_languages(*languages).build()
    return _LANGUAGE_DETECTOR


def detect_language(text: str, speak_hu3br: bool = False):
    if speak_hu3br:
        return "Português", "pt"

    detector = get_language_detector()
    lang = detector.detect_language_of(text)
    if not lang:
        return "Português", "pt"

    name = lang.name.title()
    code = lang.iso_code_639_1.name.lower()
    return name, code


def get_connected_devices():
    try:
        results = subprocess.run(
            ["kdeconnect-cli", "--list-available", "--id-only"],
            capture_output=True,
            text=True
        ).stdout.strip().split("\n")
        ids = [result.strip() for result in results if result.strip() and not result.strip().startswith("_")]
        return ids
    except Exception as e:
        print(f"Aviso: Não foi possível verificar dispositivos KDE Connect: {e}")
        return []


def get_lyrics(artist: str, title: str) -> str:
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get("lyrics", "Lyrics not found.")
    except Exception:
        pass
    return "Lyrics not found."


def notify_devices(
    song_info: str,
    art_url: str,
    language,
    station_name: str = "Verde Oliva",
    art_path: str = None,
    fetch_lyrics: bool = False,
    notify_desktop: bool = True,
    notify_kde_connect: bool = True
):
    if fetch_lyrics and " - " in song_info:
        parts = song_info.split(" - ", 1)
        artist = parts[0].strip()
        song = parts[1].strip()
        lyrics = f"\nLyrics: {get_lyrics(artist, song)}"
    else:
        lyrics = ""

    message = f"Song: {song_info}\nLanguage: {language[0]} ({language[1]}){lyrics}"

    if notify_desktop:
        if art_url and art_path:
            try:
                response = requests.get(art_url, timeout=10)
                if response.status_code == 200:
                    art_file = Image.open(BytesIO(response.content))
                    art_file.save(art_path, "PNG")
            except Exception as e:
                print(f"Aviso ao baixar imagem da capa: {e}")

        # Tenta kdialog primeiro (KDE); se indisponível, usa notify-send (padrão Freedesktop/GNOME/XFCE)
        has_kdialog = shutil.which("kdialog") is not None
        has_notify_send = shutil.which("notify-send") is not None

        try:
            if has_kdialog:
                cmd = [
                    "kdialog",
                    "--passivepopup", message, "5",
                    "--title", f"Tocando na {station_name}"
                ]
                if art_path and os.path.exists(art_path):
                    cmd.extend(["--icon", art_path])
                subprocess.run(cmd, check=True)
            elif has_notify_send:
                cmd = ["notify-send", f"Tocando na {station_name}", message, "-t", "5000"]
                if art_path and os.path.exists(art_path):
                    cmd.extend(["-i", art_path])
                subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"Aviso ao enviar notificação na área de trabalho: {e}")

    if notify_kde_connect:
        device_ids = get_connected_devices()
        for device_id in device_ids:
            try:
                cmd = ["kdeconnect-cli", "--device", device_id, "--ping-msg", message]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.strip() if e.stderr else str(e)
                print(f"Aviso ao enviar notificação KDE Connect para o dispositivo {device_id}: {err_msg}")
            except Exception as e:
                print(f"Aviso ao enviar notificação KDE Connect para o dispositivo {device_id}: {e}")


def read_aloud(
    song_info: str,
    language_code: str,
    station_name: str = "Verde Oliva",
    volume_level: int = VOICE_VOLUME,
    speak_hu3br: bool = SPEAK_HU3BR,
    enabled: bool = True,
    log_path: str = None
):
    if log_path:
        log(song_info, log_path)

    if not enabled:
        return None

    mixer = None
    original_volume = None
    try:
        mixer = alsaaudio.Mixer()
        original_volume = mixer.getvolume(0)
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
        if speak_hu3br:
            language_code = "pt"
        texts = ["Você está ouvindo ", song_name, " na voz de ", artist_name, f" na {station_name}."]
        languages = ["pt", language_code, "pt", language_code, "pt"]

    # Concatenação limpa e segura de áudio via pydub.AudioSegment
    combined_audio = AudioSegment.empty()
    for text, lang in zip(texts, languages):
        fp = io.BytesIO()
        gTTS(text, lang=lang).write_to_fp(fp)
        fp.seek(0)
        segment = AudioSegment.from_file(fp, format="mp3")
        combined_audio += segment

    try:
        if mixer and original_volume is not None and volume_level is not None:
            mixer.setvolume(volume_level)
        play_audio(combined_audio)
    finally:
        if mixer and original_volume is not None:
            mixer.setvolume(original_volume[0])


def play_audio(audio_segment: AudioSegment):
    """
    Reproduz o áudio de forma limpa, suprimindo mensagens de banner e estatísticas do player de linha de comando.
    """
    player = get_player_name()
    with tempfile.NamedTemporaryFile("w+b", suffix=".wav") as f:
        audio_segment.export(f.name, "wav")
        cmd = [player, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "quiet", f.name]
        try:
            subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception as e:
            print(f"Aviso na reprodução de áudio: {e}")


def print_track_banner(track_title: str, station_name: str, language, album_art: str = None, timestamp: str = None, is_dry_run: bool = False):
    """
    Exibe uma saída moderna e limpa no terminal para a faixa atual.
    """
    line = "─" * 60
    time_tag = f"  [{timestamp}]" if timestamp else ""
    print(f"\n{line}")
    print(f"  🎵  {track_title}{time_tag}")
    print(f"  📻  {station_name}  •  🌐 {language[0]} ({language[1]})")
    if is_dry_run:
        if album_art:
            print(f"  🖼️   Capa: {album_art}")
        print("  ⚡  [Modo Dry-Run: Áudio e notificações desativados]")
    print(f"{line}\n")


def fetch_track_state(slug: str):
    """
    Obtém as configurações e os metadados atuais da rádio.
    """
    config_data = fetch_radio_config(slug)
    radio_info = config_data.get("radio", {}) if config_data else {}
    station_name = radio_info.get("name", "Verde Oliva")
    default_logo = radio_info.get("logo_url")

    metadata_resp = fetch_radio_metadata(slug)
    meta = metadata_resp.get("metadata") if metadata_resp else None

    track_title = format_track_info(meta, station_name=station_name)
    album_art = (meta.get("album_art_url") if meta else None) or default_logo

    return track_title, album_art, station_name


def parse_args():
    parser = argparse.ArgumentParser(
        description="Oliva Announcer: Identifica e anuncia faixas em execução na Social Rádio."
    )
    parser.add_argument(
        "--radio", "-r",
        default=RADIO_URL,
        help=f"URL ou slug da estação no Social Rádio (padrão: {RADIO_URL})"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Executa em modo contínuo (monitor), detectando e anunciando apenas quando a música mudar"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=15,
        help="Intervalo de verificação em segundos para o modo --watch (padrão: 15s)"
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Desativa o anúncio em voz alta"
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Desativa as notificações na área de trabalho e KDE Connect"
    )
    parser.add_argument(
        "--volume", "-v",
        type=int,
        default=VOICE_VOLUME,
        help=f"Volume do áudio durante o anúncio (padrão: {VOICE_VOLUME})"
    )
    parser.add_argument(
        "--lyrics",
        action="store_true",
        default=FETCH_LYRICS,
        help="Baixa e exibe a letra da música atual na notificação"
    )
    parser.add_argument(
        "--hu3br",
        action="store_true",
        default=SPEAK_HU3BR,
        help="Anuncia nomes estrangeiros usando pronúncia em português do Brasil"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe os dados extraídos no console sem reproduzir áudio ou enviar notificações"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    art_path, log_path = get_app_paths()
    slug = extract_radio_slug(args.radio)

    read_aloud_enabled = READ_ALOUD and not args.no_voice and not args.dry_run
    notify_enabled = not args.no_notify and not args.dry_run

    if args.watch:
        print(f"📻 Monitorando rádio '{slug}' a cada {args.interval}s (Pressione Ctrl+C para encerrar)")
        last_track = None
        try:
            while True:
                track_title, album_art, station_name = fetch_track_state(slug)
                now_str = datetime.now().strftime("%H:%M:%S")

                sys.stdout.write("\r\033[K")
                sys.stdout.flush()

                if track_title and track_title != last_track:
                    language = detect_language(track_title, speak_hu3br=args.hu3br)
                    last_track = track_title

                    print_track_banner(
                        track_title, station_name, language,
                        album_art=album_art, timestamp=now_str, is_dry_run=args.dry_run
                    )

                    if notify_enabled:
                        notify_devices(
                            track_title, album_art, language,
                            station_name=station_name, art_path=art_path,
                            fetch_lyrics=args.lyrics, notify_desktop=NOTIFY_DESKTOP,
                            notify_kde_connect=NOTIFY_KDE_CONNECT
                        )
                    if read_aloud_enabled:
                        read_aloud(
                            track_title, language[1],
                            station_name=station_name, volume_level=args.volume,
                            speak_hu3br=args.hu3br, enabled=True, log_path=log_path
                        )
                elif track_title:
                    print(f"[{now_str}] ⏸️  Mesma música: {track_title}")

                # Contagem regressiva interativa para o próximo ciclo
                for remaining in range(args.interval, 0, -1):
                    sys.stdout.write(f"\r\033[K⏳ Próxima verificação em {remaining}s...")
                    sys.stdout.flush()
                    time.sleep(1)
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()

        except KeyboardInterrupt:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            print("\n🛑 Monitoramento encerrado pelo usuário.")
    else:
        track_title, album_art, station_name = fetch_track_state(slug)
        if not track_title:
            print("❌ Falha na extração do conteúdo da página ou rádio fora do ar.")
            return

        language = detect_language(track_title, speak_hu3br=args.hu3br)
        print_track_banner(
            track_title, station_name, language,
            album_art=album_art, is_dry_run=args.dry_run
        )

        if notify_enabled:
            notify_devices(
                track_title, album_art, language,
                station_name=station_name, art_path=art_path,
                fetch_lyrics=args.lyrics, notify_desktop=NOTIFY_DESKTOP,
                notify_kde_connect=NOTIFY_KDE_CONNECT
            )

        if read_aloud_enabled:
            read_aloud(
                track_title, language[1],
                station_name=station_name, volume_level=args.volume,
                speak_hu3br=args.hu3br, enabled=True, log_path=log_path
            )


if __name__ == "__main__":
    main()
