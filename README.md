# Anime words that aren't on the JLPT lists

`words.tsv` is a list of 70 words that come up often in the subtitles of 25 anime but aren't
on the JLPT N5 to N1 vocabulary lists. `topic_words.tsv` has 22 ordinary topic words the
lists also skip, such as 部室 (clubroom).

The script found the candidates, and we checked every row by hand against real subtitle
lines. `blocklist.tsv`, `allowlist.tsv`, `genre_words.tsv`, `senses.tsv` and
`normal_forms.tsv` hold the hand edits, with a reason on each line. A few rows were removed
from the published lists after the last run, so a rerun gives a slightly longer list.


## Running it

The subtitles aren't included. The script reads `<subtitle dir>/raw/<show>/<episode>.bin` (SRT).

    pip install sudachipy==0.6.11 sudachidict_core==20260428
    python -I not_in_jlpt.py <subtitle dir> <reference dir> out.tsv

It downloads the pinned JLPT lists and JMdict into the reference dir, then writes `out.tsv`,
`out.genre.tsv` and `out.dropped.tsv`.


## Sources

- JLPT lists: Jonathan Waller (tanos.co.uk, CC BY), via
  [stephenmk/yomitan-jlpt-vocab](https://github.com/stephenmk/yomitan-jlpt-vocab) (CC BY-SA 4.0).
- JMdict by the EDRDG, via [scriptin/jmdict-simplified](https://github.com/scriptin/jmdict-simplified) (CC BY-SA 4.0).
- Tokenizer: SudachiPy with sudachidict_core (Apache 2.0).


## License

The lists are CC BY-SA 4.0. The script is MIT. If you use the lists, please credit us with
this line:

    Data from learnfromx (https://learnfromx.com)
