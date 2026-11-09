[Manual](../MANUAL.md) › Glossary

# Words used in Margin

The app speaks plain language; the command line, the API and the code use technical names. Both are listed here.

| In the app | Technical name | Meaning |
| --- | --- | --- |
| **Project** | Project, workspace | A folder with `config.json` and `enlens.sqlite` (the database keeps the ENLENS name). The app keeps its projects in `~/margin/projects` (or `MARGIN_HOME`); the command line works on any folder given with `--ws`. Both use the same format. |
| **Document** | Document | One source file (PDF, Word .docx, HTML, TXT or MD; zips are opened). Its text is stored once, and every place in it points into that text. Its paragraphs and headings are kept, so a quote can be cited as "paragraph 6 of 8" (text and web pages) or "page 2, paragraph 3" (PDFs). Scanned pages can be read by text recognition (OCR). |
| **Excerpt**, **passage** | Passage | A paragraph of a document (long ones cut, short ones put together; up to about 1,100 characters, some 180 words). Excerpts are what the AI reads. Reference lists, page furniture and unreadable text are left out ([How documents are read](reading.md)). |
| **Hypothesis** | Hypothesis | What you check. Checked as written, or split into 2 to 5 *parts* that must all hold, each checked on its own. |
| **Part** | Claim | One statement that is checked: the hypothesis itself, or one of its parts. |
| **Judgement** | Grade, verdict | What the AI says about one excerpt: *supports*, *partly supports* (an important part is stated; something remains to be inferred), *contradicts* (`refutes`), or *not about this hypothesis*. With a quote and a certainty. |
| **Your judgement** | User verdict | Your own judgement of an excerpt. It replaces the AI's in the answer and the counts, always counts, and is kept next to the AI's. Agreeing with the AI is a review; choosing another judgement is a change. You can point to the sentence you mean. |
| **Answer** | Status | What the documents say about the whole hypothesis: *supported*, *partly supported*, *mixed evidence* (`contested`), *contradicted*, and the rest ([The answers](check.md#the-answers)). |
| **AI certainty** | Confidence | The AI's own estimate (0–100%) of how sure it is: high (≥ 80%), medium (≥ 60%), low. Not a check of whether it is right. |
| **Strictness** | Threshold | How sure the AI must be for a judgement to count (default 60%). Weaker judgements stay visible, marked *Not counted*. It applies to every result, old and new. |
| **Search** (in a check) | Round | One set of excerpts read for a part. *Read more excerpts* and *Search with other words* add searches. |
| **Search by meaning** | Semantic index | Optional: a vector per excerpt from a local embedding model, so excerpts are found by meaning as well as by shared words. |
| **About another group** | Scope note | The AI's note that an excerpt is about another group, setting, place or period than the hypothesis names ("about fully remote workers, not hybrid"). Such an excerpt supports the hypothesis at most partly. |
| **Second opinion** | Model for second opinions | Another model that reads the same excerpts on its own, to show where it differs. Its judgements never change an answer. |
| **Stronger model** | Model routing (*Steps up to*) | The model a check steps up to: it reads the excerpts again and its judgements replace the first ones; the answer shows what it was at first. |
| **The auditor** | Auditor | The model for second opinions and hard cases on Claude: Opus, or Fable when switched on. |
| **Codebook** | Framework | An optional list of codes (like codes in NVivo or Atlas.ti). Margin has no default: you choose one in the app. Built-in ones include social practice theory and the SDG targets; add your own as a CSV. The AI sees each code's text. |
| **Code**, **label** | Code, label | One entry of a codebook; a label says that a passage addresses it. |
| **Reader** | Reader | The part of Margin that turns a file into text and passages. Every document records which reader read it. |
| **Who may read with AI** | `ai_access` | A document's setting: *Claude may read it* (`cloud`), *Only a local AI* (`local`), *No AI* (`none`) ([Privacy](privacy.md#who-may-read-each-document-with-ai)). |
| **Draft** | Text, draft | Your own writing, pasted or loaded in *Check a draft*. It is kept apart from the documents and is never used as evidence ([Check a draft](drafts.md)). |
| **A claim of a draft** | Draft claim | A statement of your draft the AI marked (or you marked) as one a reader would want a source for. Each is checked against your documents as a hypothesis of its own. |
| **A claim that needs a source** | Uncited claim | A claim for which your draft cites nothing. Once you mark it supported or refuted, it gets the tag *cite here* where the citation goes; a claim your draft already cites gets *cited*. |
| **Your verdict** | Verdict on a claim | Your decision on a claim of a draft: *Supported*, *Refuted* or *Dismiss*. It belongs to the draft and does not change the claim's result. |
| **Citation** | Citation | A reference in your text such as *(Smith, 2020)* or *[3]*, matched with a work of the bibliography and checked against that work's document ([Check citations](citations.md)). |
| **Source accurate** | Citation check | The answer to a citation whose source says what your sentence says ([The answers](citations.md#the-answers)). |
| **Bibliography** | Bibliography | The works you cite, from Zotero or a file exported from a reference manager, each linked to a document when it is in the project ([Your bibliography](bibliography.md)). |
| **Outline** | Outline | A plan to write from, made without AI from a research question or from all the themes ([Make an outline](outline.md)). |
| **Skim** | Skim report | A one-page report on one document, made without AI, to decide whether to read it ([Skim one document](skim.md)). |
| **Find literature** | Literature search | A search of online sources (OpenAlex, Crossref, Semantic Scholar, Unpaywall) for works you do not have yet ([Find literature](literature.md)). |
| **Theme** | Theme | What the documents are about, grouped by their passages' meaning or terms; the same documents and settings always give the same themes ([Explore your documents](explore.md#themes)). |
| **Concept** | Concept | A term the documents use (one or more words), with its wordings, documents and related concepts ([Explore your documents](explore.md#concepts)). |
| **Profile** | Document profile | Which codes of a codebook a document addresses, how much and where ([Explore your documents](explore.md#profile)). |
| **Check several** | Batch | Many hypotheses checked one after the other from a list or CSV ([Check a hypothesis](check.md#checking-many-at-once)). |
| **Who says what** | Sides | The documents behind an answer, by side: supporting, partly supporting, contradicting ([Check a hypothesis](check.md#who-says-what)). |
| **Mixed evidence** | `contested` | Some excerpts support the hypothesis and others contradict it. |
| **Evidence map** | Map | All results as a grid of hypotheses by documents, with + (supports), (+) (partly), − (contradicts) and ± (both) ([Read and review a result](review.md#all-your-results)). |
| **The queue** | Task queue | The AI work Margin has prepared for Claude Code, answered by helpers ([Claude Code](claude-code.md)). |
