import os
import sys
import webbrowser
from pathlib import Path
from string import ascii_letters
from numpy import histogramdd

import pafy
import eyed3
import pandas as pd
from pyffmpeg import FFmpeg
from ytmusicapi import YTMusic

STRINGS = {
    'invalid_tryagain': 'Not a valid choice. Try Again? [Y/n]: '
}

def tryAgain(prompt: str='Try Again? [Y/n]'):
    """Prompt decision on whether to try again

    Keyword arguments:
    prompt -- User prompt message.
    Return: Recursive until return value equals 'y' or 'n'
    """
    user_response = input(prompt).strip()
    response = user_response.lower()
    if not response:
        if 'Y' in prompt:
            response = 'y'
        else:
            response = 'n'
    elif 'y' in response and 'n' not in response:
        response = 'y'
    elif 'n' in response and 'y' not in response:
        response = 'n'
    else:
        print(f'{user_response} is not a valid response.')
        return tryAgain(prompt)
    return response


class MusicFetcher:

    def __init__(self, download_dir: Path):
        self._download_dir = download_dir
        self.ff = FFmpeg()
        self.ytm = YTMusic()

    @property
    def download_dir(self):
        return self._download_dir

    @download_dir.setter
    def download_dir(self, value):
        if type(value) == Path:
            if not value.exists():
                value.mkdir()
        else:
            print('Unable to access .download_dir, which can be reassigned.')
            return self._download_dir
        self._download_dir = value

    @staticmethod
    def determine_action(requested_action: str):
        requested_action = requested_action.lower()
        if 'listen' in requested_action:
            for listen_type in ['song', 'shuffle', 'radio']:
                if listen_type in requested_action:
                    return ('listen', listen_type)
        elif 'browse' in requested_action:
            for browse_type in ['artist', 'album']:
                if browse_type in requested_action:
                    return ('browse', browse_type)
        elif 'download' in requested_action:
            if 'tag' in requested_action:
                return ('download', 'tag')
            else:
                return ('download', 'download')

    @staticmethod
    def browse(df: pd.DataFrame):
        baseurl = "https://music.youtube.com/channel/"
        url = baseurl + df['browseId'].to_list()[0]
        webbrowser.open(url)

    @staticmethod
    def listen(action_type: str, df: pd.DataFrame):
        baseurl = "https://music.youtube.com/watch?"
        if action_type == 'song':
            url = baseurl + 'v=' + df['videoId'].to_list()[0]
        elif action_type == 'shuffle':
            url = baseurl + 'list=' + df['shuffleId'].to_list()[0]
        elif action_type == 'radio':
            url = baseurl + 'list=' + df['radioId'].to_list()[0]
        webbrowser.open(url)

    def _parse(self, df: pd.DataFrame):
        """Parse search results & offer listening choices

        Keyword arguments:
        df -- pandas DataFrame returned from ytMusicSearch
        Return: tuple consisting of listening choice & list of url components
        """
        columns = {
            'song': {
                'display': ['title', 'artists', 'duration', 'isExplicit'],
                'hidden': ['title', 'artists', 'album', 'duration', 'videoId', 'thumbnails']},
            'artist': {
                'display': ['artist'],
                'hidden': ['shuffleId', 'radioId', 'browseId', 'thumbnails']},
            'album': {
                'display': ['title', 'type', 'year', 'artists', 'isExplicit'],
                'hidden': ['browseId', 'thumbnails']}}
        opts = {
            'song': [
                '1. Listen to Song on YouTube Music.',
                '2. Download Song (best format).',
                '3. Download & Tag Song as MP3.'],
            'artist': [
                '1. Browse Artist on YouTube Music.',
                '2. Listen to Shuffle on YouTube Music.',
                '3. Listen to Radio on YouTube Music.'],
            'album': [
                '1. Browse Album on YouTube Music.']}
        idx = df.index.to_list()
        idx.append(idx[-1]+1)
        idx = idx[1:]
        record_type = df[df.columns[0]][0]
        display_df = df[columns[record_type]['display']].copy()
        display_df.index = idx # reset to 1-based index
        hidden_df = df[columns[record_type]['hidden']].copy()
        hidden_df.index = idx
        # Split combo label and id fields
        if 'album' in display_df.columns:
            albums_and_ids = display_df['album'].to_list()
            album, album_id = [], []
            for dct in albums_and_ids:
                album.append(dct['name'])
                album_id.append(dct['id'])
            display_df['album'] = album
            hidden_df['album'] = album
            hidden_df['album_id'] = album_id
            del albums_and_ids, album, album_id
        if 'artists' in display_df.columns:
            artists_and_ids = []
            for lst in display_df['artists'].to_list():
                artists_and_ids.append(lst[0])
            artist, artist_id = [], []
            for dct in artists_and_ids:
                artist.append(dct['name'])
                artist_id.append(dct['id'])
            display_df['artists'] = artist
            hidden_df['artist'] = artist
            hidden_df['artist_id'] = artist_id
            del artists_and_ids, artist, artist_id
        # User selections
        try:
            print(display_df.to_markdown())
            sel = int(input('Please Enter Result #: ').strip())
            opts = pd.DataFrame({'Options': opts[record_type]})
            print(opts.to_markdown(index=False))
            opt = int(input('Please Enter Option #: ').strip()) - 1
        except:
            return self._parse(df) if \
                tryAgain(STRINGS['invalid_tryagain']) == 'y' else sys.exit()
        return  (opts['Options'].to_list()[opt], hidden_df[hidden_df.index==sel].copy())

    def search(self, limit: int=5):
        """Filtered Youtube Music Search

        Keyword arguments:
        limit -- number of search results
        Return: dictionary of results
        """
        search = lambda x, y: self.ytm.search(x, filter=y)

        opts = ['1. Songs', '2. Artists', '3. Albums']
        df = pd.DataFrame({"Options": opts})
        print(df.to_markdown(index=False))
        opt = input("Please Enter Option #: ").strip()
        if opt.isalnum() and abs(int(opt))-1 <= len(opts):
            opt = abs(int(opt))-1
        else:
            response = tryAgain(STRINGS['invalid_tryagain'])
            if response == 'y':
                return self._search(limit)
            else:
                sys.exit()
        fltr = opts[opt].split(". ")[-1].lower()
        qry = input(f'Enter {fltr.title()[:-1]}: ').strip()
        if not qry:
            print('A search for nothing might yield everything.')
            sys.exit()
        results = search(qry, fltr)
        if not results:
            response = tryAgain('Search yielded 0 results. Try Again? [Y/n]: ')
            if response == 'y':
                return self._search(limit)
            else:
                sys.exit()
        return pd.DataFrame(results[:limit+1])

    def download(self, action_type: str, df: pd.DataFrame):
        title = df['title'].to_list()[0]
        filename = ''.join([char for char in title if char in ascii_letters])
        video = pafy.new(df['videoId'].to_list()[0])
        if action_type == 'download':
            stream = video.getbestaudio()
            filename = filename + '.' + stream.extension
            download_path = Path(self.download_dir, filename)
            stream.download(str(download_path))
        if action_type == 'tag':
            mp3file = filename + '.' + 'mp3'
            for audio in video.audiostreams[::-1]:
                if audio.extension == "m4a":
                    m4afile = filename + '.' + audio.extension
                    audio_in = Path(self.download_dir, m4afile)
                    audio.download(str(audio_in))
                    audio_out = Path(self.download_dir, mp3file)
                    download_path = self.ff.convert(str(audio_in), str(audio_out))
                    os.remove(audio_in)
                    del mp3file, m4afile, audio_in, audio_out
                    break
            mp3file = eyed3.load(download_path)
            mp3file.tag.title = df['title'].to_list()[0]
            mp3file.tag.artist = df['artist'].to_list()[0]
            mp3file.tag.album = df['album'].to_list()[0]['name']
            mp3file.tag.comment = df['videoId'].to_list()[0]
            mp3file.tag.save()
        return download_path

    def fetch(self):
        df = self.search()
        action, df = self._parse(df)
        action, action_type = self.determine_action(action)
        if action:
            if action == 'browse':
                self.browse(df)
            elif action == 'listen':
                self.listen(action_type, df)
            elif action in ['download', 'tag']:
                self.download(action_type, df)
        else:
            print()


if __name__ == "__main__":
    homeMusicDir = Path(Path.home(), 'Music')
    if not homeMusicDir.exists():
        homeMusicDir.mkdir()
    syne = MusicFetcher(download_dir=homeMusicDir)
    syne.fetch()