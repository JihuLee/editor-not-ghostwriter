# Adding a language

The engine is English-only today. The parts that depend on the language are small and isolated:

| File | What is English-specific |
|---|---|
| `template/scripts/lexicon_en.py` | tier-A/tier-B words, AI-favoured openers, connectives, hedges, intensifiers, contractions, passive pattern, function words |
| `template/scripts/textcore.py` | `WORD_RE` (Latin letters), the abbreviation list, the sentence-boundary pattern (`.`, `!`, `?` followed by a capital) |
| `scripts/esl_candidates.py` | usage-slip candidates for English as a second language |

To add a language:

1. Copy `lexicon_en.py` to `lexicon_<code>.py` and fill every list with evidence-based entries for that
   language. Tier A should hold only words with a documented post-LLM surge in that language's academic
   writing; when in doubt, put a word in tier B, which is judged against the author's own rate.
2. Make `tells.py` load the lexicon named by the profile's `language` field instead of importing
   `lexicon_en` directly, and let `style_profile.py` take `--language`.
3. Languages without spaces between words (Chinese, Japanese) or without capital letters after a full stop
   (Chinese, Japanese, Korean) need a language-specific word pattern and sentence splitter in
   `textcore.py`. Where grammatical particles attach to words (Korean, Japanese), function-word
   stylometry needs a list of particles rather than separate function words.
4. Add a fictional demo author in that language under `examples/` and tests mirroring the English ones.

Please do not copy real people's writing into the repository as fixtures; write synthetic samples.
