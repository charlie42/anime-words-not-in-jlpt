# Anime words that aren't on the JLPT lists

`words.tsv` is a list of 46 words that come up often in the subtitles of 25 anime but aren't
on the JLPT N5 to N1 vocabulary lists. `topic_words.tsv` has 19 ordinary topic words the
lists also skip, such as 部室 (clubroom).

The JLPT lists are vocabulary lists, so this list is words only. It leaves out particles
such as ぞ and じゃん, grammar endings such as ちまう, and words fused with a particle, such as
そりゃ (= それは). Slurred grammar is left out on purpose too, such as ねえ (= ない, not)
in 知らねえ.

A word makes the list if it comes up in at least 4 of the 25 anime and in about 12 lines in all. The exact cut is 0.15 lines per 1,000, averaged over the anime, and we read up to the first 3,000 lines of each one.
It also needs one of three things. It is a slurred form of a listed word, such as すげえ for すごい. Or it has a JMdict label for casual, rough, old-fashioned or joking speech, or for speech used by men or by women, such as colloquial, slang or archaic. Or JMdict doesn't mark it common. The allow and block lists below keep or leave out a few words by hand.

The script finds the candidates and applies our hand edits, which are in the files below with a
reason on each line. A rerun on the same subtitles gives the same two lists.

The 25 anime: Chainsaw Man, Death Note, Hunter x Hunter (2011), Jujutsu Kaisen, Mob Psycho 100,
Frieren, Dororo, Serial Experiments Lain, K-On, Yuru Camp, Kaguya-sama, Toradora, Spy x Family,
Konosuba, Haikyuu, Hyouka, The Apothecary Diaries, Violet Evergarden, Steins;Gate, Cowboy Bebop,
Evangelion, Cardcaptor Sakura, Fruits Basket, Your Lie in April and Ouran High School Host Club.

- `blocklist.tsv`: rows we left out; part of speech `chunk` marks a piece of text such as ございます whose words we don't count.
- `allowlist.tsv`: words we keep by hand: interjections such as こら and やあ, which the rule for sounds like うっ and へえ would drop, and words like ねえ (hey) whose own JMdict entry has no slang label.
- `genre_words.tsv`: ordinary topic words, moved to `topic_words.tsv`.
- `contexts.tsv`: forms we count only in some places: やれ only in やれやれ, and ねえ (hey) not right after a word, where it is ない (not).
- `senses.tsv`: the JMdict sense each row is heard in (a row with none stops the run), plus an optional form to show in place of the tokenizer's.
- `meanings.tsv`: our own English and tags where no JMdict sense fits; an empty meaning keeps JMdict's English.
- `normal_forms.tsv`: the textbook form a slurred row stands for, where Sudachi's is wrong; `-` means the row isn't slurred.


## Usage

The subtitles aren't included. The script reads `<subtitle dir>/raw/<show>/<episode>.bin` (SRT).

    pip install sudachipy==0.6.11 sudachidict_core==20260428
    python -I not_in_jlpt.py <subtitle dir> <reference dir> words.tsv

It downloads the pinned JLPT lists and JMdict into the reference dir, then writes `words.tsv`,
`words.genre.tsv` and `words.dropped.tsv`. We ship `words.genre.tsv` as `topic_words.tsv`.
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
