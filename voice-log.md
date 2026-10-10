# Voice log

## 0 · 2026-10-10 14:21 +0530
words 179 · spoken 110s · typed 268s

> what's up? New project called Kirana. Make a Claude.md with these rules:
> 1. Log every prompt in voice: log.md, word for word, with timestamp, word count, and the second I took to say it (typing time at 40 words a minute), and keys replaced with redacted.
> 2. Never say "done" without running the tests.
> 3. Every commit message ends with the voice prompt number.
> 4. Readme stays in sync, and the stats script in the standard library only regenerates a good-looking SVG chart of spoken versus typed minutes per prompt at the top of the Readme on every commit: 900 by 300 dark card, total headlines, number of bars, legend, plus a per-prompt table under it. 5 keys, 11: get ignored. .env 6: don't stop to ask. Think it through, make sensible calls, and tell me after. 7: keep the file small. I review by voice. Get in remote: github.com/milap1fk/kirana Commit after every step. Push at the end. Commit this. That's from 0. Go ahead and build it.
>
> don't ask any questions like this. Just do it as told.

## 1 · 2026-10-10 14:44 +0530
words 401 · spoken ~160s · typed 602s

> merge the two logged prompts into one. That's prompt 0. It took 110 seconds. This is prompt 1. I've set the Git user for this repo to Milap Kothari. Redo the commits so far with that author.
> Now, what we have built, Kirana, is a voice khata for Indian corner shops. The shopkeeper says the days in English, and Kirana keeps the ledger and writes the WhatsApp reminder tagline: बोलो लिखा गया.
> Python standard library, only:
> - one server.py
> - one static index.html
> - SQLite file
> The page has a text box the shopkeeper dictates into with Wispr Flow or the phone's mic and presses "Grok model OpenAI/GPT-OSS 120B key from .env", temperature 0, JSON output. Turn the note into entries.
> Customer amount type: udhar or sale. Hindi numbers and words must work:
> - 500 is 5 hundred.
> - 250 is 2 hundred.
> - 1,500 is 1,000.
> - 1,200 is 1,25.
> One note can have several entries. NRIфик are trimmed, so Ramesh by Ramesh by and Shri Ramesh G are all Ramesh. Each entry becomes a confirmed card: "Ramesh ₹200 उधार सही है" with a plain English line under it. Big confirm and cancel buttons. Nothing is saved before confirm.
> Confirmed entries go to SQLite with an undo. Then कौन कितना बाकी balance पर customer उधार minus payments, different for sales excluded. With a copy reminder button that copies Ramesh जी: "200 रुपये बाकी हैं" and a WhatsApp button that opens wa.me with that text.
> Today's का हिसाब: today's total for udhar payment and sale in three titles. Today's entries: phone, first 360 px wide, no sideways scroll, 44 px button. Noto Sans for Devanagari. Add to home screen, manifest-friendly.
> Message when the AI fails:
> - No internet
> - Wrong key
> - Daily cap
> - AI confused
> Each one a plain English line. Retry on 4429 with a countdown: 1 second रुको.
> A load sample day button that adds 5 English example notes when the ledger is empty. Tests when recorded model replies, so that needs note key. Write CLAUDE.md with 5 steps.
> Phase:
> - Confirm card analyzer
> - Balance
> - WhatsApp
> - Today's 5 view
> - Phone polish, hardening, and README
> Build steps 1 and 2 now, fully with tests. Run the phase for real against Grok with 5 messy English notes, and show me the entries committed after each step. Now that's prompt 1. Go ahead and build it
