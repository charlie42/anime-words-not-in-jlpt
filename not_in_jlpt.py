import csv, glob, hashlib, io, json, os, re, statistics, sys, urllib.parse, urllib.request, zipfile
from collections import Counter, defaultdict
from sudachipy import Dictionary, SplitMode

# Jonathan Waller's JLPT N5-N1 lists (tanos.co.uk, CC BY), with JMdict ids added by stephenmk (CC BY-SA 4.0).
JLPT_URL = "https://raw.githubusercontent.com/stephenmk/yomitan-jlpt-vocab/b062d4e38c4bdd0950ae1d4ec55f04b176182e03/original_data/n{}.csv"
# JMdict (EDRDG, CC BY-SA 4.0) as JSON by scriptin/jmdict-simplified.
JMDICT_URL = "https://github.com/scriptin/jmdict-simplified/releases/download/3.6.2%2B20261102210542/jmdict-eng-3.6.2%2B20261102210542.json.zip"
JMDICT_SHA256 = "851791d3cc98a29ca7e4f65532966cdee637a1bc218cf1c99b4895b780edb101"
MIN_SHOWS, MIN_RATE = 4, 0.15         # in 4+ shows, at 0.15+ lines per 1,000 (averaged over the shows)
CAP = 3000                            # the first 3,000 lines with Japanese per show, episodes in order
SKIP_POS = {"補助記号", "空白", "記号", "接頭辞", "接尾辞"}
SKIP_SUB = {"固有名詞": "names", "数詞": "numbers"}
# Linking particles (が, を, に, て) are grammar. Sentence-final ones (ぜ, ぞ, わ) stay.
GRAMMAR_PARTICLES = {"格助詞", "係助詞", "副助詞", "接続助詞", "準体助詞"}
# Waller's lists have no grammar, so we drop the N5-N4 auxiliaries and grammar words by name.
TEXTBOOK_GRAMMAR = {"だ", "です", "ます", "た", "ない", "う", "よう", "たい", "れる", "られる", "せる", "させる",
                    "らしい", "そう", "みたい", "たがる", "しれる"}
# We keep a row only if it is slurred, has one of these labels, or its JMdict entry isn't marked common.
REGISTER = {"col", "sl", "vulg", "derog", "male", "fem", "rude", "arch", "dated", "fam", "net-sl", "joc"}
# Optional 4th argument: keep a slang spelling or use of a JLPT word.
RESCUES = {"katakana": "katakana spelling",  # ナメる for 舐める: Waller spells it in kanji or hiragana
           "verb": "after a verb"}  # まくる in 殴りまくる: a JLPT verb right after another verb's stem
# A clause ends at punctuation. Particles, auxiliaries and suffixes belong to the word before them.
PHRASE_BREAKS, PHRASE_ENDINGS = {"補助記号", "空白", "記号"}, {"助詞", "助動詞", "接尾辞"}
HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKLIST, ALLOWLIST = os.path.join(HERE, "blocklist.tsv"), os.path.join(HERE, "allowlist.tsv")
GENRE_WORDS, SENSES = os.path.join(HERE, "genre_words.tsv"), os.path.join(HERE, "senses.tsv")
NORMAL_FORMS = os.path.join(HERE, "normal_forms.tsv")
FIELDS = ["form", "most_heard_as", "other_forms", "normal_form", "reading", "pos", "meaning",
          "meaning_tags", "per_1000_lines", "count", "phrases", "shows", "link"]
TAG = re.compile(r"\{[^}]*\}|<[^>]*>|[（(][^)）]*[)）]|\[[^\]]*\]|［[^］]*］|【[^】]*】")
JP = re.compile(r"[ぁ-ヿ一-鿿々]")
KANJI = re.compile(r"[一-鿿々]")
KATA = re.compile(r"[ァ-ヺ]")
E_TO_U = dict(zip("えけげせぜてでねへべぺめれ", "うくぐすずつづぬふぶぷむる"))


STRETCH = re.compile(r"[ーっぁぃぅぇぉ〜～]|([あいうえおん])\1")
VOWEL_ROW = {c: v for v, row in zip("あいうえお", ("かさたなはまやらわがざだばぱゃ", "きしちにひみりぎじぢびぴ",
             "くすつぬふむゆるぐずづぶぷゅ", "けせてねへめれげぜでべぺ", "こそとのほもよろをごぞどぼぽょ")) for c in row + v}
LONG = {"あ": "あ", "い": "い", "う": "う", "え": "えい", "お": "おう"}  # after this vowel, these kana only lengthen it


def squash(s):  # はーい→はい, ねっ→ね, ねえ→ね, すっげー→すげ
    out = ""
    for c in re.sub(r"([あいうえおん])\1+", r"\1", re.sub(r"[ーっぁぃぅぇぉ〜～]", "", s)):
        if not (out and c in LONG.get(VOWEL_ROW.get(out[-1]), "")):
            out += c
    return out


def clean(t): return re.sub(r"\s+", " ", TAG.sub("", t).replace("\\N", " ")).strip()
def hira(s): return "".join(chr(ord(c) - 96) if "ァ" <= c <= "ヶ" else c for c in s)


GRAMMAR_SQUASHED = {squash(g) for g in TEXTBOOK_GRAMMAR}  # だぁ is a stretched だ


def fetch(url, path):
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def load_refs(ref):
    os.makedirs(ref, exist_ok=True)
    waller = defaultdict(set)  # JMdict id -> the readings Waller gives it (皆: みな, みんな)
    rows = []
    for n in range(1, 6):
        for r in csv.DictReader(open(fetch(JLPT_URL.format(n), f"{ref}/n{n}.csv"), encoding="utf-8")):
            waller[r["jmdict_seq"]].add(r["kana"])
            rows.append((r["kanji"], r["kana"]))
    path = fetch(JMDICT_URL, f"{ref}/jmdict.zip")
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == JMDICT_SHA256, "unexpected JMdict file"
    zf = zipfile.ZipFile(path)
    words = json.load(io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8"))["words"]
    entries = defaultdict(list)  # form -> JMdict entries listing it
    for w in words:
        w["kanji"] = [f for f in w["kanji"] if "sK" not in f["tags"]]  # drop search-only spellings (あぶねー)
        w["kana"] = [f for f in w["kana"] if "sk" not in f["tags"]]
        for f in w["kanji"] + w["kana"]:
            entries[f["text"]].append(w)
    jlpt_readings = defaultdict(set)  # JLPT spelling -> its readings (言う: いう, ゆう)
    for kanji, kana in rows:
        jlpt_readings[kanji or kana].add(kana)
        jlpt_readings[kana].add(kana)
    return waller, entries, jlpt_readings, {squash(r) for r in jlpt_readings}


# A line is a song lyric if it has a music symbol, is mostly English, or recurs across episodes like an OP/ED line.
MUSIC = set("♪🎵🎶♫♬")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
TIMES = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)")


def to_ms(h, m, s, f): return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(f)


def read_episode(path):  # -> [(start ms, end ms, line)]
    out = []
    for block in open(path, encoding="utf-8-sig").read().replace("\r", "").split("\n\n"):
        rows = [r for r in block.split("\n") if r]
        line, t = clean(" ".join(r for r in rows if "-->" not in r and not r.isdigit())), TIMES.search(block)
        if line:
            out.append((to_ms(*t.groups()[:4]), to_ms(*t.groups()[4:]), line) if t else (0, 0, line))
    return out


def too_much_english(t):  # mostly Latin letters and at least 2 English words: "Light it up Baby 燃やしちゃうぜ"
    latin = sum(c.isascii() and c.isalpha() for c in t)
    jp = sum("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in t)
    return latin + jp > 0 and latin / (latin + jp) > 0.3 and len(LATIN_WORD.findall(t)) >= 2


def recurring(eps):  # in 3 episodes in a row, 10+ times over 3+ episodes, or 5+ times in one of 2+ episodes
    n = Counter(eps)
    return (any(e + 1 in n and e + 2 in n for e in n) or len(n) >= 3 and sum(n.values()) >= 10
            or len(n) >= 2 and max(n.values()) >= 5)


def songs(episodes):  # -> the show's recurring song lines (5+ characters)
    where = defaultdict(list)
    for ep, rows in episodes.items():
        for _, _, t in rows:
            where[t].append(ep)
    found = {t for t, eps in where.items() if len(t) >= 5 and recurring(eps)}
    # Songs play at the same point of each episode. A line that recurs at varied points is a catchphrase, so it
    # stays (stdev of its position, as a share of the episode, above 0.10 over 3+ hits).
    at = defaultdict(list)
    for rows in episodes.values():
        length = max((e for _, e, _ in rows), default=0)
        if length > 60_000:  # a real episode, not a stub file
            for s, _, t in rows:
                if t in found:
                    at[t].append(s / length)
    return found - {t for t, p in at.items() if len(p) >= 3 and statistics.stdev(p) > 0.10}


def is_song(line, song_lines):
    return any(c in MUSIC for c in line) or too_much_english(line) or line in song_lines


def main(subs, ref, out, rescue=""):
    rescues = {RESCUES[r] for r in rescue.split(",") if r}
    refs = load_refs(ref)
    tok = Dictionary().create()
    reading = {}
    def lemma_reading(lemma):
        if lemma not in reading:
            reading[lemma] = hira("".join(m.reading_form() for m in tok.tokenize(lemma, SplitMode.C)))
        return reading[lemma]
    def split(lemma):
        return [(m.dictionary_form(), m.part_of_speech()[0]) for m in tok.tokenize(lemma, SplitMode.A)]

    lines, hits, dropped, heard = Counter(), defaultdict(set), defaultdict(Counter), defaultdict(Counter)
    phrases = defaultdict(Counter)  # key -> phrase -> lines containing it
    chunks, last_ep, lyrics = hand_list(BLOCKLIST, "chunk"), {}, Counter()
    for show_dir in sorted(glob.glob(f"{subs}/raw/*")):
        show = os.path.basename(show_dir)
        episodes = {int(os.path.basename(p)[:-4]): read_episode(p) for p in glob.glob(f"{show_dir}/*.bin")}
        song_lines = songs(episodes)  # over the whole show, before the line cap
        for ep in sorted(episodes):
            if lines[show] >= CAP:
                break
            for *_, line in episodes[ep]:
                if lines[show] >= CAP:
                    break
                if is_song(line, song_lines):
                    lyrics[show] += bool(JP.search(line))
                    continue
                last_ep[show] = str(ep)
                seen, prev, said = set(), None, set()
                inside = in_chunk(line, chunks)
                ms = list(tok.tokenize(line, SplitMode.C))
                for i, m in enumerate(ms):
                    pos = m.part_of_speech()
                    why = ("symbols and affixes" if pos[0] in SKIP_POS else SKIP_SUB.get(pos[1])
                           or ("no Japanese" if not JP.search(m.surface()) else None)
                           or ("unknown to Sudachi" if m.is_oov() else None))  # mostly laughs and gasps
                    after_verb = pos[0] == "動詞" and prev is not None and prev[0] == "動詞" and prev[5].startswith("連用形")
                    prev = pos
                    why = why or ("in a textbook chunk" if inside(m) else None)
                    if why:
                        dropped[why][m.surface()] += 1
                        continue
                    key = (m.dictionary_form(), m.normalized_form(), pos[0], pos[1], after_verb)
                    seen.add(key)
                    heard[key][m.surface()] += 1
                    said.add((key, phrase(ms, i)))
                for key, p in said:  # counted once per line
                    phrases[key][p] += 1
                lines[show] += bool(JP.search(line))  # the denominator counts lines with Japanese
                for key in seen:  # counted once per line
                    hits[key].add((show, sum(lines.values())))
    rows = classify(hits, heard, phrases, lines, refs, lemma_reading, split, dropped, rescues)
    genre = hand_list(GENRE_WORDS)
    is_genre = {id(r) for r in rows if any((r["form"], p) in genre for p in r["pos"].split())}  # before forms are renamed
    rows = add_meanings(rows, refs[1], lemma_reading)
    write([r for r in rows if id(r) not in is_genre], out, lines, dropped)
    write_rows([r for r in rows if id(r) in is_genre], out.rsplit(".", 1)[0] + ".genre.tsv")
    print("last episode used:", last_ep)
    print("song lines left out per show (lines with Japanese):", dict(lyrics))


def hand_rows(path):  # the fields of each row below the header
    return [r.split("\t") for r in open(path, encoding="utf-8").read().splitlines()[1:] if r]


def hand_list(path, pos=None):  # {(form, pos)}, or the forms with this part of speech
    rows = hand_rows(path)
    return {(r[0], r[1]) for r in rows} if pos is None else {r[0] for r in rows if r[1] == pos}


def add_meanings(rows, entries, lemma_reading):  # meaning = the JMdict sense(s) picked in senses.tsv
    picks = {r[0]: r[1:4] for r in hand_rows(SENSES)}
    missing = [r["form"] for r in rows if r["form"] not in picks]
    if missing:
        sys.exit(f"no sense picked in senses.tsv for {len(missing)} rows: {' '.join(missing)}")
    by_id, used = {w["id"]: w for ws in entries.values() for w in ws}, {r["form"] for r in rows}
    for r in rows:
        eid, ns, shown = picks[r["form"]]
        w, ns = by_id.get(eid), ns.split(",")
        if not w or not all(n.isdigit() and 1 <= int(n) <= len(w["sense"]) for n in ns):
            sys.exit(f"senses.tsv: no sense {','.join(ns)} in JMdict entry {eid} (row {r['form']})")
        senses = [w["sense"][int(n) - 1] for n in ns]
        r.update(meaning=" / ".join("; ".join(g["text"] for g in s["gloss"]) for s in senses),
                 meaning_tags=" ".join(dict.fromkeys(t for s in senses for t in s["misc"] + s["dialect"])))
        if shown:  # shown in place of the tokenizer's form (どん -> どんだけ)
            r.update(form=shown, reading=lemma_reading(shown),
                     link="https://jisho.org/search/" + urllib.parse.quote(shown))
        elif KANJI.search(r["form"]) and r["reading"] not in {hira(k["text"]) for k in w["kana"]}:
            # Sudachi's reading of a lone kanji can be its reading in compounds (民: みん); the entry's is たみ
            r["reading"] = hira(w["kana"][0]["text"])
    print("unused senses.tsv rows:", " ".join(sorted(set(picks) - used)) or "none")
    return rows


def in_chunk(line, chunks):  # -> test: is this token inside a heard chunk (ん in すみません)?
    spans = [(i, i + len(c)) for c in chunks for i in range(len(line)) if line.startswith(c, i)]
    return lambda m: any(a <= m.begin() and m.end() <= b for a, b in spans)


def finish(seg, e):  # extend to the end of a conjugated word: なっちまっ -> なっちまった
    while e + 1 < len(seg) and seg[e + 1].part_of_speech()[0] in PHRASE_ENDINGS and \
            not seg[e].part_of_speech()[5].startswith(("終止形", "命令形", "連体形", "*")):
        e += 1
    return e


def phrase(ms, i):  # the short chunk around token i, as written: そうっす, なっちまった, こいつは, いるんだ
    st = max([k + 1 for k in range(i) if ms[k].part_of_speech()[0] in PHRASE_BREAKS], default=0)
    en = next((k for k in range(i, len(ms)) if ms[k].part_of_speech()[0] in PHRASE_BREAKS), len(ms)) - 1
    seg, i = ms[st:en + 1], i - st  # the clause between punctuation marks
    tags = [m.part_of_speech()[0] for m in seg]
    head = max(k for k in range(i + 1) if k == 0 or tags[k] not in PHRASE_ENDINGS)
    if len(seg) == 1:  # the form is the whole clause: そりゃ…
        a, b = 0, 0
    elif tags[i] in PHRASE_ENDINGS and head < i:  # an ending: from the word it hangs on (そう + っす)
        a, b = head, i
    elif i + 1 < len(seg):  # a word: plus what follows it (こいつ + は, 勝手に + しろ)
        a, b = i, i + 1
    else:  # a word at the end of its clause: plus the word before it
        a, b = i - 1, i
    if b + 1 < len(seg) and tags[b + 1] == "助動詞" and seg[b].part_of_speech()[5] == "*":
        b += 1  # いるん + だ
    b = finish(seg, b)
    a -= a > 0 and tags[a - 1] == "接頭辞"  # お + さらば
    return "".join(m.surface() for m in seg[a:b + 1])


def on_jlpt(lemma, waller, entries, jlpt_readings, rd=None):
    if lemma in jlpt_readings:
        return "on JLPT"
    # JMdict lists it under a JLPT entry, read the way Waller reads it (かしら is also a reading of 頭, あたま)
    if any(w["id"] in waller and (rd is None or rd in waller[w["id"]]) for w in entries.get(lemma, [])):
        return "spelling variant"
    return None


def rescue_rule(lemma, normal, pos, after_verb, waller, entries, rescues):
    if "after a verb" in rescues and after_verb and pos == "動詞":
        return "after a verb"
    if "katakana spelling" in rescues and KATA.search(lemma) and not KANJI.search(lemma):
        ids = {w["id"] for f in (lemma, normal) for w in entries.get(f, []) if w["id"] in waller}
        if not any(KATA.search(r) for i in ids for r in waller[i]):  # Waller doesn't spell it in katakana
            return "katakana spelling"
    return ""


def drop_reason(key, rd, refs, lemma_reading, split, rescues):  # -> (why dropped or None, rescue rule that kept it)
    lemma, normal, pos, sub, after_verb = key
    waller, entries, jlpt_readings, jlpt_squashed = refs
    if sub in GRAMMAR_PARTICLES:
        return "grammar particles", ""
    if lemma in TEXTBOOK_GRAMMAR:
        return "textbook grammar", ""
    rescue = rescue_rule(lemma, normal, pos, after_verb, waller, entries, rescues)
    found = on_jlpt(lemma, waller, entries, jlpt_readings, rd)
    if found and not (rescue == "after a verb" or rescue and found == "spelling variant"):
        return found, ""
    rescued = rescue if found else ""
    # JMdict lists キレる apart from 切れる, but ヤツ under 奴.
    own_entry = lemma in entries and not any(normal in {f["text"] for f in w["kanji"] + w["kana"]} for w in entries[lemma])
    if normal != lemma and on_jlpt(normal, waller, entries, jlpt_readings):
        for nrd in sorted(jlpt_readings.get(normal, set()) | {lemma_reading(normal)}):
            if rd == nrd and not own_entry:
                if not rescue:
                    return "spelling variant", ""
                rescued = rescue
            elif rd != nrd and squash(rd) == squash(nrd):
                return "stretched/clipped", ""
            elif pos == "動詞" and rd[-1:] == "る" and len(rd) >= 2 and nrd == rd[:-2] + E_TO_U.get(rd[-2], "?"):
                return "potential form", ""
    if STRETCH.search(rd) and not KANJI.search(lemma) and squash(rd) in (GRAMMAR_SQUASHED if pos == "助動詞" else jlpt_squashed):
        return "stretched/clipped", ""
    if pos in ("感動詞", "副詞") and lemma not in entries and rd not in entries:
        return "sounds not in JMdict", ""
    parts = split(lemma)
    if pos in ("名詞", "代名詞") and len(parts) > 1 and all(
            p[1] in ("接尾辞", "接頭辞") or on_jlpt(p[0], waller, entries, jlpt_readings) for p in parts):
        return "compound of JLPT words", ""
    return None, rescued


def sounds_different(form, normal, refs, lemma_reading):  # ねえ for ない: the normal form, else ""
    normal_readings = {lemma_reading(normal)} | {hira(k["text"]) for w in refs[1].get(normal, []) for k in w["kana"]}
    return normal if squash(lemma_reading(form)) not in {squash(r) for r in normal_readings} else ""


def merge_spellings(groups, refs, lemma_reading, merged):
    # ねえ under ない and under 無い is one JMdict word, so one row. Slurred rows only: ねえ (older sister)
    # and ねえ (hey) are different words.
    owner = {}  # (squashed reading, rescue, JMdict id) -> the group that keeps it
    for key in sorted(groups, key=lambda k: (-len(groups[k]["lines"]), k)):
        normal, sq, rescue = key
        g = groups[key]
        if not sounds_different(g["forms"].most_common(1)[0][0], normal, refs, lemma_reading):
            continue
        ids = sorted({w["id"] for w in refs[1].get(normal, [])})
        target = next((owner[(sq, rescue, i)] for i in ids if (sq, rescue, i) in owner), None)
        if target is None:
            owner.update({(sq, rescue, i): key for i in ids})
            continue
        for field in ("forms", "pos", "heard", "phrases"):
            groups[target][field].update(g[field])
        groups[target]["lines"] |= g["lines"]
        groups[target]["normals"].update(g["normals"])
        merged.append(f"{normal} into {target[0]}")
        del groups[key]


def classify(hits, heard, phrases, lines, refs, lemma_reading, split, dropped, rescues):
    groups = defaultdict(lambda: {"lines": set(), "forms": Counter(), "pos": Counter(), "heard": Counter(),
                                  "normals": Counter(), "phrases": Counter()})
    for key, where in hits.items():
        lemma, normal, pos = key[:3]
        rd = lemma_reading(lemma)
        why, rescued = drop_reason(key, rd, refs, lemma_reading, split, rescues)
        if why:
            dropped[why][lemma] += len(where)
            continue
        g = groups[(normal, squash(rd), rescued)]  # すげえ / すげー / すっげえ share one row
        g["lines"] |= where
        for field, value in (("forms", lemma), ("pos", pos), ("normals", normal)):
            g[field][value] += len(where)
        g["heard"].update(heard[key])
        g["phrases"].update(phrases[key])
    merged = []
    merge_spellings(groups, refs, lemma_reading, merged)
    print("merged rows:", "; ".join(merged) or "none")
    hand = hand_list(BLOCKLIST), hand_list(ALLOWLIST), {r[0]: r[1].strip("-") for r in hand_rows(NORMAL_FORMS)}
    rows = [r for key, g in groups.items() if (r := make_row(key, g, lines, refs, lemma_reading, dropped, hand))]
    print("rows before same-form merge:", len(rows))
    rows = [r for r in merge_same_form(rows, lines) if above_threshold(r, dropped)]
    return sorted(rows, key=lambda r: (-r["per_1000_lines"], r["form"], r["pos"]))


def above_threshold(r, dropped):  # checked after the same-form merge, on the merged row's shows and unrounded rate
    rate = r.pop("rate")
    if r["shows"] >= MIN_SHOWS and rate >= MIN_RATE:
        return True
    dropped["below threshold"][r["form"]] += r["count"]
    return False


def make_row(key, g, lines, refs, lemma_reading, dropped, hand):
    normal, _, rescued = key
    shows = Counter(show for show, _ in g["lines"])
    rate = sum(shows[s] * 1000 / lines[s] for s in lines) / len(lines)
    form = g["forms"].most_common(1)[0][0]
    rd = lemma_reading(form)
    blocked, allowed, fixed_normals = hand
    normal_form = fixed_normals.get(form, " ".join(n for n, _ in g["normals"].most_common()
                                                 if sounds_different(form, n, refs, lemma_reading)))
    tags = labels(form, rd, refs[1])
    kept_by = [k for k, ok in (("slurred", normal_form), ("register", REGISTER & set(tags)),
                               ("uncommon", not is_common(form, rd, refs[1])), (rescued, rescued)) if ok]
    pos = g["pos"].most_common(1)[0][0]
    why = ("common word, no label" if not kept_by  # 顔, 霊, 魔力
           else "interjection, only uncommon" if pos == "感動詞" and kept_by == ["uncommon"] and (form, pos) not in allowed  # うっ, ハハハ, へえ
           else "blocklist" if (form, pos) in blocked else None)
    if why:
        dropped[why][form] += len(g["lines"])
        return None
    top = sorted(g["phrases"].items(), key=lambda x: (-x[1], x[0]))[:3]
    return dict(form=form, kind=kept_by[0], kept_by=" ".join(kept_by), most_heard_as=g["heard"].most_common(1)[0][0],
                other_forms=" ".join(f for f in g["forms"] if f != form), normal_form=normal_form, reading=rd,
                pos=pos, per_1000_lines=round(rate, 2), count=len(g["lines"]),
                phrases=" ".join(f"{p}({n})" for p, n in top), shows=len(shows), link="https://jisho.org/search/" + urllib.parse.quote(form),
                group=g)


def merge_same_form(rows, lines):  # ねえ as 感動詞 and 名詞 become one row
    by_form = defaultdict(list)
    for r in sorted(rows, key=lambda r: -r["count"]):
        by_form[r["form"]].append(r)
    out = []
    for form, rs in by_form.items():
        r, gs = dict(rs[0]), [x.pop("group") for x in rs]
        g = {"lines": set().union(*(g["lines"] for g in gs)), "pos": sum((g["pos"] for g in gs), Counter()),
             "heard": sum((g["heard"] for g in gs), Counter()), "phrases": sum((g["phrases"] for g in gs), Counter())}
        shows = Counter(show for show, _ in g["lines"])
        rate = sum(shows[s] * 1000 / lines[s] for s in lines) / len(lines)
        top = sorted(g["phrases"].items(), key=lambda x: (-x[1], x[0]))[:3]
        union = lambda col: " ".join(dict.fromkeys(w for x in rs for w in x[col].split()))
        r.update(pos=" ".join(p for p, _ in g["pos"].most_common()), most_heard_as=g["heard"].most_common(1)[0][0],
                 rate=rate, per_1000_lines=round(rate, 2), count=len(g["lines"]),
                 phrases=" ".join(f"{p}({n})" for p, n in top), shows=len(shows), kept_by=union("kept_by"),
                 other_forms=union("other_forms"), normal_form=union("normal_form"))
        r["kind"] = r["kept_by"].split()[0]
        r.pop("group", None)
        out.append(r)
    return out


def matching_entries(form, rd, entries):
    return [w for w in entries.get(form, []) if any(hira(k["text"]) == rd for k in w["kana"])] or entries.get(form, [])


def labels(form, rd, entries):
    return sorted({m for w in matching_entries(form, rd, entries) for s in w["sense"] for m in s["misc"]})


def is_common(form, rd, entries):  # jmdict-simplified "common": a news1/ichi1/spec1/spec2/gai1 tag on any spelling
    return any(f["common"] for w in matching_entries(form, rd, entries) for f in w["kanji"] + w["kana"])


def write_rows(rows, out):
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")  # leaves out kind, kept_by
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


def write(rows, out, lines, dropped):
    write_rows(rows, out)
    print("lines per show:", dict(lines))
    with open(out.rsplit(".", 1)[0] + ".dropped.tsv", "w", encoding="utf-8") as f:
        f.write("reason\tform\tline_hits\n")
        f.writelines(f"{why}\t{form}\t{n}\n" for why, c in sorted(dropped.items())
                     for form, n in sorted(c.items(), key=lambda x: (-x[1], x[0])))
    print("dropped: class, distinct forms, line hits (tokens for the first four), top examples")
    for why, c in sorted(dropped.items(), key=lambda x: -sum(x[1].values())):
        print(f"  {why}\t{len(c)}\t{sum(c.values())}\t{' '.join(f for f, _ in c.most_common(12))}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
