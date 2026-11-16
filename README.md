# Anime words that aren't on the JLPT lists

`words.tsv` has 46 words that come up often in the subtitles of 25 anime but aren't on the
JLPT N5 to N1 vocabulary lists. `ordinary_words.tsv` has 19 more that are ordinary words that just
happen to not be on the lists, such as 部室 (clubroom) and ブタ (pig). We sorted those into their
own file by hand; `move_to_ordinary.tsv` gives the reason for each.

The JLPT lists are vocabulary lists, so this list is words only: no particles or grammar endings.

Every word on the list:

- comes up in at least 4 of the 25 anime, and in about 12 lines in all
- is a slurred form (すげえ for すごい), is labeled casual, familiar, rough, masculine or
  old-fashioned in JMdict, or isn't marked common in JMdict

A few words are kept or left out by hand. The other .tsv files list them, each with its reason.

The 25 anime: Chainsaw Man, Death Note, Hunter x Hunter (2011), Jujutsu Kaisen, Mob Psycho 100,
Frieren, Dororo, Serial Experiments Lain, K-On, Yuru Camp, Kaguya-sama, Toradora, Spy x Family,
Konosuba, Haikyuu, Hyouka, The Apothecary Diaries, Violet Evergarden, Steins;Gate, Cowboy Bebop,
Evangelion, Cardcaptor Sakura, Fruits Basket, Your Lie in April and Ouran High School Host Club.


## Usage

The subtitles aren't included. The script reads `<subtitle dir>/raw/<show>/<episode>.bin` (SRT).

    pip install sudachipy==0.6.11 sudachidict_core==20260428
    python -I not_in_jlpt.py <subtitle dir> <reference dir> words.tsv

It downloads the pinned JLPT lists and JMdict into the reference dir, then writes `words.tsv`,
`ordinary_words.tsv` and `words.dropped.tsv`.
`words.dropped.tsv` counts what was left out and why.


## Sources

- JLPT lists: Jonathan Waller (tanos.co.uk, CC BY), via
  [stephenmk/yomitan-jlpt-vocab](https://github.com/stephenmk/yomitan-jlpt-vocab) (CC BY-SA 4.0).
- JMdict by the EDRDG, via [scriptin/jmdict-simplified](https://github.com/scriptin/jmdict-simplified) (CC BY-SA 4.0).
- Tokenizer: SudachiPy with sudachidict_core (Apache 2.0).


## License

The lists are CC BY-SA 4.0. The script is MIT. If you use the lists, please credit us with
this line:

    Data from learnfromx (https://learnfromx.com)
