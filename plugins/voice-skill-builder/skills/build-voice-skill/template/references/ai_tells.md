# AI tells

The lists live in `scripts/lexicon_en.py`; this file explains them. The author's own rates live in
`author_profile.json`, and every rule below is applied relative to them.

## Why these signals

Large studies of scientific text show that LLM use leaves population-level fingerprints: a burst of
specific "style words" after 2023 ("delves", "showcasing", "underscores", and more common ones such as
"crucial", "additionally", "comprehensive", "notably"; Kobak et al., arXiv:2406.07016), more em dashes in
preprints (Czuma, arXiv:2606.29540), and more polishing patterns such as connective phrasing, value framing
and contribution signalling. None of these proves anything about one text, but human reviewers notice the
same things, and these are exactly what an LLM edit adds to a human draft.

## Tier A (an edit that introduces one is reverted)

delve, showcase, underscore, unparalleled, invaluable, commendable, meticulous, realm, groundbreaking,
elucidate, tapestry, intricate, pivotal, "a testament to", "pave the way", "shed light", "plays a crucial /
pivotal / key ... role", "it is worth noting", "ever-evolving / rapidly evolving", "in today's", game-changer,
seamless(ly), multifaceted, holistic, nuanced, unwavering, embark, bolster, garner, myriad, plethora,
elevate, unlock, foster, heightened, boast, crucially, "in essence", "at its core", landscape (except
technical uses such as "loss landscape"), "navigate the/these ...".

A tier-A word that the author's own samples use twice or more is treated as tier B for this author.

## Tier B (judged against the author's own rate)

notably, importantly, additionally, furthermore, moreover, crucial, critical, essential, comprehensive,
leverage, utilize, enhance, insight(s), highlight, "emerge as", noteworthy, remarkable, intriguing,
surpass, streamline, harness, facilitate, "align with", effective(ly), valuable, versatile,
"robust framework/approach/...", novel, "not only ... but also", "not just / not merely".

The lint flags a tier-B word only when the draft uses it well above the author's rate; the guard warns when
an edit adds one.

## Structure

- **Em dashes** (`---`, the em dash character, spaced en dashes): a hard rule when the author's samples have
  fewer than 0.3 per 1,000 words; otherwise judged by rate. Contractions and exclamation marks work the same way.
- **AI-favoured openers**: Notably, Importantly, Crucially, Interestingly, Remarkably, Ultimately,
  Additionally, Furthermore, Moreover, Overall, In summary, In conclusion, Collectively, Taken together,
  In essence, Consequently, Indeed, In particular.
- **Summary closers**: a paragraph ending in "Overall, ...", "These results demonstrate ...",
  "This highlights ...", judged against how often the author does this.
- **Even rhythm**: sentences of near-identical length within a paragraph (within-paragraph variation below
  the author's 10th percentile).
- **Hedges and intensifiers** above the author's rates.

## Stylometry

The profile stores the author's function-word frequencies ("the", "of", "we", "that", "which", ...).
Burrows' Delta between a chunk of text and the profile measures how far the chunk's function-word usage is
from the author's; function words are hard to fake and change when someone else writes. The profile also
stores how far the author's own chunks sit from their average (median and 95th percentile). Treat this as
a document- or section-level signal, never as evidence about a single sentence.

## Limits

These are heuristics, tuned to catch what an editing pass adds, not to classify whole documents. A clean
lint does not certify a text as human, and a flag does not prove LLM use. Commercial detectors are known to
misread non-native English as machine text; comparing against the author's own writing avoids that bias.
