import sys
import webbrowser
from pathlib import Path
from string import ascii_letters

import pafy
import music_tag
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
    def determine_action(result: tuple):
        action = ["verb", "noun"]
        for verb in ['browse', 'listen', 'archive', 'download', 'download & tag', 'share']:
            if verb.title() in result[0]:
                action[0] = list(verb)[-1]
        for noun in ['song', 'shuffle', 'radio', 'artist', 'album']:
            if noun.title() in result[0]:
                action[1] = noun
        return action

    @staticmethod
    def browse(action_type: str, hidden_df: pd.DataFrame, urlonly: bool=False):
        baseurl = "https://music.youtube.com/channel/"
        url = baseurl + hidden_df['browseId'][0]
        webbrowser.open(url)

    @staticmethod
    def listen(action_type: str, hidden_df: pd.DataFrame):
        baseurl = "https://music.youtube.com/watch?video="
        if action_type == 'song':
            url = baseurl + 'v=' + hidden_df['videoId'][0]
        elif action_type in ['shuffle', 'radio']:
            url = baseurl + 'list=' + hidden_df[f'{action_type}Id'][0]
        webbrowser.open(url)

    @staticmethod
    def tag(mp3path: Path, **kwargs):
        f = music_tag.load_file(mp3path)
        for kwarg, value in kwargs.items():
            f[kwarg] = value
        return mp3path

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
                'display': ['title', 'type', 'year', 'isExplicit'],
                'hidden': ['browseId', 'thumbnails']}
        }
        opts = {
            'song': [
                '1. Listen to Song on YouTube Music.',
                '3. Download Song (best format).',
                '4. Download & Tag Song as MP3.'],
            'artist': [
                '1. Browse Artist on YouTube Music.',
                '2. Listen to Shuffle on YouTube Music.',
                '6. Listen to Radio on YouTube Music.'],
            'album': [
                '1. Browse Album on YouTube Music.']
        }
        idx = df.index.to_list()
        idx.append(idx[-1]+1)
        idx = idx[1:]
        fltr = df[df.columns[0]][0]
        display_df = df[columns[fltr]['display']].copy()
        display_df.index = idx # reset to 1-based index
        # Split the artist field from albums filter
        if fltr == 'albums':
            artist_id = display_df['artists'].to_list()
        artists, artist_ids = [], []
        for combo in artist_id:
            artists.append(combo.key())
            artist_ids.append(combo.value())
        display_df['artists'] = artists
        # Split the album field from songs filter
        if fltr == 'songs':
            album_id = display_df['album'].to_list()
        albums, album_ids = [], []
        for combo in album_id:
            albums.append(combo.key)
            album_ids.append(combo.value())
        display_df['album'] = albums
        # Ids are added to hidden_df
        hidden_df = df[columns[fltr]['hidden']].copy()
        hidden_df.index = idx
        if fltr == 'artists':
            hidden_df['artist_ids'] = artist_ids
        if fltr == 'albums':
            hidden_df['album_']
        hidden_df['album_ids'] = album_ids
        del artists, albums, artist_ids, album_ids # ~ loop
        # User selections
        print(display_df.to_markdown())
        sel = input('Please Enter Result #: ').strip()
        opts = pd.DataFrame({'Options': opts[fltr]})
        print(opts.to_markdown(index=False))
        opt = input('Please Enter Option #: ').strip()
        if sel.isalnum() and abs(int(sel))-1 <= len(display_df):
            sel = abs(int(sel))
        else:
            return self._parse(df) if \
                tryAgain(STRINGS['invalid_tryagain']) == 'y' else sys.exit()
        if opt.isalnum() and abs(int(opt))-1 <= len(display_df):
            opt = abs(int(opt))-1
        else:
            return self._parse(df) if \
                tryAgain(STRINGS['invalid_tryagain']) == 'y' else sys.exit()
        return (opts[opt], hidden_df[hidden_df.index==sel].copy()) # result param

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
        return pd.DataFrame(results)

    def download(self, action_type: str, hidden_df: pd.DataFrame):
        file_path = Path(self._download_dir,
                        ''.join(char for char in hidden_df['title'] \
                            if char in ascii_letters))
        video = pafy.new(hidden_df['videoId'][0])
        if action_type == 'download':
            stream = video.getbestaudio()
            file_path = Path(f'{file_path}.{stream.extension}')
            file_path = stream.download(file_path)
        if action_type == 'tag':
            m4a_path = Path(f'{file_path}.m4a')
            file_path = Path(f'{file_path}.mp3')
            for i, audio in enumerate(video.audiostreams()[::-1]):
                if audio.extension == "m4a":
                    m4a_path = video.audiostreams[i].dowload(m4a_path)
                    audio_in = m4a_path
                    audio_out = file_path
                    audio_out = self.ff(audio_in, audio_out)
                    file_path.unlink()
                    file_path = audio_out
                    del audio_out
            kwargs = {}
            for key in hidden_df.columns.names().to_list():
                kwargs[key] = hidden_df[key][0]
            file_path = self.tag(file_path, kwargs)
        return file_path

    def fetch(self):
        df = self.ytMusicSearch()
        result = self._parse(df)
        action = self.determine_action(result)
        action_type = action(0)
        hidden_df = action(1)
        if action_type == 'browse':
            self.browse(action_type, hidden_df)
        elif action_type == 'listen':
            self.listen(action_type, hidden_df)
        elif action_type in ['download', 'tag']:
            self.download(action_type, hidden_df)


if __name__ == "__main__":
    homeMusicDir = Path(Path.home(), 'Music')
    if not homeMusicDir.exists():
        homeMusicDir.mkdir()
    syne = MusicFetcher(path=homeMusicDir)
    syne.fetch()