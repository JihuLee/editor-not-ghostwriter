"""Generic candidate patterns for recurring usage slips in English academic prose.

find_slips.py runs these over the author's samples and shows each hit in context.
They are candidates only: Claude checks every hit in context, keeps the ones that are
real and recurring, and writes those to the author's watchlist. Nothing here is applied
automatically. Each entry: (label, regex, suggested fix, optional regex that the text
right before the match must NOT end with).
"""

CANDIDATES = [
    ("allow/enable/permit to + verb",
     r"\b(?:allow|allows|allowed|enable|enables|enabled|permit|permits|permitted)\s+to\s+[a-z]+",
     "allows us to ... / allows ...-ing", r"\b(?:is|are|was|were|be|been|being|not)\s*$"),
    ("despite of", r"\bdespite of\b", "despite / in spite of", None),
    ("discuss about", r"\bdiscuss(?:es|ed|ing)? about\b", "discuss", None),
    ("emphasize on", r"\bemphasi[sz](?:e|es|ed|ing) on\b", "emphasize", None),
    ("mention about", r"\bmention(?:s|ed|ing)? about\b", "mention", None),
    ("explain about", r"\bexplain(?:s|ed|ing)? about\b", "explain", None),
    ("comprise of", r"\bcompris(?:e|es) of\b", "comprise / consist of", None),
    ("uncountable noun in plural",
     r"\b(?:informations|advices|equipments|feedbacks|knowledges|softwares|hardwares|furnitures)\b",
     "singular (uncountable) form", None),
    ("less + countable plural",
     r"\bless (?:samples|sensors|parameters|iterations|steps|errors|points|images|examples|instances|features|"
     r"layers|nodes|users|items|words|papers|experiments|runs|epochs|queries|tokens|devices|files|cases)\b",
     "fewer", None),
    ("more + comparative", r"\bmore (?:better|faster|higher|lower|larger|smaller|easier|harder|simpler|cheaper|"
                           r"stronger|weaker|bigger)\b", "drop 'more'", None),
    ("most + superlative", r"\bmost (?:best|fastest|highest|lowest|largest|smallest|easiest|simplest)\b",
     "drop 'most'", None),
    ("in the other hand", r"\bin the other hand\b", "on the other hand", None),
    ("on the contrary to", r"\bon the contrary to\b", "contrary to", None),
    ("till now", r"\btill now\b", "so far / until now", None),
    ("run-together words", r"\b(?:upto|inspite|alot|aswell|eachother|infact|atleast|incase|everytime|"
                           r"inorder)\b", "two words", None),
    ("can able to", r"\bcan able to\b", "can / is able to", None),
    ("the both", r"\bthe both\b", "both", None),
    ("and etc.", r"\band etc\b", "etc.", None),
    ("for e.g.", r"\bfor e\.g\b", "e.g.", None),
    ("such as ... etc.", r"\bsuch as\b[^.;]{0,80}\betc\b", "drop 'etc.' after 'such as'", None),
    ("i.e / e.g without final period", r"\b(?:i\.e|e\.g)(?![.\w])", "i.e. / e.g.", None),
    ("as follow", r"\bas follow\b(?!s)", "as follows", None),
    ("the same with", r"\bthe same with\b", "the same as", None),
    ("similar with", r"\bsimilar with\b", "similar to", None),
    ("consist in", r"\bconsists? in\b", "consist of (unless 'lies in' is meant)", None),
    ("make an experiment", r"\bmak(?:e|es|ing) (?:an?|the) experiments?\b", "run / perform an experiment", None),
    ("in the last years", r"\bin the last years\b", "in recent years", None),
    ("since + duration", r"\bsince (?:two|three|four|five|several|many|\d+) (?:years|months|weeks|days)\b",
     "for ... (since takes a point in time)", None),
    ("explain + person without 'to'", r"\bexplain(?:s|ed)? (?:us|me|them|him|her)\b", "explain to us", None),
    ("a + vowel sound", r"\ba (?=(?-i:[aeio][a-z]{2,})\b)(?!one\b|once\b|eu)", "an", None),
    ("an + consonant sound", r"\ban (?=(?-i:[bcdfgjklmnpqrstvwxyz][a-z]{2,})\b)(?!h(?:our|onest|onou?r|eir))",
     "a", None),
    ("doubled word", r"\b(?!(?:that|had|MATH|REF|Author|CODE|URL)\b)([A-Za-z]+)\s+\1\b", "remove the repeat", None),
    ("despite + clause", r"\bdespite (?:the fact )?(?:it|we|they|this|there) (?:is|are|was|were|has|have)\b",
     "although ... / despite the fact that ...", None),
]
