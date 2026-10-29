"""English lexicon for AI-tell detection and style measurement (data only).

Tier A  - words and constructions that careful human academic prose rarely uses and
          that became far more frequent in scientific text after LLM chat assistants
          appeared. An edit that introduces one is reverted, unless the author's own
          samples use the word (then it is judged like tier B).
Tier B  - ordinary words that LLMs overuse. Judged against the author's own rate.
Openers - sentence-initial transitions LLMs favour; also judged against the author.

To support another language, copy this file (e.g. lexicon_de.py), translate the lists,
and see docs/adding-a-language.md. Patterns are case-insensitive regular expressions.
"""

TIER_A = {
    "delve": r"\bdelv(?:e|es|ed|ing)\b",
    "showcase": r"\bshowcas(?:e|es|ed|ing)\b",
    "underscore": r"\bunderscor(?:e|es|ed|ing)\b",
    "unparalleled": r"\bunparalleled\b",
    "invaluable": r"\binvaluable\b",
    "commendable": r"\bcommendabl[ey]\b",
    "meticulous": r"\bmeticulous(?:ly)?\b",
    "realm": r"\brealms?\b",
    "groundbreaking": r"\bground-?breaking\b",
    "elucidate": r"\belucidat(?:e|es|ed|ing)\b",
    "tapestry": r"\btapestr(?:y|ies)\b",
    "intricate": r"\bintricat(?:e|ely|acy|acies)\b",
    "pivotal": r"\bpivotal\b",
    "a testament to": r"\ba testament to\b",
    "pave the way": r"\bpav(?:e|es|ed|ing) the way\b",
    "shed light": r"\bsh(?:ed|eds|edding) (?:new |some |more )?light\b",
    "plays a ... role": r"\bplay(?:s|ed|ing)? (?:a|an) (?:crucial|pivotal|vital|key|central|critical|significant|"
                        r"important|fundamental|major) role\b",
    "it is worth noting": r"\bit(?:'s| is) (?:worth|important to) not(?:e|ing)\b|\bworth mentioning\b",
    "ever-evolving": r"\bever[- ](?:evolving|changing|growing|increasing)\b",
    "rapidly evolving": r"\brapidly evolving\b",
    "in today's": r"\bin today's\b",
    "game-changer": r"\bgame[- ]chang(?:er|ers|ing)\b",
    "seamless": r"\bseamless(?:ly)?\b",
    "multifaceted": r"\bmulti-?faceted\b",
    "holistic": r"\bholistic(?:ally)?\b",
    "nuanced": r"\bnuanced\b",
    "unwavering": r"\bunwavering\b",
    "embark": r"\bembark(?:s|ed|ing)?\b",
    "bolster": r"\bbolster(?:s|ed|ing)?\b",
    "garner": r"\bgarner(?:s|ed|ing)?\b",
    "myriad": r"\bmyriad\b",
    "plethora": r"\bplethora\b",
    "elevate": r"\belevat(?:e|es|ing)\b",
    "unlock": r"\bunlock(?:s|ed|ing)?\b",
    "foster": r"\bfoster(?:s|ed|ing)?\b",
    "heightened": r"\bheightened\b",
    "boast": r"\bboast(?:s|ed|ing)?\b",
    "crucially": r"\bcrucially\b",
    "in essence": r"\bin essence\b",
    "at its core": r"\bat (?:its|their) core\b",
    "landscape (figurative)": r"(?<!loss )(?<!energy )(?<!fitness )(?<!optimization )(?<!error )\blandscapes?\b",
    "navigate (figurative)": r"\bnavigat(?:e|es|ed|ing) (?:the|this|these|complex|such)\b",
}

TIER_B = {
    "notably": r"\bnotably\b",
    "importantly": r"\bimportantly\b",
    "additionally": r"\badditionally\b",
    "furthermore": r"\bfurthermore\b",
    "moreover": r"\bmoreover\b",
    "crucial": r"\bcrucial\b",
    "critical": r"\bcritical(?:ly)?\b",
    "essential": r"\bessential(?:ly)?\b",
    "comprehensive": r"\bcomprehensive(?:ly)?\b",
    "leverage": r"\bleverag(?:e|es|ed|ing)\b",
    "utilize": r"\butili[sz](?:e|es|ed|ing|ation)\b",
    "enhance": r"\benhanc(?:e|es|ed|ing|ement|ements)\b",
    "insight": r"\binsights?\b",
    "highlight": r"\bhighlight(?:s|ed|ing)?\b",
    "emerge as": r"\bemerg(?:e|es|ed|ing) as\b",
    "noteworthy": r"\bnoteworthy\b",
    "remarkable": r"\bremarkabl[ey]\b",
    "intriguing": r"\bintriguing(?:ly)?\b",
    "surpass": r"\bsurpass(?:es|ed|ing)?\b",
    "streamline": r"\bstreamlin(?:e|es|ed|ing)\b",
    "harness": r"\bharness(?:es|ed|ing)?\b",
    "facilitate": r"\bfacilitat(?:e|es|ed|ing)\b",
    "align with": r"\balign(?:s|ed)? (?:well )?with\b",
    "effective": r"\beffective(?:ly|ness)?\b",
    "valuable": r"\bvaluable\b",
    "versatile": r"\bversatil(?:e|ity)\b",
    "robust (non-technical)": r"\brobust(?:ly)? (?:framework|approach|solution|foundation|performance)\b",
    "novel": r"\bnovel\b",
    "not only ... but also": r"\bnot only\b[^.;]{0,150}?\bbut(?: also)?\b",
    "not just / not merely": r"\bnot (?:just|merely|simply)\b",
}

AI_OPENERS = [
    "notably", "importantly", "crucially", "interestingly", "remarkably", "ultimately",
    "additionally", "furthermore", "moreover", "overall", "in summary", "in conclusion",
    "collectively", "taken together", "in essence", "consequently", "indeed", "in particular",
]

# sentence-initial discourse markers counted in the author profile
CONNECTIVES = [
    "however", "thus", "hence", "therefore", "then", "note that", "that is", "in particular",
    "specifically", "moreover", "furthermore", "additionally", "also", "in addition", "for example",
    "for instance", "in other words", "in turn", "as a result", "consequently", "finally", "first",
    "second", "third", "overall", "in summary", "in short", "to this end", "to that end",
    "on the other hand", "in contrast", "by contrast", "similarly", "likewise", "indeed", "importantly",
    "notably", "interestingly", "here", "next", "now", "still", "yet", "instead", "otherwise",
    "meanwhile", "accordingly", "put differently", "in practice", "in fact", "of course", "clearly",
    "nevertheless", "nonetheless", "conversely", "alternatively", "as such", "to be more specific",
    "more precisely", "concretely", "in what follows", "we stress that", "recall that", "observe that",
    "for simplicity", "without loss of generality", "intuitively", "formally", "in this section",
    "in this paper", "in this work", "to summarize", "to conclude", "in conclusion", "taken together",
    "collectively", "ultimately", "crucially", "remarkably", "fortunately", "unfortunately",
    "surprisingly", "of note", "as expected", "in general", "in this case", "to see this", "to do so",
    "as a consequence", "to be safe", "for completeness", "in turn", "by construction", "in our experiments",
]

SUMMARY_CLOSER = (r"^(?:overall|in summary|in conclusion|in short|taken together|together|collectively|ultimately|"
                  r"these (?:results|findings|observations|experiments) (?:show|demonstrate|suggest|confirm|indicate|"
                  r"highlight)|this (?:highlights|underscores|demonstrates|showcases|confirms|emphasizes|illustrates))\b")

HEDGE = (r"\b(?:may|might|could|possibly|potentially|likely|perhaps|arguably|appears? to|seems? to|tends? to)\b")
INTENSIFIER = (r"\b(?:significantly|substantially|considerably|remarkably|highly|greatly|clearly|consistently|"
               r"dramatically|markedly|notably|effectively|successfully|extremely|truly|particularly)\b")
CONTRACTION = (r"\b(?:it's|that's|there's|we're|we've|we'll|let's|isn't|aren't|don't|doesn't|didn't|can't|"
               r"won't|wouldn't|shouldn't|couldn't|haven't|hasn't)\b")
PASSIVE = (r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(?:\w+ed|shown|given|done|known|seen|made|"
           r"written|chosen|taken|drawn|found|run|set|put|kept|built|left|led|held)\b")
TRIAD = r"\b[A-Za-z-]+, [A-Za-z-]+,? and [A-Za-z-]+\b"
FIRST_PERSON = r"\b(?:we|our|us)\b"

FUNCTION_WORDS = [
    "the", "of", "and", "to", "a", "in", "is", "that", "for", "we", "with", "as", "by", "on",
    "be", "are", "this", "which", "it", "from", "an", "can", "not", "or", "at", "has", "have",
    "our", "its", "when", "than", "these", "such", "also", "each", "all", "but", "if", "then",
    "where", "while", "so", "there", "their", "only", "any", "both", "more", "most", "under",
    "between", "into", "since", "however", "thus", "hence", "here", "would", "will", "may",
    "could", "should", "been", "was", "were", "does", "do", "other", "same", "very", "well",
    "how", "what", "whether", "because", "although", "even", "much", "many", "some", "without",
    "within", "via", "further", "first",
]
