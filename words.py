from pathlib import Path
import pickle

import jieba
import jieba.analyse
import requests


jieba_dictionary_download_path = "https://raw.githubusercontent.com/fxsjy/jieba/master/extra_dict/dict.txt.big"
jieba_dictionary_path = Path("./dict/dict.txt.big")
jieba_stop_words_download_path = "https://raw.githubusercontent.com/fxsjy/jieba/master/extra_dict/stop_words.txt"
jieba_stop_words_path = Path("./dict/stop_words.txt")
jieba_user_dict_path = Path("./dict/user_dict.txt")


def install():
    """Download and save dictionaries."""
    download_pathes = (jieba_dictionary_download_path, jieba_stop_words_download_path)
    save_pathes = (jieba_dictionary_path, jieba_stop_words_path)

    for download_path, save_path in zip(download_pathes, save_pathes):
        if not save_path.exists():
            response = requests.get(download_path, timeout=None)
            save_path.parent.mkdir(exist_ok=True)
            response_encoding = response.encoding if response.encoding else "UTF-8"
            save_path.write_text(response.content.decode(response_encoding), encoding="UTF-8")


if __name__ == "__main__":
    install()

    jieba.set_dictionary(jieba_dictionary_path)
    jieba.analyse.set_stop_words(jieba_stop_words_path)
    if jieba_user_dict_path.exists():
        jieba.load_userdict(str(jieba_user_dict_path))
    cache_path = Path(__file__).parent / "cache.pkl"
    cache = pickle.load(cache_path.open('rb'))
    entries = cache["data"]
    titles = []
    for entry in entries:
        if entry["status"] in ("read", "removed", ):
            continue
        titles.append(entry["title"])

    tags = jieba.analyse.extract_tags(" ".join(titles), 50, True)
    print(tags)
